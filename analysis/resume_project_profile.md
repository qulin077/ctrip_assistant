# 数据科学简历项目稿：企业级旅行客服 Agent

## 项目名称

企业级旅行客服智能体系统：RAG 政策检索、受保护工具调用与端到端评测

## 一句话简介

构建了一个面向旅行客服场景的企业级 Agent 原型，整合结构化订单数据库、政策知识库 RAG、LangGraph 工具调用、写操作风控、审计日志、人工工单和三层评测体系，用于提升客服自动化、安全性和可解释性。

## 业务痛点

- 旅行客服政策复杂，改签、退款、发票、酒店、租车、景点等规则分散在 FAQ 中，人工查找成本高。
- 大模型客服容易在退款、取消、改签等高风险场景中做出越权承诺。
- 取消、改签、预订属于数据库写操作，不能只靠 prompt 约束，必须有确认和审计机制。
- 企业客服系统需要可量化评测，证明 RAG 命中率、风险拦截率和端到端流程可靠性。
- 普通 demo 往往只能聊天，缺少真实业务数据、工具调用、审计日志和面向运营的数据分析。

## 解决方案

- 将原始单文件 FAQ 重构为 9 份结构化政策文档，补充 YAML metadata，包括 `service`、`policy_type`、`requires_human_review` 等字段。
- 构建 RAG ingestion pipeline，将政策文档切分为语义 chunk，使用 `sentence_transformers + BAAI/bge-m3` 生成本地向量索引。
- 基于 LangGraph 实现 `assistant -> tools -> assistant` 工作流，支持政策问答、航班查询、酒店/租车/景点查询与写操作。
- 为 11 个写操作增加统一 guarded action 层，执行前强制查政策、判断风险、要求用户确认，并写入审计日志。
- 设计 action audit logs 和 service tickets，用于记录用户意图、命中政策、确认状态、执行结果和人工升级。
- 针对多意图、相邻 policy 和高风险咨询新增 query router 与独立 escalation policy，减少误召回和过度升级。
- 搭建 FastAPI + Streamlit 工作台，展示客服 Copilot、客户上下文、政策命中、操作状态、审计日志和业务分析指标。
- 建立三层评测体系：retrieval evaluation、guardrail evaluation、end-to-end scenario evaluation。

## 技术路径

```text
SQLite 业务数据 + Markdown 政策知识库
  -> 数据审计与知识库治理
  -> policy metadata + semantic chunking
  -> BAAI/bge-m3 embedding + 本地 vector store
  -> LangGraph agent tool calling
  -> guarded action layer
  -> audit logs / service tickets
  -> FastAPI backend + Streamlit workbench
  -> retrieval / guardrail / e2e evaluation
```

## 数据与业务建模

- 使用本地 SQLite 旅行数据库模拟真实订单系统，核心链路为：

```text
bookings -> tickets -> ticket_flights -> flights -> boarding_passes
```

- 扩展服务包括：

```text
hotels
car_rentals
trip_recommendations
```

- 政策知识库包括：

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

## 评测设计

### 1. Retrieval Evaluation

目标：评估用户问题是否能命中正确政策。

评测集规模：114 条。

覆盖类型：

- 直接问法：电子机票可以当发票吗？
- 同义改写：行程单能报销吗？
- 多意图：我想退票，不行的话帮我改签到明天下午。
- 高风险/冲突：酒店已经入住了还能全额退吗？
- 噪声口语：我这票还能不能往后挪一下？

指标：

| 指标 | 含义 |
| --- | --- |
| Top1 Accuracy | 第一条召回是否为正确 policy |
| Top3 Accuracy | 前三条中是否包含正确 policy |
| MRR | 正确结果排名越靠前得分越高 |
| Filtered Top1 Accuracy | 带 service / policy_type 过滤后的 Top1 准确率 |

当前结果：

| 指标 | 结果 |
| --- | ---: |
| Top1 Accuracy | 0.8596 |
| Top3 Accuracy | 1.0000 |
| MRR | 0.9269 |
| Filtered Top1 Accuracy | 1.0000 |

Embedding 对比：

| Embedding | Top1 | Top3 | MRR |
| --- | ---: | ---: | ---: |
| local_hash | 0.7895 | 0.9123 | 0.8421 |
| BAAI/bge-m3 | 0.7982 | 0.9386 | 0.8640 |
| BAAI/bge-m3 + query router | 0.8596 | 1.0000 | 0.9269 |

提升：

- 从 local_hash 到 bge-m3，Top3 提升 2.63 个百分点，MRR 提升 2.19 个百分点。
- 从 bge-m3 到 query router，Top1 提升 6.14 个百分点，Top3 提升到 1.0，MRR 提升到 0.9269。

结论：`BAAI/bge-m3` 改善语义召回；query router 进一步解决多意图和相邻 policy 的 Top1 稳定性问题。

### 2. Guardrail Evaluation

目标：评估写操作前的风控流程是否可靠。

评测集规模：40 条。

覆盖场景：

- 未确认时发起改签/取消/预订，应阻断。
- 已确认时执行写操作，应写审计日志。
- 高风险政策应创建 service ticket。
- 无政策依据的写操作应阻断。

指标：

