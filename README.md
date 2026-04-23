# Enterprise Travel Customer Service Agent

一个面向旅行客服场景的企业级智能体项目。项目基于 LangGraph 构建客服 Agent，结合 SQLite/MySQL 业务数据、结构化政策知识库、RAG 检索、工具调用、写操作保护、人工复核工单和数据分析报告。

这个项目不是简单聊天机器人，而是一个可解释、可审计、可评测的客服自动化系统原型。

## 项目亮点

- LangGraph agent workflow：assistant -> tools -> assistant 的客服执行流。
- 结构化业务数据：航班、票号、订单、登机牌、酒店、租车、景点推荐。
- RAG policy retrieval：将原始 FAQ 拆分为可维护政策知识库，并生成 chunks 和本地向量索引。
- Guarded write actions：改签、取消、预订等写操作执行前强制查政策并要求用户确认。
- Human review workflow：高风险或待人工确认政策自动生成 service ticket。
- Audit logging：写操作意图、命中政策、确认状态、执行结果写入审计表。
- Retriever evaluation：用 golden set 评估政策检索 top-k 命中率。
- Customer service analytics：输出业务数据、风险控制和工单指标，适合数据科学面试展示。

## 系统架构

```text
User
  -> LangGraph Assistant
  -> Policy Retriever / RAG
  -> Guarded Action Layer
  -> Business Tools
  -> SQLite Business Database
  -> Audit Logs / Service Tickets / Analytics
```

核心层次：

- `graph_chat/`：LangGraph 工作流、assistant 节点和命令行对话入口。
- `tools/`：航班、酒店、租车、景点工具，以及 RAG、guardrail、analytics 工具。
- `kb/raw/policy/`：拆分后的结构化政策知识库。
- `kb/processed/`：RAG chunks、向量索引和统计。
- `analysis/`：数据审计、知识库治理、RAG ingestion、guarded action 和业务分析报告。

## 数据集

项目依赖两个本地 SQLite 数据库：

- `travel2.sqlite`：原始备份数据库。
- `travel_new.sqlite`：运行时工作数据库。

这两个文件各约 109MB，超过 GitHub 普通文件 100MB 限制，因此默认不纳入 Git。运行项目前需要把它们放在项目根目录。

核心业务链路：

```text
bookings -> tickets -> ticket_flights -> flights -> boarding_passes
```

扩展服务链路：

```text
hotels
car_rentals
trip_recommendations
```

## 知识库与 RAG

原始知识库文件是 `order_faq.md`。当前项目已拆分为：

```text
kb/raw/policy/
  ticket_change_policy.md
  refund_policy.md
  invoice_policy.md
  payment_policy.md
  fare_rules.md
  booking_platform_policy.md
  hotel_policy.md
  car_rental_policy.md
  excursion_policy.md
```

知识库处理流程：

```text
policy markdown
  -> YAML metadata parsing
  -> semantic chunking
  -> kb/processed/chunks.jsonl
  -> vector_store
  -> lookup_policy / lookup_policy_structured
```

重新生成 chunk：

```bash
python tools/build_kb_chunks.py
```

重新构建向量索引：

```bash
python tools/build_vector_index.py
```

## 写操作保护

以下 11 个写工具受保护：

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

保护逻辑：

```text
write tool request
  -> policy lookup
  -> risk metadata extraction
  -> confirmation required
  -> optional service ticket
  -> execute original tool only after confirmation
  -> write action_audit_logs
```

如果用户没有明确回复“确认、是、好的、同意、继续”等肯定表达，写工具只返回确认提示，不执行数据库写操作。

## 审计与工单

项目会自动创建两张企业化辅助表：

```text
action_audit_logs
service_tickets
```

`action_audit_logs` 记录：

- 用户意图
- 工具名称
- 命中的 policy
- 是否需要人工复核
- 是否需要确认
- 用户是否确认
- 写操作是否执行
- 执行结果

`service_tickets` 记录：

- 高风险操作
- 待人工确认政策
- 无政策命中的阻断场景
- 后续人工客服处理状态

## 配置

复制环境变量示例：

```bash
cp .env.example .env
```

然后填写：

