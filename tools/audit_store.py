import json
import sqlite3
from datetime import datetime
from typing import Any, Optional

from project_config import TRAVEL_DB_PATH


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(TRAVEL_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_audit_tables() -> None:
    with connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS action_audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                session_id TEXT,
                passenger_id TEXT,
                intent TEXT,
                tool_name TEXT NOT NULL,
                service TEXT,
                policy_type TEXT,
                policy_id TEXT,
                policy_ids TEXT,
                requires_human_review INTEGER NOT NULL DEFAULT 0,
                risk_level TEXT,
                requires_confirmation INTEGER NOT NULL DEFAULT 0,
                user_confirmation TEXT,
                confirmed INTEGER NOT NULL DEFAULT 0,
                executed INTEGER NOT NULL DEFAULT 0,
                blocked_reason TEXT,
                result TEXT,
                metadata_json TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS service_tickets (
                ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                session_id TEXT,
                passenger_id TEXT,
                issue_type TEXT NOT NULL,
                priority TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                tool_name TEXT,
                intent TEXT,
                policy_id TEXT,
                reason TEXT,
                metadata_json TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS operator_notes (
                note_id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                session_id TEXT,
                passenger_id TEXT,
                author TEXT NOT NULL DEFAULT 'operator',
                note TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS conversation_summaries (
                summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                session_id TEXT NOT NULL,
                passenger_id TEXT,
                summary TEXT NOT NULL,
                main_intent TEXT,
                resolution_status TEXT,
                tools_used TEXT,
                policies_used TEXT
            )
            """
        )
        conn.commit()


def insert_action_audit(event: dict[str, Any]) -> int:
    init_audit_tables()
    policy = event.get("policy") or {}
    metadata = {
        key: value
        for key, value in event.items()
        if key
        not in {
            "created_at",
            "session_id",
            "passenger_id",
            "intent",
            "tool_name",
            "service",
            "policy_type",
            "requires_confirmation",
            "user_confirmation",
            "confirmed",
            "executed",
            "blocked_reason",
            "result",
        }
    }
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO action_audit_logs (
                created_at, session_id, passenger_id, intent, tool_name, service,
                policy_type, policy_id, policy_ids, requires_human_review,
                risk_level, requires_confirmation, user_confirmation, confirmed,
                executed, blocked_reason, result, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.get("created_at") or datetime.now().isoformat(timespec="seconds"),
                event.get("session_id"),
                event.get("passenger_id"),
                event.get("intent"),
                event.get("tool_name"),
                event.get("service"),
                event.get("policy_type"),
                policy.get("policy_id"),
                json.dumps(policy.get("policy_ids") or [], ensure_ascii=False),
                int(bool(policy.get("requires_human_review"))),
                policy.get("risk_level"),
                int(bool(event.get("requires_confirmation"))),
                event.get("user_confirmation"),
                int(bool(event.get("confirmed"))),
                int(bool(event.get("executed"))),
                event.get("blocked_reason"),
                event.get("result"),
                json.dumps(metadata, ensure_ascii=False, default=str),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def create_service_ticket(
    *,
    issue_type: str,
    priority: str,
    reason: str,
    tool_name: Optional[str] = None,
    intent: Optional[str] = None,
    policy_id: Optional[str] = None,
    session_id: Optional[str] = None,
    passenger_id: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> int:
    init_audit_tables()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO service_tickets (
                created_at, session_id, passenger_id, issue_type, priority,
                status, tool_name, intent, policy_id, reason, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(timespec="seconds"),
                session_id,
                passenger_id,
                issue_type,
                priority,
                tool_name,
                intent,
                policy_id,
                reason,
                json.dumps(metadata or {}, ensure_ascii=False, default=str),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def update_service_ticket_status(ticket_id: int, status: str) -> None:
    init_audit_tables()
    with connect() as conn:
        cursor = conn.execute(
            "UPDATE service_tickets SET status = ? WHERE ticket_id = ?",
            (status, ticket_id),
        )
        if cursor.rowcount == 0:
            raise ValueError(f"service ticket {ticket_id} not found")
        conn.commit()


def add_operator_note(
    *,
    note: str,
    author: str = "operator",
    session_id: Optional[str] = None,
    passenger_id: Optional[str] = None,
) -> int:
    init_audit_tables()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO operator_notes (created_at, session_id, passenger_id, author, note)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(timespec="seconds"),
                session_id,
                passenger_id,
                author,
                note,
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def upsert_conversation_summary(
    *,
    session_id: str,
    summary: str,
    passenger_id: Optional[str] = None,
    main_intent: Optional[str] = None,
    resolution_status: Optional[str] = None,
    tools_used: Optional[list[str]] = None,
    policies_used: Optional[list[str]] = None,
) -> int:
    init_audit_tables()
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO conversation_summaries (
                created_at, session_id, passenger_id, summary, main_intent,
                resolution_status, tools_used, policies_used
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now().isoformat(timespec="seconds"),
                session_id,
                passenger_id,
                summary,
                main_intent,
                resolution_status,
                json.dumps(tools_used or [], ensure_ascii=False),
                json.dumps(policies_used or [], ensure_ascii=False),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def table_exists(table_name: str) -> bool:
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?",
            (table_name,),
        ).fetchone()
        return bool(row)
