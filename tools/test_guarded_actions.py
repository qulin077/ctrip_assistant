import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from project_config import TRAVEL_DB_PATH
from tools.action_guard import cancel_ticket, update_ticket_to_new_flight
from tools.init_db import update_dates
from tools.retriever_vector import lookup_policy_structured


PASSENGER_ID = "3442 587242"


def fetch_sample_ticket() -> str:
    conn = sqlite3.connect(TRAVEL_DB_PATH)
    try:
        row = conn.execute(
            "SELECT ticket_no FROM tickets WHERE passenger_id = ? LIMIT 1",
            (PASSENGER_ID,),
        ).fetchone()
    finally:
        conn.close()
    if not row:
        raise RuntimeError(f"No sample ticket found for passenger {PASSENGER_ID}")
    return row[0]


def print_policy_summary(result: dict) -> None:
    matches = result.get("matches", [])
    if not matches:
        print("Policy hit: none")
        return
    top = matches[0]
    print(f"Policy hit: {top.get('policy_id')} | section={top.get('section_title')}")
    print(f"requires_human_review={top.get('requires_human_review')}")
    print(f"requires_confirmation={top.get('requires_confirmation')}")
    print(f"risk_level={top.get('risk_level') or 'normal'}")
    print(f"allowed_action={top.get('allowed_action')}")


def scenario_change_without_confirmation(ticket_no: str) -> None:
    print("=" * 80)
    print("Scenario 1: 用户要求改签，但未确认")
    result = update_ticket_to_new_flight.invoke(
        {
            "ticket_no": ticket_no,
            "new_flight_id": 1,
        },
        config={"configurable": {"passenger_id": PASSENGER_ID}},
    )
    print(result)
    print("triggered_confirmation=", "是否确认" in result)
    print("executed_write=", "写操作执行结果" in result)


def scenario_cancel_with_confirmation(ticket_no: str) -> None:
    print("=" * 80)
    print("Scenario 2: 用户要求取消机票，并明确确认")
    result = cancel_ticket.invoke(
        {
            "ticket_no": ticket_no,
            "user_confirmation": "确认",
        },
        config={"configurable": {"passenger_id": PASSENGER_ID}},
    )
    print(result)
    print("triggered_confirmation=", "requires_confirmation: 是" in result)
    print("executed_write=", "写操作执行结果" in result)


def scenario_hotel_after_checkin_cancel() -> None:
    print("=" * 80)
    print("Scenario 3: 用户咨询酒店入住后取消")
    result = lookup_policy_structured(
        query="酒店入住后还能取消吗 需要人工处理吗",
        service="hotel",
        policy_type="booking_policy",
    )
    print_policy_summary(result)
    cautious = any(
        match.get("risk_level") == "high" or "人工" in match.get("chunk_text", "")
        for match in result.get("matches", [])
    )
    print("cautious_reply=", cautious)
    if cautious:
        print("建议回复：入住后取消通常不可自动承诺退款，需结合酒店规则或转人工确认。")


def scenario_refund_human_review() -> None:
    print("=" * 80)
    print("Scenario 4: 用户咨询退款")
    result = lookup_policy_structured(
        query="取消机票后退款多久到账 退款规则",
        service="flight",
        policy_type="refund",
    )
    print_policy_summary(result)
    cautious = any(match.get("requires_human_review") for match in result.get("matches", []))
    print("requires_cautious_reply=", cautious)
    if cautious:
        print("建议回复：退款政策存在待人工确认内容，应提示以人工复核或实际票规为准。")


def main() -> None:
    update_dates()
    ticket_no = fetch_sample_ticket()
    scenario_change_without_confirmation(ticket_no)
    scenario_cancel_with_confirmation(ticket_no)
    scenario_hotel_after_checkin_cancel()
    scenario_refund_human_review()


if __name__ == "__main__":
    main()
