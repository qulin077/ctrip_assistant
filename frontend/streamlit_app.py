from typing import Any, Optional

import requests
import streamlit as st


API_BASE_URL = st.sidebar.text_input("后端 API 地址", value="http://127.0.0.1:8000").rstrip("/")


def ensure_copilot_state() -> None:
    st.session_state.setdefault("copilot_messages", [])
    st.session_state.setdefault("copilot_thread_id", "streamlit-copilot")
    st.session_state.setdefault("copilot_passenger_id", "3442 587242")


def api_get(path: str, timeout: int = 20, **params) -> dict[str, Any]:
    response = requests.get(f"{API_BASE_URL}{path}", params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: Optional[dict[str, Any]] = None, timeout: int = 60) -> dict[str, Any]:
    response = requests.post(f"{API_BASE_URL}{path}", json=payload or {}, timeout=timeout)
    response.raise_for_status()
    return response.json()


def render_status() -> None:
    st.title("企业级旅行客服智能体工作台")
    st.caption("政策 RAG 检索、受保护写操作、审计日志与客服分析。")
    try:
        health = api_get("/health")
        st.success(f"后端已连接。受保护写操作数：{health['protected_actions']}")
    except Exception as exc:
        st.warning(f"后端无法连接：{exc}")
        st.info("运行：uvicorn app.api:app --reload --port 8000")


def render_kpis() -> None:
    try:
        summary = api_get("/api/analytics/summary")
    except Exception:
        return
    tables = summary["tables"]
    guardrails = summary["guardrails"]
    cols = st.columns(4)
    cols[0].metric("机票数", f"{tables.get('tickets', 0):,}")
    cols[1].metric("航段数", f"{tables.get('ticket_flights', 0):,}")
    cols[2].metric("审计日志", guardrails.get("audit_total", 0))
    cols[3].metric("服务工单", tables.get("service_tickets", 0))
    st.progress(
        0 if guardrails.get("audit_total", 0) == 0 else guardrails.get("executed", 0) / guardrails["audit_total"],
        text="受保护写操作执行率",
    )


def render_business_guide() -> None:
    with st.expander("这个项目在模拟什么业务？每个页面怎么用？", expanded=False):
        st.markdown(
            """
            **业务背景：** 这是一个旅行客服 Agent 原型，模拟客服坐席处理航班、酒店、租车、景点相关问题。
            它不是普通聊天机器人，而是把业务数据库、政策知识库、写操作保护、审计日志和工单串起来。

            - **客服 Copilot**：最像真实客服对话。适合问“我可以改签吗”“帮我取消机票”这类自然语言问题。它会调用 LangGraph 和大模型，所以可能比普通检索慢。
            - **客户上下文**：客服坐席看旅客资料、机票航班、历史备注、会话摘要和操作时间线。
            - **政策检索**：只查政策知识库，不走大模型。适合快速验证 RAG，比如“我可以在起飞前多久在线改签？”。
            - **受保护操作**：手动测试取消、改签、预订等写操作是否会先查政策、要求确认、写审计日志。
            - **审计**：查看系统做过什么、是否执行、为什么阻断、是否创建人工工单。
            - **数据分析**：面向数据科学面试，展示自动化率、阻断率、人工复核、高风险操作等指标。

            **小提示：** 简单政策问题先用“政策检索”页，速度最快；要演示完整客服 Agent 流程时再用“客服 Copilot”。
            """
        )


def render_policy_search() -> None:
    st.subheader("政策检索")
    with st.form("policy_search"):
        query = st.text_input("问题", value="酒店入住后还能取消吗？")
        col1, col2, col3 = st.columns(3)
        service = col1.selectbox("服务类型", ["", "flight", "hotel", "car_rental", "excursion", "booking"])
        policy_type = col2.selectbox(
            "政策类型",
            ["", "change", "refund", "invoice", "payment", "fare", "platform", "booking_policy"],
        )
        top_k = col3.number_input("返回数量", min_value=1, max_value=10, value=3)
        submitted = st.form_submit_button("检索政策")
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
        st.markdown(f"**政策：** `{policy.get('policy_id')}`")
        cols = st.columns(3)
        cols[0].metric("人工复核", "是" if policy.get("requires_human_review") else "否")
        cols[1].metric("需要确认", "是" if policy.get("requires_confirmation") else "否")
        cols[2].metric("风险等级", policy.get("risk_level") or "normal")
        st.caption(f"章节：{policy.get('section_title')}")
        allowed = policy.get("allowed_action") or []
        if allowed:
            st.caption("允许操作：" + ", ".join(allowed))


