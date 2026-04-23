# Unified Guardrail Execution Report

## 1. 修改文件

本次修改：

- `tools/action_guard.py`
- `app/api.py`
- `frontend/streamlit_app.py`
- `tools/test_api.py`
- `analysis/unified_guardrail_report.md`

核对文件：

- `graph_chat/assistant.py`

`graph_chat/assistant.py` 已经绑定 `tools.action_guard` 中的 guarded 写工具，因此本次无需再替换工具绑定，只做路径核验。

## 2. 执行路径统一情况

现在三条执行路径统一如下：

```text
LangGraph assistant
  -> tools.action_guard guarded tool
  -> guarded_action_structured
  -> policy lookup / confirmation / audit / service ticket / original tool

FastAPI
  -> action_guard.execute_guarded_action_structured
  -> guarded_action_structured
  -> policy lookup / confirmation / audit / service ticket / original tool

Streamlit
  -> FastAPI /api/actions/execute
  -> action_guard.execute_guarded_action_structured
```

只读工具仍保留原始版本：

- `fetch_user_flight_information`
- `search_flights`
- `search_hotels`
- `search_car_rentals`
- `search_trip_recommendations`
- `lookup_policy`

写工具统一走 guarded path：

- `update_ticket_to_new_flight`
- `cancel_ticket`
- `book_hotel`
- `update_hotel`
- `cancel_hotel`
- `book_car_rental`
- `update_car_rental`
- `cancel_car_rental`
- `book_excursion`
- `update_excursion`
- `cancel_excursion`

## 3. 结构化返回 Schema

新增核心函数：

```python
guarded_action_structured(...) -> dict
execute_guarded_action_structured(tool_name, arguments, user_confirmation, config) -> dict
```

结构化结果字段：

```json
{
  "status": "blocked | needs_confirmation | executed",
  "tool_name": "cancel_ticket",
  "intent": "取消票号 XXX",
  "policy_summary": {
    "policy_id": "refund_policy",
    "policy_ids": ["refund_policy"],
    "section_title": "...",
    "requires_human_review": true,
    "risk_level": "high",
    "requires_confirmation": true,
    "allowed_action": ["cancel", "refund"],
    "match_count": 3
  },
  "confirmation_prompt": "我将为您取消票号 XXX 的机票，是否确认？",
  "result_text": "为避免误操作，本次写操作尚未执行。",
  "service_ticket_created": false,
  "service_ticket_id": null,
  "executed": false,
  "requires_confirmation": true,
  "requires_human_review": true,
  "policy_id": "refund_policy",
  "blocked_reason": "missing_confirmation"
}
```

## 4. 兼容性处理

LangChain tool 仍需要返回字符串，因此保留字符串包装：

```python
guarded_action(...) -> str
format_guarded_result(result: dict) -> str
```

各个 `@tool` 写工具继续返回可读文本，保证 LangGraph assistant 和现有命令行流程不需要重写。

API 层直接调用：

```python
execute_guarded_action_structured(...)
```

因此 `/api/actions/execute` 不再依赖字符串包含关系判断执行状态。

## 5. API 响应字段

`POST /api/actions/execute` 当前返回：

- `tool_name`
- `status`
- `executed`
- `requires_confirmation`
- `requires_human_review`
- `policy_id`
- `policy_summary`
- `result_text`
- `confirmation_prompt`
- `service_ticket_created`
- `service_ticket_id`
- `blocked_reason`
- `display_text`

其中 `display_text` 是给前端展示的人类可读文本；其他字段用于稳定程序判断。

## 6. 当前剩余未统一点

- LangGraph assistant 的工具调用仍通过 LangChain tool 字符串返回，这是兼容 LangGraph 的必要处理，不影响内部 guardrail 结构化执行。
- 多轮确认状态还没有进入 LangGraph state，仍通过再次调用写工具时传入 `user_confirmation` 实现。
- 人工工单已经入库，但还没有完整后台处理流转。
- 前端是 demo dashboard，没有登录鉴权。

## 7. 验证

建议运行：

```bash
python tools/test_api.py
python tools/test_guarded_actions.py
python tools/evaluate_policy_retriever.py
```

预期：

- API health 正常。
- `/api/actions/execute` 返回 `status=needs_confirmation`，未确认时 `executed=false`。
- guarded action 测试中 11 个写工具仍由 assistant 统一绑定。