| 指标 | 结果 | 含义 |
| --- | ---: | --- |
| scenario_pass_rate | 1.0 | 整体场景通过率 |
| confirmation_gate_hit_rate | 1.0 | 需要确认的场景全部触发确认门 |
| unsafe_execution_rate | 0.0 | 未发现未确认直接执行 |
| service_ticket_trigger_rate | 1.0 | 高风险/人工复核场景均触发工单 |
| audit_log_write_rate | 1.0 | 所有写操作路径均写审计 |

结论：guardrail 层核心安全目标达成，即未确认不执行、危险操作有审计、有工单。独立 escalation policy 修复了早期 service ticket 过度触发问题。

### 3. End-to-End Scenario Evaluation

目标：从自然语言输入出发，评估系统最终行为是否正确。

评测集规模：30 条。

覆盖场景：

- 纯咨询类问题。
- 写操作类问题。
- 高风险问题。
- 多意图问题。
- 含糊表达。

当前结果：

| 指标 | 结果 |
| --- | ---: |
| scenario_pass_rate | 1.0000 |
| answer_only_accuracy | 1.0000 |
| needs_confirmation_accuracy | 1.0000 |
| blocked_accuracy | 1.0000 |
| executed_accuracy | 1.0000 |
| handoff_accuracy | 1.0000 |

结论：在 deterministic evaluator 下，query router 和 escalation policy 已让咨询、确认、执行、阻断、人工升级五类场景都达到预期。下一步应接入真实 LangGraph tool call trace，评估在线模型 planner 的稳定性。

## 错误分析

- 多意图最容易错，例如“退票不行就改签”会在 `refund_policy` 和 `ticket_change_policy` 之间摇摆。
- 中文歧义会导致误命中，例如“行程单”可能被误召回到景点 `excursion_policy`。
- 酒店、租车、景点都属于扩展服务，policy_type 接近，未过滤时容易相互干扰。
- 当前 query router 已缓解上述问题，但复杂多意图仍建议继续做 multi-intent splitter，而不是只选择一个主 policy。

## 模型与系统迭代过程

| Version | Key Change | Retrieval Top1 | Retrieval Top3 | MRR | Guardrail Pass | E2E Pass |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| V0 | local_hash baseline | 0.7895 | 0.9123 | 0.8421 | - | - |
| V1 | BAAI/bge-m3 embedding | 0.7982 | 0.9386 | 0.8640 | 0.75 | 0.4333 |
| V2 | query router + escalation policy | 0.8596 | 1.0000 | 0.9269 | 1.0000 | 1.0000 |

这个迭代体现：先用 baseline 跑通链路，再用 embedding 提升语义召回，最后通过业务路由和升级策略解决企业 Agent 的流程问题。

## 简历项目经历版本

**企业级旅行客服 Agent 系统 | LangGraph, RAG, BAAI/bge-m3, FastAPI, Streamlit, SQLite**

- 构建面向旅行客服场景的企业级 Agent 原型，整合航班/酒店/租车/景点业务数据、政策知识库、工具调用、风控确认、审计日志和客服数据分析，支持政策问答、机票查询、改签/取消/预订等流程。
- 将原始单文件 FAQ 拆分治理为 9 份结构化政策文档，设计 `service`、`policy_type`、`requires_human_review` 等 metadata，并构建 semantic chunking + 本地向量索引的 RAG pipeline。
- 使用 `sentence_transformers + BAAI/bge-m3` 替换离线 hash embedding，并进一步引入 query router 与 broad fallback，在 114 条检索评测集上将 Top1 Accuracy 从 0.7895 提升到 0.8596、Top3 Accuracy 从 0.9123 提升到 1.0、MRR 从 0.8421 提升到 0.9269。
- 基于 LangGraph 实现 `assistant -> tools -> assistant` 多轮工具调用流程，并通过 FastAPI 封装为后端服务，Streamlit 构建客服 Copilot 工作台，展示政策命中、客户上下文、审计日志和操作结果。
- 为 11 个高风险写操作实现统一 guarded action 层，在执行改签、取消、预订前强制进行政策检索、用户确认和风险判断；通过独立 escalation policy 将 guardrail scenario pass rate 从 0.75 提升到 1.0，并保持 unsafe execution rate 0.0、audit log write rate 1.0。
- 设计三层评测体系，包括 Retrieval Evaluation、Guardrail Evaluation 和 End-to-End Scenario Evaluation，覆盖直接问法、同义改写、多意图、高风险和口语化 query；引入 query router 和 handoff 策略后，deterministic E2E scenario pass rate 从 0.4333 提升到 1.0。
- 构建 action audit logs 与 service tickets，用于记录用户意图、命中政策、确认状态、执行结果和人工复核需求，并生成客服自动化率、高风险拦截率、人工升级率等数据分析报告，支撑运营和质检场景。

## 面试讲述重点

1. 这个项目不是简单 RAG，而是“RAG + Tool Calling + Guardrail + Evaluation”的完整 Agent 系统。
2. 数据科学价值体现在：数据审计、知识库治理、评测集设计、指标拆解、错误分析和业务指标建模。
3. 最亮的指标不是 E2E pass rate，而是：
   - Retrieval Top3 = 1.0。
   - Retrieval MRR = 0.9269。
   - Filtered Top1 = 1.0。
   - Unsafe Execution Rate = 0.0。
   - Audit Log Write Rate = 1.0。
4. 这个项目的亮点是持续迭代：从 local_hash baseline，到 bge-m3，再到 query router 和 escalation policy，每一步都有指标验证。
