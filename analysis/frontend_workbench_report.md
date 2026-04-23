# Frontend Workbench Report

## 1. 新增交互能力

本次将 `frontend/streamlit_app.py` 从功能面板升级为更接近企业客服 Copilot 工作台的界面。

新增能力：

- `Customer Copilot` tab 使用后端 `/api/agent/chat`，由 LangGraph assistant 处理自然语言输入。
- 聊天历史保存在 Streamlit `session_state` 中，按 `passenger_id` 和 `thread_id` 维持会话。
- Copilot 响应中展示命中的 policy card、最近 audit log 和 action 状态。
- `Customer Context` tab 展示 passenger profile、票务与航班信息、operator notes、conversation summary 和 action timeline。
- `Audit` tab 支持 service ticket 状态更新。
- `Analytics` tab 通过 API 获取 summary 和 markdown report，前端不再直接读取本地分析文件。

## 2. Agent Chat 状态流转

当前 Copilot 不再使用前端规则型 `infer_intent` 判断意图，而是统一调用 FastAPI 后端：

```text
user input
  -> POST /api/agent/chat
  -> LangGraph assistant
  -> policy retriever / guarded tools
  -> audit log / service ticket
  -> frontend renders assistant output, policy cards, recent audit
```

对于写操作：

```text
user asks write action
  -> LangGraph selects guarded write tool
  -> guarded action performs policy lookup
  -> no confirmation: status=needs_confirmation, no write
  -> user confirms in same thread
  -> guarded action executes dry business tool path and writes audit
```

说明：多轮确认由 LangGraph thread memory 和 guarded tool 的 `user_confirmation` 参数共同承接，前端只负责保存对话上下文和展示结果。

## 3. Policy Card 与 Action Card

Policy card 展示：

- `policy_id`
- `title`
- `section_title`
- `requires_human_review`
- `requires_confirmation`
- `risk_level`
- `allowed_action`

Action/audit card 展示：

- `tool_name`
- `executed`
- `requires_confirmation`
- `risk_level`
- `policy_id`
- `blocked_reason`

这些字段来自后端结构化响应或 audit log，不再依赖前端字符串猜测。

## 4. Customer Context

新增的客服上下文页面面向坐席工作台：

- Passenger profile：展示旅客票务、航班、审计数量和工单数量。
- Action timeline：按时间合并 audit、service ticket、operator note。
- Operator notes：支持坐席新增和查看备注。
- Conversation summary：根据当前 session 的 audit log 生成轻量会话摘要。

这些能力为后续接入 `action_audit_logs`、`conversation_summaries`、质检和人工升级提供了产品入口。

## 5. API 解耦

前端主要通过 API 获取数据：

- `POST /api/agent/chat`
- `GET /api/passengers/{passenger_id}/profile`
- `GET /api/timeline`
- `POST /api/operator-notes`
- `POST /api/conversation-summaries`
- `PATCH /api/service-tickets/{ticket_id}`
- `GET /api/analytics/summary`
- `GET /api/analytics/report`

仍保留的本地耦合主要在后端：API 会读取 SQLite、生成 markdown report，并调用本地 LangGraph / retriever 代码。

## 6. 仍像 Demo 的地方

- 前端没有登录、角色权限和坐席队列。
- Copilot 的真实多轮工具选择依赖在线大模型，离线时不能完整演示。
- Conversation summary 目前基于 audit log 生成模板摘要，还不是 LLM 摘要。
- Service ticket 只支持状态更新，尚无负责人、优先级流转 SLA 和关闭原因。
- 前端没有细粒度展示 LangGraph tool calls，只展示 assistant output 和 audit 结果。

## 7. 后续建议

- 将 `/api/agent/chat` 的 LangGraph message/tool trace 结构化返回，用于前端 action timeline。
- 增加坐席登录、队列、工单负责人、SLA 和关闭原因。
- Conversation summary 改为 LLM 摘要，并落库为可审计版本。
- 增加 passenger risk profile、历史问题聚类和质检打分。
