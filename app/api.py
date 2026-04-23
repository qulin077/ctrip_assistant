import sqlite3
import sys
from pathlib import Path
from typing import Any, Optional
import re

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from project_config import TRAVEL_DB_PATH
from project_config import PROJECT_ROOT
from graph_chat.workflow import create_graph
from tools import action_guard
from tools.audit_store import (
    add_operator_note,
    connect,
    init_audit_tables,
    update_service_ticket_status,
    upsert_conversation_summary,
)
from tools.customer_analytics import generate_report
from tools.retriever_vector import lookup_policy_structured


PROTECTED_ACTIONS = {
    "update_ticket_to_new_flight": action_guard.update_ticket_to_new_flight,
    "cancel_ticket": action_guard.cancel_ticket,
    "book_hotel": action_guard.book_hotel,
    "update_hotel": action_guard.update_hotel,
    "cancel_hotel": action_guard.cancel_hotel,
    "book_car_rental": action_guard.book_car_rental,
    "update_car_rental": action_guard.update_car_rental,
    "cancel_car_rental": action_guard.cancel_car_rental,
    "book_excursion": action_guard.book_excursion,
    "update_excursion": action_guard.update_excursion,
    "cancel_excursion": action_guard.cancel_excursion,
}

GRAPH = None


class PolicySearchRequest(BaseModel):
    query: str
    service: Optional[str] = None
    policy_type: Optional[str] = None
    top_k: int = Field(default=3, ge=1, le=10)


