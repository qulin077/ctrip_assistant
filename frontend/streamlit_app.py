from typing import Any, Optional

import requests
import streamlit as st


API_BASE_URL = st.sidebar.text_input("API Base URL", value="http://127.0.0.1:8000").rstrip("/")


def ensure_copilot_state() -> None:
    st.session_state.setdefault("copilot_messages", [])
    st.session_state.setdefault("copilot_thread_id", "streamlit-copilot")
    st.session_state.setdefault("copilot_passenger_id", "3442 587242")


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


def render_policy_card(policy: dict[str, Any]) -> None:
    if not policy:
        return
    with st.container(border=True):
        st.markdown(f"**Policy:** `{policy.get('policy_id')}`")
        cols = st.columns(3)
        cols[0].metric("Human Review", "Yes" if policy.get("requires_human_review") else "No")
        cols[1].metric("Confirmation", "Yes" if policy.get("requires_confirmation") else "No")
        cols[2].metric("Risk", policy.get("risk_level") or "normal")
        st.caption(f"Section: {policy.get('section_title')}")
        allowed = policy.get("allowed_action") or []
        if allowed:
            st.caption("Allowed action: " + ", ".join(allowed))


def render_action_card(result: dict[str, Any]) -> None:
    with st.container(border=True):
        st.markdown(f"**Action:** `{result.get('tool_name')}`")
        cols = st.columns(4)
        cols[0].metric("Status", result.get("status") or "-")
        cols[1].metric("Executed", "Yes" if result.get("executed") else "No")
        cols[2].metric("Ticket", "Created" if result.get("service_ticket_created") else "No")
        cols[3].metric("Policy", result.get("policy_id") or "-")
        if result.get("confirmation_prompt"):
            st.warning(result["confirmation_prompt"])
        st.text(result.get("display_text") or result.get("result_text") or "")


def render_audit_event_card(event: dict[str, Any]) -> None:
    with st.container(border=True):
        st.markdown(f"**Audit Event:** `{event.get('tool_name')}`")
        cols = st.columns(4)
        cols[0].metric("Executed", "Yes" if event.get("executed") else "No")
        cols[1].metric("Confirm", "Yes" if event.get("requires_confirmation") else "No")
        cols[2].metric("Risk", event.get("risk_level") or "normal")
        cols[3].metric("Policy", event.get("policy_id") or "-")
        st.caption(event.get("intent") or "")
        if event.get("blocked_reason"):
            st.warning(f"Blocked reason: {event['blocked_reason']}")


def render_copilot() -> None:
    ensure_copilot_state()
    st.subheader("Customer Copilot")
    st.caption("LangGraph-powered copilot for policy questions and guarded write actions.")
    col1, col2 = st.columns(2)
    st.session_state.copilot_passenger_id = col1.text_input(
        "Passenger ID",
        value=st.session_state.copilot_passenger_id,
        key="copilot_passenger_input",
    )
    st.session_state.copilot_thread_id = col2.text_input(
        "Session ID",
        value=st.session_state.copilot_thread_id,
        key="copilot_thread_input",
    )

    for item in st.session_state.copilot_messages:
        with st.chat_message(item["role"]):
            st.markdown(item["content"])
            for policy in item.get("policies", []):
                render_policy_card(policy)
            if item.get("action_result"):
                render_action_card(item["action_result"])
            if item.get("latest_audit"):
                render_audit_event_card(item["latest_audit"])
            if item.get("audit"):
                st.dataframe(item["audit"], use_container_width=True)

    prompt = st.chat_input("Ask the LangGraph assistant")
    if not prompt:
        return

    st.session_state.copilot_messages.append({"role": "user", "content": prompt})
    assistant_item: dict[str, Any] = {"role": "assistant", "content": ""}

    try:
        result = api_post(
            "/api/agent/chat",
            {
                "message": prompt,
                "passenger_id": st.session_state.copilot_passenger_id,
                "thread_id": st.session_state.copilot_thread_id,
            },
        )
        assistant_item["content"] = result.get("assistant_output") or "已处理。"
        assistant_item["policies"] = result.get("policy_cards", [])
        audit_rows = result.get("recent_audit", [])
        assistant_item["audit"] = audit_rows
        if audit_rows:
            assistant_item["latest_audit"] = audit_rows[0]
    except Exception as exc:
        assistant_item["content"] = f"处理失败：{exc}"

    st.session_state.copilot_messages.append(assistant_item)
    st.rerun()


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
        st.write(
            {
                "status": result.get("status"),
                "policy_id": result.get("policy_id"),
                "requires_confirmation": result.get("requires_confirmation"),
                "requires_human_review": result.get("requires_human_review"),
                "service_ticket_created": result.get("service_ticket_created"),
            }
        )
        st.text(result.get("display_text") or result.get("result_text", ""))


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

    st.markdown("**Update Service Ticket**")
    c1, c2, c3 = st.columns([1, 1, 2])
    ticket_id = c1.number_input("Ticket ID", min_value=1, value=1)
    new_status = c2.selectbox("Status", ["open", "in_progress", "resolved", "closed"])
    if c3.button("Update Ticket Status"):
        try:
            result = requests.patch(
                f"{API_BASE_URL}/api/service-tickets/{ticket_id}",
                json={"status": new_status},
                timeout=20,
            )
            result.raise_for_status()
            st.success(f"Ticket {ticket_id} updated to {new_status}")
        except Exception as exc:
            st.error(str(exc))


