# 数据科学 / Agent 工程简历版本

## 项目标题

企业级旅行客服 Agent：RAG 政策检索、受保护工具调用、审计工单与多层评测体系

## 一句话项目简介

构建了一个面向旅行客服场景的企业级 Agent 原型，将结构化订单数据、政策知识库 RAG、LangGraph 工具调用、写操作风控、审计日志、人工工单和多层评测体系整合在一起，用于提升客服自动化、安全性、可解释性和可量化评估能力。

## 简历 Bullet 版本

**Enterprise Travel Customer Service Agent | LangGraph, RAG, BAAI/bge-m3, FastAPI, Streamlit, SQLite**

- 构建面向旅行客服场景的企业级 Agent 原型，整合航班/酒店/租车/景点业务数据、政策知识库、工具调用、风控确认、审计日志和客服质检指标，支持政策问答、机票查询、改签/取消/预订等流程。
- 将原始 FAQ 拆分治理为 9 份结构化政策文档，设计 `service`、`policy_type`、`requires_human_review`、`risk_level` 等 metadata，并构建 semantic chunking + 本地向量索引的 RAG pipeline。
- 使用 `sentence_transformers + BAAI/bge-m3` 替换离线 hash embedding，并引入 query router 与 filtered retrieval，在 114 条 regression 检索集上将 Top1 Accuracy 提升到 0.8596、Top3 Accuracy 提升到 1.0、MRR 提升到 0.9269。
- 为 11 个高风险写操作实现统一 guarded action 层，在执行改签、取消、预订前强制政策检索、用户确认和风险判断；在 regression 评测中实现 guardrail pass rate 1.0、unsafe execution rate 0.0、audit log write rate 1.0。
- 设计 action audit logs 与 service tickets，记录用户意图、命中政策、确认状态、执行结果和人工复核需求，支持客服质检、风控回放和人工升级。
- 将评测体系从单一 controlled regression suite 升级为 regression / validation holdout / blind stress 三层，新增 227 条更真实的 holdout + stress case，覆盖同义改写、口语噪声、中英混合、多意图、跨域和高风险冲突场景。
- 新增 LangGraph trace evaluation，真实运行 LLM planner 并记录工具调用路径；在 12 条 holdout trace 中观察到 completed=12、policy_lookup_pass_rate=0.8333、tool_selection_pass_rate=0.5833、guarded_order_pass_rate=1.0、unsupported_safe_rate=1.0，定位出真实 planner 未优先查政策或未调用最终写工具的问题。
- 基于 FastAPI 和 Streamlit 构建客服 Copilot 工作台，展示客户上下文、政策命中、操作状态、审计日志、人工工单和业务分析结果，支持端到端 demo 和数据科学面试展示。

## STAR 讲述版本

**Situation**

旅行客服需要处理改签、退款、发票、酒店、租车和景点行程等复杂政策。普通聊天机器人容易凭模型记忆回答，或者在取消/改签等写操作中缺少确认、审计和人工复核。

**Task**

目标是构建一个可解释、可审计、可评测的客服 Agent 原型，不只回答问题，还要能安全调用工具、处理写操作、记录审计日志，并用指标证明系统可靠。

**Action**

- 将 FAQ 拆分为 9 个 policy domain，并补充结构化 metadata。
- 构建 `BAAI/bge-m3` 向量检索和 query router，提升政策召回。
- 使用 LangGraph 实现 `assistant -> tools -> assistant` 的工具调用 workflow。
- 为 11 个写操作实现统一 guarded action，强制查政策、确认、审计和人工工单。
- 建立 regression / holdout / stress 三层评测体系，并新增真实 LangGraph trace evaluation。

**Result**

- Regression retrieval Top3 达到 1.0，MRR 达到 0.9269。
- Guardrail regression pass rate 达到 1.0，unsafe execution rate 保持 0.0。
- Holdout/stress 暴露出真实泛化短板，尤其是 multi-intent 和 cross-domain。
- LangGraph trace evaluation 发现真实 LLM planner 在部分政策咨询中没有优先 `lookup_policy`，为下一轮 prompt 和 tool schema 优化提供了可操作证据。

