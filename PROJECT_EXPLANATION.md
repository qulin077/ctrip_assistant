# ctrip_assistant 项目完整讲解

这个项目是一个“企业级旅行客服 Agent 原型”。它模拟旅行平台或航司客服系统，把旅客订单数据、政策知识库、RAG 检索、LangGraph 工具调用、写操作保护、审计日志、人工工单和数据分析串成一个完整客服工作台。

一句话概括：

```text
旅客问题
  -> 客服 Copilot / API
  -> LangGraph Assistant
  -> 政策 RAG + 业务工具
  -> 写操作 Guardrail
  -> SQLite 业务库
  -> 审计日志 / 人工工单 / 数据分析
```

它不是普通 FAQ 聊天机器人，而是一个能回答政策、查询订单、处理改签/取消/预订，并且对高风险写操作做确认和审计的客服智能体系统。

## 1. 业务背景

旅行客服场景里，用户经常问的问题包括：

- “我可以在起飞前多久改签？”
- “帮我查一下我的航班。”
- “我想取消机票，退款多久到账？”
- “酒店已经入住了还能退吗？”
- “租车开始后还能改日期吗？”
- “第三方平台买的票能不能让你直接取消？”

这些问题看起来像聊天，但背后其实有三类能力：

| 类型 | 例子 | 系统需要做什么 |
| --- | --- | --- |
| 政策咨询 | “电子机票能当发票吗？” | 查知识库，返回可信政策 |
| 业务查询 | “我的航班是什么？” | 查数据库，返回订单/航班/座位 |
| 状态变更 | “帮我取消机票” | 先查政策，再确认，再执行，再审计 |

这个项目的重点是第三类：写操作不能只靠大模型一句话决定，必须经过政策检索、确认、风险判断和审计。

## 2. 痛点

传统客服系统和普通大模型客服都会遇到这些问题：

1. **政策分散且难维护**
   原始 `order_faq.md` 是一个大 FAQ 文件，主题混杂，不适合直接做企业级 RAG。

2. **大模型容易越权承诺**
   比如用户问“活动开始后能全额退吗”，模型可能直接回答“可以”，但真实业务里需要人工复核。

3. **写操作风险高**
   改签、取消、预订会改变数据库状态，不能只靠 prompt 约束。

4. **客服过程不可审计**
   企业需要知道系统为什么执行、命中了什么政策、用户是否确认、是否创建人工工单。

5. **项目缺少可量化评测**
   面试或落地时，不能只说“能跑”，还要能说明检索准确率、guardrail 是否拦截危险操作、端到端场景通过率。

## 3. 针对人群

| 人群 | 使用页面/能力 | 目标 |
| --- | --- | --- |
| 旅客/普通用户 | 客服 Copilot、可选政策检索 | 自助咨询、查询订单、发起改签/取消 |
| 客服坐席 | 客服 Copilot、客户上下文、受保护操作、审计 | 辅助处理用户请求，减少查政策和查订单时间 |
| 运营/质检 | 审计、工单、数据分析 | 发现高风险场景，统计自动化率和人工升级率 |
| 数据科学/算法面试官 | 评测报告、analytics、RAG 指标 | 判断项目是否有数据意识、评测体系和业务闭环 |

实际产品形态可以拆成两端：

- **C 端用户界面**：只开放“客服 Copilot”，必要时开放“政策检索”。
- **客服工作台**：开放客户上下文、审计、工单、受保护操作和数据分析。

## 4. 数据集

项目使用两类数据：结构化业务数据库和非结构化政策知识库。

### 4.1 SQLite 业务数据库

本地数据库文件：

```text
travel_new.sqlite  # 运行时工作库
travel2.sqlite     # 备份库
```

核心航班订单链路：

```text
bookings -> tickets -> ticket_flights -> flights -> boarding_passes
```

重点表：

| 表 | 作用 |
| --- | --- |
| `bookings` | 订单预订记录 |
| `tickets` | 票号、乘客 ID、订单号 |
| `ticket_flights` | 票号和航段的关联 |
| `flights` | 航班号、机场、计划起降时间、状态 |
| `boarding_passes` | 登机牌和座位 |
| `hotels` | 酒店演示数据 |
| `car_rentals` | 租车演示数据 |
| `trip_recommendations` | 景点/行程推荐演示数据 |
| `airports_data` | 机场基础数据 |
| `aircrafts_data` | 机型基础数据 |
| `seats` | 座位基础数据 |

示例旅客 ID：

```text
3442 587242
```

这个 ID 可以查询到票号和航班信息，是前端默认演示用户。

### 4.2 政策知识库

原始 FAQ：

```text
order_faq.md
```

重构后的结构化知识库：

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

每个 Markdown 文件都有 YAML front matter，例如：

```yaml
policy_id: ticket_change_policy
service: flight
policy_type: change
language: zh-CN
source: order_faq.md
review_status: draft
requires_human_review: false
```

这样做的目的，是让 RAG 不只是向量相似度检索，还能按 `service`、`policy_type`、`requires_human_review` 等字段做业务过滤和风控判断。

