import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from project_config import PROJECT_ROOT, TRAVEL_DB_PATH
from tools.audit_store import init_audit_tables, table_exists


DEFAULT_REPORT_PATH = PROJECT_ROOT / "analysis" / "customer_service_analytics.md"


def fetch_scalar(conn: sqlite3.Connection, query: str, params: tuple = ()) -> int:
    row = conn.execute(query, params).fetchone()
    return int(row[0] or 0) if row else 0


def fetch_rows(conn: sqlite3.Connection, query: str, params: tuple = ()) -> list[sqlite3.Row]:
    return conn.execute(query, params).fetchall()


def table_count(conn: sqlite3.Connection, table: str) -> int:
    if not table_exists(table):
        return 0
    return fetch_scalar(conn, f'SELECT COUNT(*) FROM "{table}"')


def top_counts(conn: sqlite3.Connection, table: str, column: str, limit: int = 10) -> list[tuple[str, int]]:
    if not table_exists(table):
        return []
    rows = fetch_rows(
        conn,
        f'''
        SELECT "{column}" AS value, COUNT(*) AS count
        FROM "{table}"
        GROUP BY "{column}"
        ORDER BY count DESC
        LIMIT ?
        ''',
        (limit,),
    )
    return [(str(row["value"]), int(row["count"])) for row in rows]


def json_counter(rows: list[sqlite3.Row], column: str) -> Counter:
    counter: Counter = Counter()
    for row in rows:
        raw = row[column]
        if not raw:
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(value, list):
            counter.update(str(item) for item in value)
        elif value:
            counter[str(value)] += 1
    return counter


def markdown_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return lines


def generate_report(output_path: Path = DEFAULT_REPORT_PATH) -> None:
    init_audit_tables()
    conn = sqlite3.connect(TRAVEL_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        core_counts = {
            table: table_count(conn, table)
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

        passenger_count = fetch_scalar(conn, "SELECT COUNT(DISTINCT passenger_id) FROM tickets")
        booked_hotels = fetch_scalar(conn, "SELECT COUNT(*) FROM hotels WHERE booked = 1")
        booked_cars = fetch_scalar(conn, "SELECT COUNT(*) FROM car_rentals WHERE booked = 1")
        booked_excursions = fetch_scalar(conn, "SELECT COUNT(*) FROM trip_recommendations WHERE booked = 1")

        audit_rows = fetch_rows(conn, "SELECT * FROM action_audit_logs")
        executed = sum(int(row["executed"]) for row in audit_rows)
        blocked = len(audit_rows) - executed
        confirmation_required = sum(int(row["requires_confirmation"]) for row in audit_rows)
        human_review = sum(int(row["requires_human_review"]) for row in audit_rows)
        high_risk = sum(1 for row in audit_rows if row["risk_level"] == "high")
        policy_counter = Counter(row["policy_id"] for row in audit_rows if row["policy_id"])
        allowed_action_counter = json_counter(audit_rows, "policy_ids")

        service_tickets = fetch_rows(conn, "SELECT * FROM service_tickets")
        ticket_status = Counter(row["status"] for row in service_tickets)
        ticket_priority = Counter(row["priority"] for row in service_tickets)

        lines = [
            "# Customer Service Analytics",
            "",
            "## 1. 数据资产概览",
            "",
            *markdown_table(
                ["Table", "Rows"],
                [[table, count] for table, count in core_counts.items()],
            ),
            "",
            "## 2. 订单与服务覆盖",
            "",
            f"- 唯一乘客数：`{passenger_count}`",
            f"- 航班票号数：`{core_counts['tickets']}`",
            f"- 航段票数：`{core_counts['ticket_flights']}`",
            f"- 已预订酒店数：`{booked_hotels}`",
            f"- 已预订租车数：`{booked_cars}`",
            f"- 已预订景点/行程数：`{booked_excursions}`",
            "",
            "## 3. 票价与航班分布",
            "",
            "### 票价条件 Top 10",
            "",
            *markdown_table(
                ["Fare Condition", "Count"],
                [[value, count] for value, count in top_counts(conn, "ticket_flights", "fare_conditions", 10)],
            ),
            "",
            "### 出发机场 Top 10",
            "",
            *markdown_table(
                ["Airport", "Flights"],
                [[value, count] for value, count in top_counts(conn, "flights", "departure_airport", 10)],
            ),
            "",
            "## 4. Guardrail 与审计指标",
            "",
            f"- 写操作审计记录数：`{len(audit_rows)}`",
            f"- 已执行写操作数：`{executed}`",
            f"- 被阻止/等待确认数：`{blocked}`",
            f"- 需要确认的记录数：`{confirmation_required}`",
            f"- 命中人工复核政策数：`{human_review}`",
            f"- 高风险记录数：`{high_risk}`",
            "",
            "### 命中政策分布",
            "",
            *markdown_table(
                ["Policy", "Hits"],
                [[policy, count] for policy, count in policy_counter.most_common()],
            ),
            "",
            "## 5. 人工工单指标",
            "",
            f"- service ticket 总数：`{len(service_tickets)}`",
            "",
            "### 工单优先级",
            "",
            *markdown_table(
                ["Priority", "Count"],
                [[priority, count] for priority, count in ticket_priority.most_common()],
            ),
            "",
            "### 工单状态",
            "",
            *markdown_table(
                ["Status", "Count"],
                [[status, count] for status, count in ticket_status.most_common()],
            ),
            "",
            "## 6. 面试讲述重点",
            "",
            "- 这个项目不仅能调用工具完成客服动作，还能在写操作前强制查政策、要求确认并记录审计。",
            "- 结构化业务表和 RAG 政策库共同支持客服决策，适合讲数据建模、检索评测和风险控制。",
            "- 审计表和工单表为后续自动化率、人工升级率、风险拦截率等数据科学指标提供数据基础。",
        ]
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    finally:
        conn.close()


def main() -> None:
    generate_report()
    print(f"Wrote {DEFAULT_REPORT_PATH}")


if __name__ == "__main__":
    main()