def render_action_card(result: dict[str, Any]) -> None:
    with st.container(border=True):
        st.markdown(f"**操作：** `{result.get('tool_name')}`")
        cols = st.columns(4)
        cols[0].metric("状态", result.get("status") or "-")
        cols[1].metric("已执行", "是" if result.get("executed") else "否")
        cols[2].metric("工单", "已创建" if result.get("service_ticket_created") else "否")
        cols[3].metric("政策", result.get("policy_id") or "-")
        if result.get("confirmation_prompt"):
            st.warning(result["confirmation_prompt"])
        st.text(result.get("display_text") or result.get("result_text") or "")


def render_audit_event_card(event: dict[str, Any]) -> None:
    with st.container(border=True):
        st.markdown(f"**审计事件：** `{event.get('tool_name')}`")
        cols = st.columns(4)
        cols[0].metric("已执行", "是" if event.get("executed") else "否")
        cols[1].metric("需要确认", "是" if event.get("requires_confirmation") else "否")
        cols[2].metric("风险等级", event.get("risk_level") or "normal")
        cols[3].metric("政策", event.get("policy_id") or "-")
        st.caption(event.get("intent") or "")
        if event.get("blocked_reason"):
            st.warning(f"阻断原因：{event['blocked_reason']}")


def render_copilot() -> None:
    ensure_copilot_state()
    st.subheader("客服 Copilot")
    st.caption("由 LangGraph 驱动的客服助手，可回答政策问题并处理受保护写操作。")
    st.info("这个页面会调用大模型，首次请求或复杂工具调用可能需要 30 秒以上；只想快速查政策时，请用“政策检索”页。")
    col1, col2 = st.columns(2)
    st.session_state.copilot_passenger_id = col1.text_input(
        "旅客 ID",
        value=st.session_state.copilot_passenger_id,
        key="copilot_passenger_input",
    )
    st.session_state.copilot_thread_id = col2.text_input(
        "会话 ID",
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

    prompt = st.chat_input("输入客服问题或操作请求")
    if not prompt:
        return

    st.session_state.copilot_messages.append({"role": "user", "content": prompt})
    assistant_item: dict[str, Any] = {"role": "assistant", "content": ""}

    try:
        with st.spinner("正在调用 LangGraph 客服助手，请稍等..."):
            result = api_post(
                "/api/agent/chat",
                {
                    "message": prompt,
                    "passenger_id": st.session_state.copilot_passenger_id,
                    "thread_id": st.session_state.copilot_thread_id,
                },
                timeout=120,
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
    st.subheader("受保护写操作演示")
    action = st.selectbox(
        "操作",
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
    passenger_id = st.text_input("旅客 ID", value="3442 587242")
    thread_id = st.text_input("会话 ID", value="streamlit-demo")
    user_confirmation = st.text_input("用户确认", value="")
    st.caption("留空确认内容可预览确认门，不会执行写操作。")

    args: dict[str, Any] = {}
    if action in {"cancel_ticket", "update_ticket_to_new_flight"}:
        args["ticket_no"] = st.text_input("票号", value="7240005432906569")
    if action == "update_ticket_to_new_flight":
        args["new_flight_id"] = st.number_input("新航班 ID", min_value=1, value=1)
    if action in {"book_hotel", "cancel_hotel"}:
        args["hotel_id"] = st.number_input("酒店 ID", min_value=1, value=1)
    if action in {"book_car_rental", "cancel_car_rental"}:
        args["rental_id"] = st.number_input("租车 ID", min_value=1, value=1)
    if action in {"book_excursion", "cancel_excursion"}:
        args["recommendation_id"] = st.number_input("景点/行程 ID", min_value=1, value=1)

    if st.button("执行受保护操作"):
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
            st.success("写操作已执行")
        else:
            st.warning("写操作未执行")
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
    st.subheader("审计日志与服务工单")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**最近审计日志**")
        try:
            rows = api_get("/api/audit/recent", limit=10).get("items", [])
            st.dataframe(rows, use_container_width=True)
        except Exception as exc:
            st.error(str(exc))
    with col2:
        st.markdown("**服务工单**")
        try:
            rows = api_get("/api/service-tickets", limit=10).get("items", [])
            st.dataframe(rows, use_container_width=True)
        except Exception as exc:
            st.error(str(exc))

    st.markdown("**更新服务工单**")
    c1, c2, c3 = st.columns([1, 1, 2])
    ticket_id = c1.number_input("工单 ID", min_value=1, value=1)
    new_status = c2.selectbox("状态", ["open", "in_progress", "resolved", "closed"])
    if c3.button("更新工单状态"):
        try:
            result = requests.patch(
                f"{API_BASE_URL}/api/service-tickets/{ticket_id}",
                json={"status": new_status},
                timeout=20,
            )
            result.raise_for_status()
            st.success(f"工单 {ticket_id} 已更新为 {new_status}")
        except Exception as exc:
            st.error(str(exc))


def render_customer_context() -> None:
    st.subheader("旅客画像、时间线与备注")
    col1, col2 = st.columns(2)
    passenger_id = col1.text_input("旅客 ID", value="3442 587242", key="profile_passenger")
    session_id = col2.text_input("会话 ID", value="streamlit-copilot", key="profile_session")

    profile = api_get(f"/api/passengers/{passenger_id}/profile")
    k1, k2, k3 = st.columns(3)
    k1.metric("机票数", len(profile.get("tickets", [])))
    k2.metric("审计日志", profile.get("audit_count", 0))
    k3.metric("服务工单", profile.get("service_ticket_count", 0))

    with st.expander("机票与航班", expanded=True):
        st.dataframe(profile.get("tickets", []), use_container_width=True)
        st.dataframe(profile.get("flights", []), use_container_width=True)

    st.markdown("**坐席备注**")
    note = st.text_area("新增备注")
    if st.button("保存坐席备注"):
        api_post(
            "/api/operator-notes",
            {
                "note": note,
                "author": "operator",
                "session_id": session_id,
                "passenger_id": passenger_id,
            },
        )
        st.success("备注已保存")
    notes = api_get("/api/operator-notes", session_id=session_id, passenger_id=passenger_id, limit=20).get("items", [])
    st.dataframe(notes, use_container_width=True)

    st.markdown("**会话摘要**")
    if st.button("生成会话摘要"):
        summary = api_post(
            "/api/conversation-summaries",
            {"session_id": session_id, "passenger_id": passenger_id},
        )
        st.success(summary.get("summary"))
    summaries = api_get("/api/conversation-summaries", session_id=session_id, passenger_id=passenger_id).get("items", [])
    st.dataframe(summaries, use_container_width=True)

    st.markdown("**操作时间线**")
    timeline = api_get("/api/timeline", session_id=session_id, passenger_id=passenger_id, limit=50).get("items", [])
    st.dataframe(timeline, use_container_width=True)


def render_report() -> None:
    st.subheader("客服分析")
    if st.button("生成分析报告"):
        api_post("/api/analytics/report")
    try:
        summary = api_get("/api/analytics/summary")
        guardrails = summary.get("guardrails", {})
        cols = st.columns(5)
        cols[0].metric("审计", guardrails.get("audit_total", 0))
        cols[1].metric("已执行", guardrails.get("executed", 0))
        cols[2].metric("待处理", guardrails.get("blocked_or_pending", 0))
        cols[3].metric("人工复核", guardrails.get("requires_human_review", 0))
        cols[4].metric("高风险", guardrails.get("high_risk", 0))
        report = api_get("/api/analytics/report")
        st.markdown(report.get("content", ""))
    except Exception as exc:
        st.error(f"无法从 API 加载分析报告：{exc}")


def main() -> None:
    st.set_page_config(page_title="携程旅行客服智能体", layout="wide")
    render_status()
    render_kpis()
    render_business_guide()
    tabs = st.tabs(["客服 Copilot", "客户上下文", "政策检索", "受保护操作", "审计", "数据分析"])
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
