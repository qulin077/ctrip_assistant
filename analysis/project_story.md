# 项目逻辑梳理：企业级旅行客服 Agent

## 1. 业务痛点

旅行客服不是简单问答。真实客服场景里，用户会同时问政策、查订单、要求改签、取消、退款、开发票、订酒店、改租车或处理景点行程。难点主要有五类：

| 痛点 | 具体表现 | 风险 |
| --- | --- | --- |
| 政策分散 | 改签、退款、发票、支付、酒店、租车、景点规则分散在 FAQ 中 | 客服查找慢，回答不一致 |
| 用户表达自然且模糊 | `我这票还能不能往后挪`、`不飞了是退好还是改好` | 单纯关键词匹配容易误判 |
| 多意图输入多 | `退票，不行就改签，再看看发票` | 只处理第一个意图会漏掉用户真实目标 |
| 写操作有业务后果 | 改签、取消、预订会改变订单状态 | 未确认或政策不清时执行会造成投诉和资损 |
| 企业系统需要可审计 | 客服自动化必须能解释、回放、量化评测 | 只靠 prompt 难以满足风控和质检 |

## 2. 数据与知识库

项目使用本地旅行订单数据库模拟真实业务系统：

```text
bookings -> tickets -> ticket_flights -> flights -> boarding_passes
```

并扩展了三类非机票服务：

```text
hotels
car_rentals
trip_recommendations / excursion
```

政策知识库从原始 `order_faq.md` 拆分为 9 个结构化 policy：

```text
ticket_change_policy
refund_policy
invoice_policy
payment_policy
fare_rules
booking_platform_policy
hotel_policy
car_rental_policy
excursion_policy
```

每个 policy 带有 metadata，例如：

```text
service
policy_type
requires_confirmation
requires_human_review
risk_level
allowed_action
```

这些 metadata 是后续 query router、guardrail 和 service ticket 的基础。

## 3. 技术路径

整体链路如下：

```text
SQLite 业务数据 + Markdown 政策知识库
  -> policy metadata 结构化
  -> semantic chunking
  -> BAAI/bge-m3 embedding
  -> 本地 vector store
  -> LangGraph assistant -> tools -> assistant workflow
  -> lookup_policy / business tools
  -> guarded action layer
  -> audit logs / service tickets
  -> regression / holdout / stress / trace evaluation
```

核心技术组件：

| 模块 | 文件 | 作用 |
| --- | --- | --- |
| LangGraph workflow | `graph_chat/workflow.py` | 定义 `assistant -> tools -> assistant` 循环 |
| Assistant prompt + tools | `graph_chat/assistant.py` | 绑定 LLM 与可调用工具 |
| Policy retriever | `tools/retriever_vector.py` | 查政策，返回 policy 命中和风险 metadata |
| Guarded action | `tools/action_guard.py` | 写操作前查政策、要求确认、写审计、必要时建工单 |
| Audit / ticket | `tools/audit_store.py` | 管理审计日志和人工工单 |
| Deterministic eval | `tools/evaluate_*.py` | 稳定评估检索、护栏、端到端业务链路 |
| LangGraph trace eval | `tools/evaluate_langgraph_trace.py` | 真实运行 LLM planner，记录工具调用路径 |

## 4. Workflow 是什么

LangGraph 的执行流是：

```text
START
  -> assistant
  -> tools, if assistant emits tool_calls
  -> assistant
  -> tools, if more tool_calls
  -> assistant final answer
```

也就是：

```text
用户输入
  -> LLM 判断是否需要工具
  -> ToolNode 执行工具
  -> LLM 读取工具结果
  -> 继续调用工具或给出最终回答
```

这和 deterministic E2E 不同。deterministic E2E 是我们用规则模拟业务流程；LangGraph trace 是让真实 LLM 自己选择工具，因此更能发现 planner 问题。

## 5. 写操作为什么需要 Guardrail

这个项目里的“危险操作”不是物理世界危险，而是客服后台里的高风险写操作：

```text
update_ticket_to_new_flight
cancel_ticket
book_hotel / update_hotel / cancel_hotel
book_car_rental / update_car_rental / cancel_car_rental
book_excursion / update_excursion / cancel_excursion
```

这些动作会改变订单、预订、取消或改签状态。在真实企业系统里，它们可能影响库存、退款、客户行程和审计责任。

因此项目要求：

```text
写操作请求
  -> 先 lookup_policy
  -> 提取 risk metadata
  -> 未确认不执行
  -> 高风险或待人工确认则创建 service ticket
  -> 执行时写 action_audit_logs
```

当前最重要的安全指标是：

```text
unsafe_execution_rate = 0.0
```

这说明复杂输入下即使 planner 或 E2E 表现不完美，也没有发现未确认或无依据的危险写操作被执行。

## 6. 当前系统能解决什么问题

这个项目可以解决或模拟解决：

- 客服政策查找慢、答案不一致的问题。
- 改签、退款、发票、酒店、租车、景点等多业务政策的统一检索问题。
- 写操作前缺少确认和审计的问题。
- 高风险问题无法自动升级人工的问题。
- Agent demo 没有可量化评测的问题。
- 真实 LLM planner 工具调用不可观察的问题。

它不是要让 Agent 替代所有人工客服，而是把客服流程拆成：

```text
低风险咨询 -> 自动回答
普通写操作 -> 查政策 + 用户确认 + 审计
高风险 / 无政策依据 / 多意图复杂场景 -> 人工工单
```

## 7. 当前结论

当前系统最强的是：

- 政策检索 Top3 召回稳定。
- Guardrail 安全链路稳定。
- 未确认写操作不会误执行。
- 审计和工单链路完整。
- 已经能真实观察 LLM planner 的工具调用路径。

当前主要短板是：

- multi-intent 还没有真正拆解成多个子任务执行。
- 真实 LLM planner 有时先查用户订单，而不是先查政策。
- 写操作类 trace 中，LLM 经常停在查询/解释阶段，没有调用最终 guarded action。
- 在线 LLM 调用耗时较长，需要较大的 per-case timeout。

## 8. 未来提升方向

| 方向 | 目标 |
| --- | --- |
| Multi-intent splitter | 将 `退票，不行就改签，再补发票` 拆成多个可追踪子任务 |
| Planner policy-first prompt | 强化政策咨询和写操作前必须先 `lookup_policy` |
| Tool schema 优化 | 让 LLM 更容易调用 `cancel_ticket`、`update_ticket_to_new_flight` 等 guarded action |
| Trace 自动评分增强 | 从工具路径扩展到最终回答内容和 policy_id 是否一致 |
| Human review dashboard | 把 service ticket 和 trace failure 接到运营质检视图 |
| Evaluation data governance | 控制 holdout/stress 不被手工过拟合，形成长期评测资产 |