class GuardedActionRequest(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    user_confirmation: Optional[str] = None
    passenger_id: str = "3442 587242"
    thread_id: str = "demo-session"


class AgentChatRequest(BaseModel):
    message: str
    passenger_id: str = "3442 587242"
    thread_id: str = "copilot-session"


class ServiceTicketUpdateRequest(BaseModel):
    status: str


class OperatorNoteRequest(BaseModel):
    note: str
    author: str = "operator"
    session_id: Optional[str] = None
    passenger_id: Optional[str] = None


class ConversationSummaryRequest(BaseModel):
    session_id: str
    passenger_id: Optional[str] = None


def get_graph():
    global GRAPH
    if GRAPH is None:
        GRAPH = create_graph()
    return GRAPH


def message_to_dict(message) -> dict[str, Any]:
    return {
        "type": message.__class__.__name__,
        "content": getattr(message, "content", ""),
        "name": getattr(message, "name", None),
        "tool_calls": getattr(message, "tool_calls", None),
    }


def extract_policy_cards(messages: list) -> list[dict[str, Any]]:
    cards = []
    for message in messages:
        content = str(getattr(message, "content", "") or "")
        if "policy_id:" not in content:
            continue
        blocks = content.split("【政策命中")
        for block in blocks:
            policy_match = re.search(r"policy_id:\s*([^\n]+)", block)
            if not policy_match:
                continue
            cards.append(
                {
                    "policy_id": policy_match.group(1).strip(),
                    "title": _regex_value(block, r"title:\s*([^\n]+)"),
                    "section_title": _regex_value(block, r"section_title:\s*([^\n]+)"),
                    "requires_human_review": _regex_value(block, r"requires_human_review:\s*([^\n]+)") in {"是", "True", "true"},
                    "requires_confirmation": _regex_value(block, r"requires_confirmation:\s*([^\n]+)") in {"是", "True", "true"},
                    "risk_level": _regex_value(block, r"risk_level:\s*([^\n]+)") or "normal",
                }
            )
    return cards


def _regex_value(text: str, pattern: str) -> Optional[str]:
    match = re.search(pattern, text)
    return match.group(1).strip() if match else None


def create_app() -> FastAPI:
    app = FastAPI(
        title="Enterprise Travel Customer Service Agent API",
        version="0.1.0",
        description="Policy RAG, guarded actions, audit logs, and service analytics for the Ctrip Assistant demo.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def startup() -> None:
        init_audit_tables()

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "status": "ok",
            "database_exists": TRAVEL_DB_PATH.exists(),
            "protected_actions": len(PROTECTED_ACTIONS),
        }

    @app.get("/api/actions")
    def list_actions() -> dict[str, Any]:
        return {"actions": sorted(PROTECTED_ACTIONS)}

    @app.post("/api/agent/chat")
    def agent_chat(request: AgentChatRequest) -> dict[str, Any]:
        graph = get_graph()
        config = {
            "configurable": {
                "passenger_id": request.passenger_id,
                "thread_id": request.thread_id,
            }
        }
        result = graph.invoke({"messages": ("user", request.message)}, config)
        messages = result.get("messages", [])
        assistant_message = messages[-1] if messages else None
        audit_rows = recent_audit(limit=5, session_id=request.thread_id)["items"]
        return {
            "thread_id": request.thread_id,
            "passenger_id": request.passenger_id,
            "assistant_output": getattr(assistant_message, "content", "") if assistant_message else "",
            "messages": [message_to_dict(message) for message in messages[-8:]],
            "policy_cards": extract_policy_cards(messages),
            "recent_audit": audit_rows,
        }

    @app.post("/api/policy/search")
    def search_policy(request: PolicySearchRequest) -> dict[str, Any]:
        return lookup_policy_structured(
            query=request.query,
            top_k=request.top_k,
            service=request.service,
            policy_type=request.policy_type,
        )

    @app.post("/api/actions/execute")
    def execute_guarded_action(request: GuardedActionRequest) -> dict[str, Any]:
        tool = PROTECTED_ACTIONS.get(request.tool_name)
        if tool is None:
            raise HTTPException(status_code=404, detail=f"Unknown guarded action: {request.tool_name}")
        try:
            result = action_guard.execute_guarded_action_structured(
                tool_name=request.tool_name,
                arguments=request.arguments,
                user_confirmation=request.user_confirmation,
                config={
                    "configurable": {
                        "passenger_id": request.passenger_id,
                        "thread_id": request.thread_id,
                    }
                },
            )
        except TypeError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid arguments for {request.tool_name}: {exc}") from exc
        except (KeyError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except sqlite3.Error as exc:
            raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc
        policy_summary = result.get("policy_summary") or {}
        return {
            "tool_name": request.tool_name,
            "status": result.get("status"),
            "executed": bool(result.get("executed")),
            "requires_confirmation": bool(result.get("requires_confirmation")),
            "requires_human_review": bool(result.get("requires_human_review")),
            "policy_id": result.get("policy_id"),
            "policy_summary": policy_summary,
            "result_text": result.get("result_text"),
            "confirmation_prompt": result.get("confirmation_prompt"),
            "service_ticket_created": bool(result.get("service_ticket_created")),
            "service_ticket_id": result.get("service_ticket_id"),
            "blocked_reason": result.get("blocked_reason"),
            "display_text": action_guard.format_guarded_result(result),
        }

    @app.get("/api/audit/recent")
    def recent_audit(limit: int = 20, session_id: Optional[str] = None, passenger_id: Optional[str] = None) -> dict[str, Any]:
        init_audit_tables()
        filters = []
        params: list[Any] = []
        if session_id:
            filters.append("session_id = ?")
            params.append(session_id)
        if passenger_id:
            filters.append("passenger_id = ?")
            params.append(passenger_id)
        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)
        with connect() as conn:
            rows = conn.execute(
                f"""
                SELECT id, created_at, passenger_id, intent, tool_name, policy_id,
                       requires_human_review, risk_level, requires_confirmation,
                       confirmed, executed, blocked_reason, result
                FROM action_audit_logs
                {where_clause}
                ORDER BY id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return {"items": [dict(row) for row in rows]}

    @app.get("/api/service-tickets")
    def service_tickets(limit: int = 20, status: Optional[str] = None) -> dict[str, Any]:
        init_audit_tables()
        where_clause = "WHERE status = ?" if status else ""
        params = (status, limit) if status else (limit,)
        with connect() as conn:
            rows = conn.execute(
                f"""
                SELECT ticket_id, created_at, passenger_id, issue_type, priority,
                       status, tool_name, intent, policy_id, reason
                FROM service_tickets
                {where_clause}
                ORDER BY ticket_id DESC
                LIMIT ?
                """,
                params,
            ).fetchall()
        return {"items": [dict(row) for row in rows]}

    @app.patch("/api/service-tickets/{ticket_id}")
    def update_ticket(ticket_id: int, request: ServiceTicketUpdateRequest) -> dict[str, Any]:
        try:
            update_service_ticket_status(ticket_id, request.status)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {"ticket_id": ticket_id, "status": request.status}

    @app.get("/api/passengers/{passenger_id}/profile")
    def passenger_profile(passenger_id: str) -> dict[str, Any]:
        init_audit_tables()
        with connect() as conn:
            tickets = conn.execute(
                "SELECT ticket_no, book_ref, passenger_id FROM tickets WHERE passenger_id = ? LIMIT 10",
                (passenger_id,),
            ).fetchall()
            flights = conn.execute(
                """
                SELECT t.ticket_no, f.flight_id, f.flight_no, f.departure_airport,
                       f.arrival_airport, f.scheduled_departure, tf.fare_conditions
                FROM tickets t
                JOIN ticket_flights tf ON t.ticket_no = tf.ticket_no
                JOIN flights f ON tf.flight_id = f.flight_id
                WHERE t.passenger_id = ?
                LIMIT 10
                """,
                (passenger_id,),
            ).fetchall()
            audit_count = conn.execute(
                "SELECT COUNT(*) AS count FROM action_audit_logs WHERE passenger_id = ?",
                (passenger_id,),
            ).fetchone()["count"]
            ticket_count = conn.execute(
                "SELECT COUNT(*) AS count FROM service_tickets WHERE passenger_id = ?",
                (passenger_id,),
            ).fetchone()["count"]
        return {
            "passenger_id": passenger_id,
            "tickets": [dict(row) for row in tickets],
            "flights": [dict(row) for row in flights],
            "audit_count": audit_count,
            "service_ticket_count": ticket_count,
        }

    @app.get("/api/timeline")
    def action_timeline(session_id: Optional[str] = None, passenger_id: Optional[str] = None, limit: int = 50) -> dict[str, Any]:
        init_audit_tables()
        params: list[Any] = []
        filters = []
        if session_id:
            filters.append("session_id = ?")
            params.append(session_id)
        if passenger_id:
            filters.append("passenger_id = ?")
            params.append(passenger_id)
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        with connect() as conn:
            audits = conn.execute(
                f"""
                SELECT created_at, 'audit' AS event_type, tool_name AS title,
                       intent AS detail, policy_id, executed, blocked_reason
                FROM action_audit_logs
                {where}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                tuple(params + [limit]),
            ).fetchall()
            tickets = conn.execute(
                f"""
                SELECT created_at, 'service_ticket' AS event_type, tool_name AS title,
                       reason AS detail, policy_id, status AS executed, priority AS blocked_reason
                FROM service_tickets
                {where}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                tuple(params + [limit]),
            ).fetchall()
            notes = conn.execute(
                f"""
                SELECT created_at, 'operator_note' AS event_type, author AS title,
                       note AS detail, NULL AS policy_id, NULL AS executed, NULL AS blocked_reason
                FROM operator_notes
                {where}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                tuple(params + [limit]),
            ).fetchall()
        events = [dict(row) for row in audits + tickets + notes]
        events.sort(key=lambda item: item["created_at"], reverse=True)
        return {"items": events[:limit]}

    @app.post("/api/operator-notes")
    def create_operator_note(request: OperatorNoteRequest) -> dict[str, Any]:
        note_id = add_operator_note(
            note=request.note,
            author=request.author,
            session_id=request.session_id,
            passenger_id=request.passenger_id,
        )
        return {"note_id": note_id}

    @app.get("/api/operator-notes")
    def operator_notes(session_id: Optional[str] = None, passenger_id: Optional[str] = None, limit: int = 20) -> dict[str, Any]:
        init_audit_tables()
        filters = []
        params: list[Any] = []
        if session_id:
            filters.append("session_id = ?")
            params.append(session_id)
        if passenger_id:
            filters.append("passenger_id = ?")
            params.append(passenger_id)
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)
        with connect() as conn:
            rows = conn.execute(
                f"""
                SELECT note_id, created_at, session_id, passenger_id, author, note
                FROM operator_notes
                {where}
                ORDER BY note_id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return {"items": [dict(row) for row in rows]}

    @app.post("/api/conversation-summaries")
    def create_conversation_summary(request: ConversationSummaryRequest) -> dict[str, Any]:
        audit = recent_audit(limit=20, session_id=request.session_id, passenger_id=request.passenger_id)["items"]
        tools = sorted({row.get("tool_name") for row in audit if row.get("tool_name")})
        policies = sorted({row.get("policy_id") for row in audit if row.get("policy_id")})
        executed = sum(1 for row in audit if row.get("executed"))
        blocked = len(audit) - executed
        summary = (
            f"会话 {request.session_id} 共记录 {len(audit)} 个受保护动作，"
            f"已执行 {executed} 个，等待确认或阻断 {blocked} 个。"
        )
        summary_id = upsert_conversation_summary(
            session_id=request.session_id,
            passenger_id=request.passenger_id,
            summary=summary,
            main_intent=", ".join(tools[:3]) if tools else None,
            resolution_status="needs_follow_up" if blocked else "resolved",
            tools_used=tools,
            policies_used=policies,
        )
        return {"summary_id": summary_id, "summary": summary, "tools_used": tools, "policies_used": policies}

    @app.get("/api/conversation-summaries")
    def conversation_summaries(session_id: Optional[str] = None, passenger_id: Optional[str] = None, limit: int = 10) -> dict[str, Any]:
        init_audit_tables()
        filters = []
        params: list[Any] = []
        if session_id:
            filters.append("session_id = ?")
            params.append(session_id)
        if passenger_id:
            filters.append("passenger_id = ?")
            params.append(passenger_id)
        where = f"WHERE {' AND '.join(filters)}" if filters else ""
        params.append(limit)
        with connect() as conn:
            rows = conn.execute(
                f"""
                SELECT summary_id, created_at, session_id, passenger_id, summary,
                       main_intent, resolution_status, tools_used, policies_used
                FROM conversation_summaries
                {where}
                ORDER BY summary_id DESC
                LIMIT ?
                """,
                tuple(params),
            ).fetchall()
        return {"items": [dict(row) for row in rows]}

    @app.get("/api/analytics/summary")
    def analytics_summary() -> dict[str, Any]:
        init_audit_tables()
        with connect() as conn:
            tables = {
                table: conn.execute(f'SELECT COUNT(*) AS count FROM "{table}"').fetchone()["count"]
                for table in [
                    "bookings",
                    "tickets",
                    "ticket_flights",
                    "flights",
                    "boarding_passes",
                    "hotels",
                    "car_rentals",
                    "trip_recommendations",
                    "action_audit_logs",
                    "service_tickets",
                ]
            }
            audit = conn.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    SUM(executed) AS executed,
                    SUM(requires_confirmation) AS requires_confirmation,
                    SUM(requires_human_review) AS requires_human_review,
                    SUM(CASE WHEN risk_level = 'high' THEN 1 ELSE 0 END) AS high_risk
                FROM action_audit_logs
                """
            ).fetchone()
        total = int(audit["total"] or 0)
        executed = int(audit["executed"] or 0)
        return {
            "tables": dict(tables),
            "guardrails": {
                "audit_total": total,
                "executed": executed,
                "blocked_or_pending": total - executed,
                "requires_confirmation": int(audit["requires_confirmation"] or 0),
                "requires_human_review": int(audit["requires_human_review"] or 0),
                "high_risk": int(audit["high_risk"] or 0),
            },
        }

    @app.post("/api/analytics/report")
    def build_analytics_report() -> dict[str, Any]:
        generate_report()
        return {"path": "analysis/customer_service_analytics.md"}

    @app.get("/api/analytics/report")
    def get_analytics_report() -> dict[str, Any]:
        report_path = PROJECT_ROOT / "analysis" / "customer_service_analytics.md"
        if not report_path.exists():
            generate_report(report_path)
        return {
            "path": "analysis/customer_service_analytics.md",
            "content": report_path.read_text(encoding="utf-8"),
        }

    return app


app = create_app()