def render_customer_context() -> None:
    st.subheader("Passenger Profile, Timeline & Notes")
    col1, col2 = st.columns(2)
    passenger_id = col1.text_input("Passenger ID", value="3442 587242", key="profile_passenger")
    session_id = col2.text_input("Session ID", value="streamlit-copilot", key="profile_session")

    profile = api_get(f"/api/passengers/{passenger_id}/profile")
    k1, k2, k3 = st.columns(3)
    k1.metric("Tickets", len(profile.get("tickets", [])))
    k2.metric("Audit Logs", profile.get("audit_count", 0))
    k3.metric("Service Tickets", profile.get("service_ticket_count", 0))

    with st.expander("Tickets and Flights", expanded=True):
        st.dataframe(profile.get("tickets", []), use_container_width=True)
        st.dataframe(profile.get("flights", []), use_container_width=True)

    st.markdown("**Operator Notes**")
    note = st.text_area("Add note")
    if st.button("Save Operator Note"):
        api_post(
            "/api/operator-notes",
            {
                "note": note,
                "author": "operator",
                "session_id": session_id,
                "passenger_id": passenger_id,
            },
        )
        st.success("Note saved")
    notes = api_get("/api/operator-notes", session_id=session_id, passenger_id=passenger_id, limit=20).get("items", [])
    st.dataframe(notes, use_container_width=True)

    st.markdown("**Conversation Summary**")
    if st.button("Generate Conversation Summary"):
        summary = api_post(
            "/api/conversation-summaries",
            {"session_id": session_id, "passenger_id": passenger_id},
        )
        st.success(summary.get("summary"))
    summaries = api_get("/api/conversation-summaries", session_id=session_id, passenger_id=passenger_id).get("items", [])
    st.dataframe(summaries, use_container_width=True)

    st.markdown("**Action Timeline**")
    timeline = api_get("/api/timeline", session_id=session_id, passenger_id=passenger_id, limit=50).get("items", [])
    st.dataframe(timeline, use_container_width=True)


def render_report() -> None:
    st.subheader("Customer Service Analytics")
    if st.button("Generate Analytics Report"):
        api_post("/api/analytics/report")
    try:
        summary = api_get("/api/analytics/summary")
        guardrails = summary.get("guardrails", {})
        cols = st.columns(5)
        cols[0].metric("Audit", guardrails.get("audit_total", 0))
        cols[1].metric("Executed", guardrails.get("executed", 0))
        cols[2].metric("Pending", guardrails.get("blocked_or_pending", 0))
        cols[3].metric("Human Review", guardrails.get("requires_human_review", 0))
        cols[4].metric("High Risk", guardrails.get("high_risk", 0))
        report = api_get("/api/analytics/report")
        st.markdown(report.get("content", ""))
    except Exception as exc:
        st.error(f"Failed to load analytics report from API: {exc}")


def main() -> None:
    st.set_page_config(page_title="Ctrip Assistant", layout="wide")
    render_status()
    render_kpis()
    tabs = st.tabs(["Customer Copilot", "Customer Context", "Policy Search", "Guarded Action", "Audit", "Analytics"])
    with tabs[0]:
        render_copilot()
    with tabs[1]:
        render_customer_context()
    with tabs[2]:
        render_policy_search()
    with tabs[3]:
        render_guarded_action()
    with tabs[4]:
        render_audit()
    with tabs[5]:
        render_report()


if __name__ == "__main__":
    main()
