# Guarded Actions Implementation Report

## 1. 新增与修改文件

新增文件：

- `tools/action_guard.py`
- `tools/audit_store.py`
- `tools/customer_analytics.py`
- `tools/test_guarded_actions.py`
- `analysis/guarded_actions_report.md`
- `analysis/customer_service_analytics.md`

修改文件：

- `graph_chat/assistant.py`
- `tools/retriever_vector.py`
- `tools/flights_tools.py`

本次没有重写 LangGraph 主流程。数据库侧只新增企业化辅助表，不改原有业务表结构。

## 2. 写操作保护层设计

本次采用最小侵入方案：不改 `ToolNode`，而是在原始写工具外包一层 guarded tool。

执行链路：

1. 模型调用写操作工具。
2. guarded tool 内部先调用 `lookup_policy_structured(...)`。
3. 记录政策命中结果：
   - `policy_id`
   - `requires_human_review`
   - `risk_level`
   - `requires_confirmation`
   - `allowed_action`
4. 如果没有命中政策，直接阻止执行。
5. 如果没有 `user_confirmation=确认`，只返回确认提示，不执行原始写工具。
6. 用户明确确认后，模型再次调用同一个写工具并带上 `user_confirmation`，guard 才执行原始写工具。
7. 每次决策写入 SQLite `action_audit_logs`，并保留 `logs/action_audit.jsonl` 作为本地调试旁路。
8. 如果命中高风险或人工复核场景，自动生成 `service_tickets`。

这样即使模型没有遵守 prompt 中“状态变更前先查政策”的规则，写操作工具本身也会强制先查政策。

## 3. 当前受保护工具

目前共有 11 个写工具受保护：

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

只读工具保持不变：

- `fetch_user_flight_information`
- `search_flights`
- `search_hotels`
- `search_car_rentals`
- `search_trip_recommendations`
- `lookup_policy`

## 4. 确认机制

每个受保护写工具新增 `user_confirmation` 参数。

当 `user_confirmation` 为空或不是明确肯定表达时：

- 工具会返回政策检查结果。
- 工具会返回确认问题。
- 工具不会执行数据库写操作。

当前识别的确认表达包括：

- `确认`
- `确定`
- `是`
- `是的`
- `好的`
- `可以`
- `同意`
- `继续`
- `执行`
- `yes`
- `ok`

示例：

```text
我将为您取消票号 XXX 的机票，是否确认？
如确认执行，请明确回复“确认”。
```

确认后模型需要再次调用对应写工具，并传入：

```text
user_confirmation="确认"
```

## 5. 审计记录

当前审计记录写入：

- `action_audit_logs`
- `logs/action_audit.jsonl`

每条记录包含：

- `created_at`
- `intent`
- `tool_name`
- `policy`
- `requires_confirmation`
- `user_confirmation`
- `confirmed`
- `executed`
- `blocked_reason`
- `result`

`logs/action_audit.jsonl` 已经被 `.gitignore` 中的 `logs/` 忽略，不会提交到仓库。

新增 `service_tickets` 表用于记录需要人工介入的场景：

- 无政策命中，无法安全执行写操作。
- 命中 `requires_human_review=true`。
- 命中 `risk_level=high`。

当前测试样例中，确认取消机票命中 `refund_policy` 的高风险/人工复核政策，因此会创建 1 条 open service ticket。

## 6. Retriever Tool 改进

`lookup_policy` 已从单参数升级为：

```python
lookup_policy(query: str, service: Optional[str] = None, policy_type: Optional[str] = None)
```

返回内容中新增：

- `requires_confirmation`
- `risk_level`
- `allowed_action`

这样模型可以更明确地按业务类型查询政策，guard 层也可以复用同一套结构化检索结果。

## 7. 修复项

测试确认取消机票时发现原始 `cancel_ticket` 查询了 `tickets.flight_id`，但 `tickets` 表不存在该字段。

已修复为查询：

```sql
SELECT ticket_no FROM tickets WHERE ticket_no = ? AND passenger_id = ?
```

该修改不改变数据库结构，只修正已有 SQL 字段错误。

## 8. 测试结果

测试脚本：

```bash
/Users/qulin/opt/anaconda3/envs/langchain_env/bin/python tools/test_guarded_actions.py
```

覆盖场景：

1. 用户要求改签，但未确认：命中政策，触发确认，不执行写操作。
2. 用户要求取消机票，并明确确认：命中政策，触发确认，执行取消。
3. 用户咨询酒店入住后取消：命中高风险/人工处理相关政策，触发谨慎回复。
4. 用户咨询退款：命中 `requires_human_review=true` 政策，触发谨慎回复。

同时保留原 retriever 评测：

```bash
python3 tools/evaluate_policy_retriever.py
```

当前结果：

- Top-1 accuracy: `1.0`
- Top-3 accuracy: `1.0`

## 9. 数据科学分析报告

新增脚本：

```bash
python tools/customer_analytics.py
```

输出：

```text
analysis/customer_service_analytics.md
```

报告包含：

- 核心业务表行数。
- 乘客、票号、航段、酒店、租车、景点服务覆盖。
- 票价条件和出发机场 Top 分布。
- 写操作审计记录数。
- 执行/阻断/确认/人工复核/高风险指标。
- service ticket 数量、优先级和状态。

这是为了让项目更适合数据科学岗位面试展示：不仅展示 agent 能力，也能展示业务数据分析、风险指标设计和客服运营指标。

## 10. 当前限制

- 确认状态没有持久写入 LangGraph state，只通过用户再次调用写工具时的 `user_confirmation` 参数判断。
- 还没有完整人工升级节点；当前是生成 `service_tickets`，但没有独立人工处理工作流。
- 模型是否能自然地在二次确认后补传 `user_confirmation`，仍依赖提示词和工具描述。
- 对复杂多轮确认、撤销确认、批量操作确认还没有支持。

## 11. 下一步建议

后续可以继续补充：

- `service_sessions`
- `conversation_summaries`

建议新增字段：

- `session_id`
- `passenger_id`
- `conversation_summary`
- `main_intent`
- `resolution_status`
- `tools_used`
- `policies_used`
- `created_at`

LangGraph 层面下一步可以新增：

- `confirm_action` 节点
- `human_escalation` 节点
- `summarize_conversation` 节点

这样可以把当前最小 guarded tool 方案升级成更标准的企业客服工作流。
