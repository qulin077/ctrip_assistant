import sys
from pathlib import Path
from typing import Any, Optional

import requests
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.customer_analytics import generate_report


API_BASE_URL = st.sidebar.text_input("API Base URL", value="http://127.0.0.1:8000").rstrip("/")


def api_get(path: str, **params) -> dict[str, Any]:
    response = requests.get(f"{API_BASE_URL}{path}", params=params, timeout=20)
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    response = requests.post(f"{API_BASE_URL}{path}", json=payload or {}, timeout=30)
    response.raise_for_status()
    return response.json()


def render_status() -> None:
    st.title("Enterprise Travel Customer Service Agent")
    st.caption("RAG policy retrieval, guarded actions, audit logs, and service analytics.")
    try:
        health = api_get("/health")
        st.success(f"Backend connected. Protected actions: {health['protected_actions']}")
    except Exception as exc:
        st.warning(f"Backend not reachable: {exc}")
        st.info("Run: uvicorn app.api:app --reload --port 8000")


def render_kpis() -> None:
    try:
        summary = api_get("/api/analytics/summary")
    except Exception:
        return
    tables = summary["tables"]
    guardrails = summary["guardrails"]
    cols = st.columns(4)
    cols[0].metric("Tickets", f"{tables.get('tickets', 0):,}")
    cols[1].metric("Flight Segments", f"{tables.get('ticket_flights', 0):,}")
    cols[2].metric("Audit Logs", guardrails.get("audit_total", 0))
    cols[3].metric("Service Tickets", tables.get("service_tickets", 0))
    st.progress(
        0 if guardrails.get("audit_total", 0) == 0 else guardrails.get("executed", 0) / guardrails["audit_total"],
        text="Guarded action execution rate",
    )


def render_policy_search() -> None:
    st.subheader("Policy Search")
    with st.form("policy_search"):
        query = st.text_input("Query", value="酒店入住后还能取消吗？")
        col1, col2, col3 = st.columns(3)
        service = col1.selectbox("Service", ["", "flight", "hotel", "car_rental", "excursion", "booking"])
        policy_type = col2.selectbox(
            "Policy Type",
            ["", "change", "refund", "invoice", "payment", "fare", "platform", "booking_policy"],
        )
        top_k = col3.number_input("Top K", min_value=1, max_value=10, value=3)
        submitted = st.form_submit_button("Search Policy")
    if submitted:
        result = api_post(
            "/api/policy/search",
            {
                "query": query,
                "service": service or None,
                "policy_type": policy_type or None,
                "top_k": top_k,
            },
        )
        for match in result.get("matches", []):
            st.markdown(f"**{match['policy_id']}** · {match['section_title']}")
            st.write(
                {
                    "service": match.get("service"),
                    "policy_type": match.get("policy_type"),
                    "requires_human_review": match.get("requires_human_review"),
                    "requires_confirmation": match.get("requires_confirmation"),
                    "risk_level": match.get("risk_level") or "normal",
                    "allowed_action": match.get("allowed_action"),
                    "similarity": match.get("similarity"),
                }
            )
            st.info(match.get("chunk_text", ""))


def render_guarded_action() -> None:
    st.subheader("Guarded Action Demo")
    action = st.selectbox(
        "Action",
        [
            "cancel_ticket",
            "update_ticket_to_new_flight",
            "book_hotel",
            "cancel_hotel",
            "book_car_rental",
            "cancel_car_rental",
            "book_excursion",
            "cancel_excursion",
        ],
    )
    passenger_id = st.text_input("Passenger ID", value="3442 587242")
    thread_id = st.text_input("Session ID", value="streamlit-demo")
    user_confirmation = st.text_input("User Confirmation", value="")
    st.caption("Leave confirmation empty to preview the confirmation gate without executing writes.")

    args: dict[str, Any] = {}
    if action in {"cancel_ticket", "update_ticket_to_new_flight"}:
        args["ticket_no"] = st.text_input("Ticket No", value="7240005432906569")
    if action == "update_ticket_to_new_flight":
        args["new_flight_id"] = st.number_input("New Flight ID", min_value=1, value=1)
    if action in {"book_hotel", "cancel_hotel"}:
        args["hotel_id"] = st.number_input("Hotel ID", min_value=1, value=1)
    if action in {"book_car_rental", "cancel_car_rental"}:
        args["rental_id"] = st.number_input("Rental ID", min_value=1, value=1)
    if action in {"book_excursion", "cancel_excursion"}:
        args["recommendation_id"] = st.number_input("Recommendation ID", min_value=1, value=1)

    if st.button("Run Guarded Action"):
        result = api_post(
            "/api/actions/execute",
            {
                "tool_name": action,
                "arguments": args,
                "user_confirmation": user_confirmation or None,
                "passenger_id": passenger_id,
                "thread_id": thread_id,
            },
        )
        if result.get("executed"):
            st.success("Write action executed")
        else:
            st.warning("Write action not executed")
        st.text(result.get("result", ""))


def render_audit() -> None:
    st.subheader("Audit Logs & Service Tickets")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Recent Audit Logs**")
        try:
            rows = api_get("/api/audit/recent", limit=10).get("items", [])
            st.dataframe(rows, use_container_width=True)
        except Exception as exc:
            st.error(str(exc))
    with col2:
        st.markdown("**Service Tickets**")
        try:
            rows = api_get("/api/service-tickets", limit=10).get("items", [])
            st.dataframe(rows, use_container_width=True)
        except Exception as exc:
            st.error(str(exc))


def render_report() -> None:
    st.subheader("Customer Service Analytics")
    if st.button("Generate Analytics Report"):
        api_post("/api/analytics/report")
    report_path = Path(__file__).resolve().parents[1] / "analysis" / "customer_service_analytics.md"
    if report_path.exists():
        st.markdown(report_path.read_text(encoding="utf-8"))
    else:
        generate_report(report_path)
        st.markdown(report_path.read_text(encoding="utf-8"))


def main() -> None:
    st.set_page_config(page_title="Ctrip Assistant", layout="wide")
    render_status()
    render_kpis()
    tabs = st.tabs(["Policy Search", "Guarded Action", "Audit", "Analytics"])
    with tabs[0]:
        render_policy_search()
    with tabs[1]:
        render_guarded_action()
    with tabs[2]:
        render_audit()
    with tabs[3]:
        render_report()


if __name__ == "__main__":
    main()