## 5. 完整业务流程

### 5.1 咨询类问题

例子：

```text
用户：我可以在起飞前多久在线改签？
```

流程：

```text
前端客服 Copilot
  -> FastAPI /api/agent/chat
  -> LangGraph assistant
  -> lookup_policy
  -> retriever 读取 vector_store
  -> 返回 ticket_change_policy
  -> assistant 组织答案
```

如果只用“政策检索”页面，则不经过大模型：

```text
前端政策检索
  -> FastAPI /api/policy/search
  -> lookup_policy_structured
  -> vector_store
  -> 返回 policy card 和 chunk 文本
```

### 5.2 查询订单/航班

例子：

```text
用户：3442 587242，这是我的 ID，请帮我查询机票。
```

流程：

```text
LangGraph assistant
  -> fetch_user_flight_information
  -> tickets / ticket_flights / flights / boarding_passes
  -> 返回票号、航班号、出发到达机场、起降时间、座位
  -> assistant 总结给用户
```

代码里已经处理了一个真实问题：不是所有航段都有登机牌，所以 `boarding_passes` 使用 `LEFT JOIN`，避免因为没有座位号导致整张票查不出来。

### 5.3 写操作：改签/取消/预订

例子：

```text
用户：帮我取消票号 7240005432906569。
```

写操作保护流程：

```text
写操作请求
  -> action_guard
  -> policy lookup
  -> 判断 requires_human_review / risk_level / requires_confirmation
  -> 如果未确认：返回确认提示，不执行
  -> 如果已确认：调用原始业务工具
  -> 写 action_audit_logs
  -> 高风险时创建 service_tickets
```

也就是说，工具不是直接删数据库，而是先经过统一保护层。

受保护写工具共 11 个：

```text
update_ticket_to_new_flight
cancel_ticket
book_hotel
update_hotel
cancel_hotel
book_car_rental
update_car_rental
cancel_car_rental
book_excursion
update_excursion
cancel_excursion
```

## 6. 技术路径

### 6.1 LangGraph Agent

代码位置：

```text
graph_chat/workflow.py
graph_chat/assistant.py
graph_chat/state.py
tools/tools_handler.py
```

LangGraph 主流程：

```text
START -> assistant -> tools -> assistant
```

含义：

1. assistant 接收用户问题。
2. LLM 判断是否需要调用工具。
3. tools 节点执行工具。
4. 工具结果回到 assistant。
5. assistant 继续判断或生成最终回答。

### 6.2 LLM 接入

代码位置：

```text
graph_chat/assistant.py
project_config.py
.env.example
```

当前使用 OpenAI-compatible 方式接入 MiniMax：

```text
MINIMAX_API_KEY=...
MINIMAX_BASE_URL=https://api.minimaxi.com/v1
MINIMAX_MODEL=MiniMax-M2.7
```

这样 `ChatOpenAI` 可以通过兼容接口调用 MiniMax 模型。

### 6.3 RAG 知识库

代码位置：

```text
tools/build_kb_chunks.py
tools/build_vector_index.py
tools/retriever_vector.py
tools/policy_vector_store.py
tools/kb_embeddings.py
kb/raw/policy/
kb/processed/
kb/metadata/policy_index.jsonl
```

RAG 处理链路：

```text
政策 Markdown
  -> 解析 YAML metadata
  -> 按标题/段落/条款切 chunk
  -> kb/processed/chunks.jsonl
  -> BAAI/bge-m3 embedding
  -> kb/processed/vector_store/
  -> lookup_policy_structured
```

当前默认 embedding：

```text
sentence_transformers + BAAI/bge-m3
```

也保留了 `local_hash`，用于无模型环境下做离线 smoke test。

### 6.4 业务工具

代码位置：

```text
tools/flights_tools.py
tools/hotels_tools.py
tools/car_tools.py
tools/trip_tools.py
```

工具分两类：

| 类型 | 工具 |
| --- | --- |
| 只读工具 | 查航班、查酒店、查租车、查景点、查政策 |
| 写工具 | 改签、取消、预订、修改 |

写工具不会直接暴露给 assistant，而是通过 `tools/action_guard.py` 的 guarded 版本进入 LangGraph。

### 6.5 写操作保护

代码位置：

```text
tools/action_guard.py
tools/audit_store.py
```

保护层输出结构化结果：

```json
{
  "status": "needs_confirmation",
  "tool_name": "cancel_ticket",
  "policy_id": "refund_policy",
  "requires_human_review": true,
  "requires_confirmation": true,
  "executed": false,
  "confirmation_prompt": "我将为您取消票号 XXX，是否确认？",
  "service_ticket_created": true
}
```

这个结构化返回会被 API 和前端直接使用，避免前端靠字符串判断是否执行。

### 6.6 FastAPI 后端

代码位置：

```text
app/api.py
```

主要接口：