## 数据科学专家会喜欢的点

| 能力 | 项目体现 |
| --- | --- |
| 数据治理 | 原始 FAQ 拆分、policy metadata、chunk stats、数据审计 |
| 模型评估 | Top1/Top3/MRR、pass rate、unsafe execution、trace pass |
| 实验迭代 | local_hash baseline -> bge-m3 -> query router -> trace eval |
| 错误分析 | 多意图、相邻 policy、跨域、工具选择失败 |
| 风控建模 | confirmation gate、human review、service ticket、audit log |
| 系统落地 | LangGraph + FastAPI + Streamlit + SQLite |
| 可解释性 | policy_id、section_title、risk_level、trace_events |

## 面试 60 秒版本

我做了一个旅行客服 Agent 项目，不是普通问答 demo，而是把结构化订单数据、政策知识库 RAG、LangGraph 工具调用、写操作风控、审计日志、人工工单和多层评测串起来。  

我先把原始 FAQ 拆成 9 个结构化 policy，并用 `BAAI/bge-m3` 做本地向量检索；之后加了 query router，让 regression 检索 Top3 达到 1.0、MRR 达到 0.9269。  

在工具调用层，我把取消、改签、预订等 11 个写操作统一包进 guarded action，要求执行前必须查政策、用户确认、必要时转人工，并写 audit log。Guardrail regression pass rate 达到 1.0，unsafe execution rate 保持 0。  

最后我把评测从单一 regression 升级为 regression、holdout、stress 和真实 LangGraph trace。Trace eval 真实观察 LLM planner 的工具调用路径，发现部分 case 没有优先查政策或没有调用最终写工具，这给后续 prompt、tool schema 和 multi-intent splitter 提供了明确优化方向。

## 可量化结果汇总

| 模块 | 指标 | 结果 |
| --- | --- | ---: |
| Retrieval Regression | Top1 Accuracy | 0.8596 |
| Retrieval Regression | Top3 Accuracy | 1.0000 |
| Retrieval Regression | MRR | 0.9269 |
| Retrieval Holdout | Top1 Accuracy | 0.6875 |
| Retrieval Stress | Top1 Accuracy | 0.6444 |
| Guardrail Regression | Scenario Pass Rate | 1.0000 |
| Guardrail Regression | Unsafe Execution Rate | 0.0000 |
| Guardrail Holdout | Unsafe Execution Rate | 0.0000 |
| Guardrail Stress | Unsafe Execution Rate | 0.0000 |
| E2E Regression | Scenario Pass Rate | 1.0000 |
| E2E Holdout | Scenario Pass Rate | 0.5588 |
| E2E Stress | Scenario Pass Rate | 0.3250 |
| LangGraph Trace Holdout | Trace Pass Rate | 0.4167 |
| LangGraph Trace Holdout | Policy Lookup Pass Rate | 0.8333 |
| LangGraph Trace Holdout | Tool Selection Pass Rate | 0.5833 |
| LangGraph Trace Holdout | Guarded Order Pass Rate | 1.0000 |
| LangGraph Trace Holdout | Unsupported Safe Rate | 1.0000 |

## 后续提升方向

- 增加 multi-intent splitter，将复杂请求拆成多个可追踪子任务。
- 强化 policy-first planner prompt，让政策咨询和写操作前优先 `lookup_policy`。
- 优化写工具 schema，提高真实 LLM 调用 `cancel_ticket`、`update_ticket_to_new_flight` 等 guarded action 的概率。
- 将 LangGraph trace scoring 从工具路径扩展到最终回答内容、policy_id 命中和人工升级合理性。
- 用 trace failure 反向构建 planner regression set，形成模型/提示词迭代闭环。
