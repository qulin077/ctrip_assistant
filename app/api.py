import sqlite3
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from project_config import TRAVEL_DB_PATH
from tools import action_guard
from tools.audit_store import connect, init_audit_tables
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
        payload = dict(request.arguments)
        if request.user_confirmation is not None:
            payload["user_confirmation"] = request.user_confirmation
        try:
            result = tool.invoke(
                payload,
                config={
                    "configurable": {
                        "passenger_id": request.passenger_id,
                        "thread_id": request.thread_id,
                    }
                },
            )
        except TypeError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid arguments for {request.tool_name}: {exc}") from exc
        except sqlite3.Error as exc:
            raise HTTPException(status_code=500, detail=f"Database error: {exc}") from exc
        return {
            "tool_name": request.tool_name,
            "executed": "写操作执行结果" in result,
            "requires_confirmation": "是否确认" in result or "requires_confirmation: 是" in result,
            "result": result,
        }

    @app.get("/api/audit/recent")
    def recent_audit(limit: int = 20) -> dict[str, Any]:
        init_audit_tables()
        with connect() as conn:
            rows = conn.execute(
                """
                SELECT id, created_at, passenger_id, intent, tool_name, policy_id,
                       requires_human_review, risk_level, requires_confirmation,
                       confirmed, executed, blocked_reason, result
                FROM action_audit_logs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return {"items": [dict(row) for row in rows]}

    @app.get("/api/service-tickets")
    def service_tickets(limit: int = 20) -> dict[str, Any]:
        init_audit_tables()
        with connect() as conn:
            rows = conn.execute(
                """
                SELECT ticket_id, created_at, passenger_id, issue_type, priority,
                       status, tool_name, intent, policy_id, reason
                FROM service_tickets
                ORDER BY ticket_id DESC
                LIMIT ?
                """,
                (limit,),
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

    return app


app = create_app()
