import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.api import app


def main() -> None:
    client = TestClient(app)

    health = client.get("/health")
    health.raise_for_status()
    print("health:", health.json())

    policy = client.post(
        "/api/policy/search",
        json={
            "query": "酒店入住后还能取消吗？",
            "service": "hotel",
            "policy_type": "booking_policy",
            "top_k": 3,
        },
    )
    policy.raise_for_status()
    policy_json = policy.json()
    print("policy_top:", policy_json["matches"][0]["policy_id"])

    action = client.post(
        "/api/actions/execute",
        json={
            "tool_name": "cancel_ticket",
            "arguments": {"ticket_no": "7240005432906569"},
            "passenger_id": "3442 587242",
            "thread_id": "api-test",
        },
    )
    action.raise_for_status()
    action_json = action.json()
    print("action_status:", action_json["status"])
    print("action_executed:", action_json["executed"])
    print("action_requires_confirmation:", action_json["requires_confirmation"])
    print("action_policy_id:", action_json["policy_id"])

    analytics = client.get("/api/analytics/summary")
    analytics.raise_for_status()
    print("analytics_keys:", sorted(analytics.json().keys()))

    report = client.get("/api/analytics/report")
    report.raise_for_status()
    print("report_has_content:", bool(report.json().get("content")))

    tickets = client.get("/api/service-tickets")
    tickets.raise_for_status()
    print("service_ticket_count:", len(tickets.json()["items"]))

    profile = client.get("/api/passengers/3442%20587242/profile")
    profile.raise_for_status()
    print("profile_tickets:", len(profile.json()["tickets"]))

    note = client.post(
        "/api/operator-notes",
        json={
            "note": "API smoke test note",
            "author": "tester",
            "session_id": "api-test",
            "passenger_id": "3442 587242",
        },
    )
    note.raise_for_status()
    print("note_id:", note.json()["note_id"])

    summary = client.post(
        "/api/conversation-summaries",
        json={"session_id": "api-test", "passenger_id": "3442 587242"},
    )
    summary.raise_for_status()
    print("summary_id:", summary.json()["summary_id"])

    timeline = client.get("/api/timeline", params={"session_id": "api-test", "passenger_id": "3442 587242"})
    timeline.raise_for_status()
    print("timeline_count:", len(timeline.json()["items"]))


if __name__ == "__main__":
    main()