| 接口 | 作用 |
| --- | --- |
| `GET /health` | 健康检查 |
| `POST /api/agent/chat` | 调用 LangGraph 客服 Agent |
| `POST /api/policy/search` | 结构化政策检索 |
| `POST /api/actions/execute` | 手动执行受保护写操作 |
| `GET /api/passengers/{passenger_id}/profile` | 查询客户上下文 |
| `GET /api/audit/recent` | 查看审计日志 |
| `GET /api/service-tickets` | 查看人工工单 |
| `PATCH /api/service-tickets/{ticket_id}` | 更新工单状态 |
| `GET /api/analytics/summary` | 获取指标摘要 |
| `POST /api/analytics/report` | 生成分析报告 |

### 6.7 Streamlit 前端

代码位置：

```text
frontend/streamlit_app.py
```

页面含义：

| 页面 | 面向谁 | 作用 |
| --- | --- | --- |
| 客服 Copilot | 旅客/客服 | 多轮自然语言客服对话 |
| 客户上下文 | 客服坐席 | 查看旅客资料、航班、备注、摘要、时间线 |
| 政策检索 | 客服/用户自助 | 快速检索政策，不走大模型 |
| 受保护操作 | 客服/演示 | 手动测试写操作保护 |
| 审计 | 质检/运营 | 查看执行、阻断、确认、工单 |
| 数据分析 | 数据科学/运营 | 展示业务指标、自动化率、风险分布 |

## 7. 评测体系

代码位置：

```text
tools/evaluate_retriever_v2.py
tools/evaluate_guardrails.py
tools/evaluate_e2e.py
tools/generate_eval_sets.py
kb/metadata/retriever_eval_set_v2.jsonl
kb/metadata/guardrail_eval_set.jsonl
kb/metadata/e2e_eval_set.jsonl
```

报告位置：

```text
analysis/retriever_eval_v2.md
analysis/guardrail_eval.md
analysis/e2e_eval.md
analysis/eval_summary.md
analysis/embedding_comparison.md
```

三层评测：

| 层级 | 评估什么 |
| --- | --- |
| Retrieval Evaluation | policy 是否命中，top1/top3/MRR |
| Guardrail Evaluation | 是否查政策、是否要求确认、是否错误执行 |
| E2E Scenario Evaluation | 从自然语言输入到最终行为是否正确 |

这部分是项目面试时最重要的“数据科学感”：不只是做了一个 Agent，还用指标评价它。

## 8. 企业化价值

这个项目可以讲成四条主线：

1. **知识库治理**
   从单文件 FAQ 拆成结构化政策文档，带 metadata，可做 RAG 和风控。

2. **业务系统接入**
   使用 SQLite 模拟真实订单、票号、航段、酒店、租车和景点数据。

3. **风险控制**
   改签/取消/预订前强制查政策，必须确认，高风险创建工单。

4. **可观测与评测**
   审计日志记录所有关键操作，评测集衡量检索和端到端行为。

## 9. 当前仍可优化的地方

1. **多意图 query 路由**
   例如“退票不行就帮我改签”，当前容易只命中一个 policy，后续应拆成多个意图分别检索。

2. **人工工单闭环**
   当前能创建和更新工单状态，但还没有完整的人工作业流、SLA、分派和通知。

3. **数据库企业化**
   当前使用 SQLite，本地演示足够；生产环境应迁移到 MySQL/PostgreSQL，并拆出审计表、会话摘要表、工单表。

4. **权限与认证**
   当前 demo 没有登录、角色权限、数据脱敏。企业系统需要区分用户、客服、管理员。

5. **前端产品化**
   Streamlit 适合演示和面试；正式产品可以改成 React + FastAPI。

## 10. 运行方式

安装依赖：

```bash
pip install -r requirements.txt
```

配置环境变量：

```bash
cp .env.example .env
```

启动后端：

```bash
uvicorn app.api:app --reload --port 8000
```

启动前端：

```bash
streamlit run frontend/streamlit_app.py
```

命令行版本：

```bash
python -m graph_chat.cli
```

重新构建知识库：

```bash
python tools/build_kb_chunks.py
python tools/build_vector_index.py
```

运行评测：

```bash
python tools/evaluate_retriever_v2.py
python tools/evaluate_guardrails.py
python tools/evaluate_e2e.py
```

## 11. 面试讲述模板

可以这样讲：

> 我做了一个企业级旅行客服 Agent 原型。它不是简单聊天机器人，而是把结构化订单数据库、政策 RAG、LangGraph 工具调用、写操作保护、审计日志、人工工单和评测体系串起来。用户可以问政策、查机票，也可以发起取消或改签；系统在执行任何写操作前都会先检索政策、判断风险、要求用户确认，并把结果写入审计日志。为了证明系统可靠，我还设计了 retrieval、guardrail、end-to-end 三层评测，衡量 policy 命中率、危险操作拦截率和场景通过率。

项目亮点可以落在：

- 数据：结构化订单表 + 非结构化政策知识库。
- 算法：RAG、embedding、metadata filtering。
- Agent：LangGraph 工具调用流程。
- 风控：guarded action、confirmation、human review。
- 数据科学：评测集、指标、错误分析、业务分析报告。