```text
MINIMAX_API_KEY=your_minimax_api_key
MINIMAX_BASE_URL=https://api.minimaxi.com/v1
MINIMAX_MODEL=MiniMax-M2.7
MINIMAX_REASONING_SPLIT=true

EMBEDDING_PROVIDER=local_hash
EMBEDDING_MODEL=BAAI/bge-m3
TAVILY_API_KEY=
```

`TAVILY_API_KEY` 是可选项；不填时不会启用网络搜索工具。

默认 embedding 使用 `local_hash`，不需要联网，适合本地快速验证。正式检索建议切换为：

```text
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=BAAI/bge-m3
```

切换后重新构建向量索引。

## 安装

推荐使用项目环境：

```bash
pip install -r requirements.txt
```

如果本地暂时无法安装 `sentence-transformers`，保留 `EMBEDDING_PROVIDER=local_hash` 也可以运行基础 RAG 和 guardrail 测试。

## 运行 Agent

推荐从项目根目录以模块方式运行：

```bash
python -m graph_chat.第一个流程图
```

程序会先用 `travel2.sqlite` 重置 `travel_new.sqlite`，再进入命令行对话。

退出命令：

```text
q
exit
quit
```

## 运行前后端 Demo

启动 FastAPI 后端：

```bash
uvicorn app.api:app --reload --port 8000
```

启动 Streamlit 前端：

```bash
streamlit run frontend/streamlit_app.py
```

前端包含：

- Policy Search：按 query / service / policy_type 检索政策。
- Guarded Action：演示受保护写操作，未确认时只返回确认提示。
- Audit：查看最近 action audit logs 和 service tickets。
- Analytics：展示客服业务分析报告。

后端主要接口：

```text
GET  /health
POST /api/policy/search
POST /api/actions/execute
GET  /api/audit/recent
GET  /api/service-tickets
GET  /api/analytics/summary
POST /api/analytics/report
```

## 测试与评估

政策检索冒烟测试：

```bash
python tools/test_policy_retriever.py
```

政策检索评测：

```bash
python tools/evaluate_policy_retriever.py
```

写操作保护测试：

```bash
python tools/test_guarded_actions.py
```

后端 API 测试：

```bash
python tools/test_api.py
```

生成业务分析报告：

```bash
python tools/customer_analytics.py
```

当前检索评测结果：

```text
Top-1 accuracy: 1.0
Top-3 accuracy: 1.0
```

## 数据科学分析

业务分析报告输出：

```text
analysis/customer_service_analytics.md
```

报告覆盖：

- 核心业务表行数。
- 乘客、票号、航段、酒店、租车、景点服务覆盖。
- 票价条件和机场分布。
- 写操作执行率、阻断率、确认率。
- 人工复核政策命中数。
- service ticket 数量、优先级和状态。

这些指标可以用于面试中讲：

- 客服自动化率。
- 高风险操作拦截率。
- 人工升级率。
- RAG policy 命中质量。
- 工具调用成功率。

## 导入 SQLite 到 MySQL

项目提供了一个导入脚本，会把两个本地 SQLite 数据库分别导入为两个 MySQL database：

```text
travel_new.sqlite -> ctrip_travel_new
travel2.sqlite    -> ctrip_travel_backup
```

运行：

```bash
python scripts/import_sqlite_to_mysql.py --password your_mysql_password
```

## 面试讲述方式

可以把项目总结为：

> I built an enterprise-style travel customer service agent that combines structured booking data, RAG-based policy retrieval, guarded tool execution, audit logging, and customer service analytics. The system does not directly execute risky write actions. It first retrieves relevant policies, checks risk metadata, asks for user confirmation, writes audit logs, and escalates high-risk cases into service tickets.

建议强调：

- 数据治理：从原始 FAQ 到结构化政策知识库。
- RAG 评测：golden set、top-k accuracy、metadata filtering。
- 业务建模：航班订单核心链路和扩展服务链路。
- 风险控制：写操作保护、确认机制、人工复核。
- 数据科学：审计日志、工单、自动化率和人工升级率分析。

## 项目说明

完整代码讲解见：

```text
PROJECT_EXPLANATION.md
```
