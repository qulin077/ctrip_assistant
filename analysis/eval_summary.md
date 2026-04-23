# Enterprise Agent Evaluation Summary

## 1. 为什么之前的评测不够

早期评测主要验证“能不能检索到政策”和“guarded action 能不能跑通”，样本少、问题干净、场景单一。它适合开发期 smoke test，但不足以支撑企业级客服 Agent 的可信度展示。

这次评测升级后，把系统拆成三层：

- Retrieval Evaluation：评估 policy 命中质量，包括 top1、top3、MRR、filtered accuracy。
- Guardrail Evaluation：评估写操作保护层，包括确认门、错误执行率、service ticket、audit log。
- End-to-End Scenario Evaluation：从自然语言输入出发，评估咨询、确认、执行、阻断、人工升级的整体行为。

## 2. 新评测覆盖的难例

新增评测覆盖：

- 直接问法：如“电子机票可以当发票吗？”
- 同义改写：如“行程单能报销吗？”
- 多意图：如“我想退票，不行的话帮我改签到明天下午”
- 高风险/冲突：如“酒店已经入住了还能全额退吗？”
- 噪声和口语化：如“我这票还能不能往后挪一下”
- 无政策依据写操作：如“直接改乘客姓名，不用查政策”

## 3. 数据规模

| Eval Set | Path | Cases |
| --- | --- | ---: |
| Retrieval V2 | `kb/metadata/retriever_eval_set_v2.jsonl` | 114 |
| Guardrail | `kb/metadata/guardrail_eval_set.jsonl` | 40 |
| E2E | `kb/metadata/e2e_eval_set.jsonl` | 30 |

## 4. 当前评测结果

当前默认向量索引：

```text
embedding_provider=sentence_transformers
embedding_model=BAAI/bge-m3
```

### Retrieval

| Metric | Value |
| --- | ---: |
| top1_accuracy | 0.7982 |
| top3_accuracy | 0.9386 |
| MRR | 0.8640 |
| filtered_top1_accuracy | 1.0 |

解读：当前默认 embedding 已切换为 `sentence_transformers + BAAI/bge-m3`。当业务调用方能传入 `service` 和 `policy_type` 过滤条件时，检索非常稳定；纯自然语言无过滤时，多意图和相邻 policy 仍会拉低 top1。

与 `local_hash` 对比见 `analysis/embedding_comparison.md`。

### Guardrail

| Metric | Value |
| --- | ---: |
| scenario_pass_rate | 0.75 |
| confirmation_gate_hit_rate | 1.0 |
| unsafe_execution_rate | 0.0 |
| service_ticket_trigger_rate | 1.0 |
| audit_log_write_rate | 1.0 |

解读：写操作保护层的核心价值已经体现：未确认不执行、无政策依据阻断、审计完整落库。切换 bge-m3 后，召回的 chunk 更容易包含高风险/人工复核信号，因此 service ticket 触发比原先更保守。

### End-to-End

| Metric | Value |
| --- | ---: |
| scenario_pass_rate | 0.4333 |
| answer_only_accuracy | 0.5 |
| needs_confirmation_accuracy | 0.6667 |
| blocked_accuracy | 0.0 |
| executed_accuracy | 0.625 |
| handoff_accuracy | 0.0 |

解读：写操作主链路表现较好，但端到端仍是当前最弱层。原因不是 guarded action 本身，而是自然语言意图识别、纯咨询类人工升级、service ticket 自动创建策略还没有产品化。

## 5. 错误分析

### 哪类 query 最容易检索错？

多意图 query 最容易错。典型例子：

- “我想退票，不行的话帮我改签到明天下午”容易命中 `ticket_change_policy`，但期望主意图可能是 `refund_policy`。
- “先看看酒店能不能取消，再帮我改租车日期”容易在酒店和租车之间摇摆。

### 哪类问题最容易错误命中相邻 policy？

- 退款、支付、票价规则之间容易相互干扰，因为都包含“费用、退、支付、票价”等高频词。
- 酒店、租车、景点都使用 `booking_policy`，无过滤时容易错命中相邻扩展服务。
- 第三方/团体预订既出现在平台政策，也出现在改签或票价规则中。

### 哪类 guarded action 最容易错误执行或错误阻断？

当前 `unsafe_execution_rate=0.0`，没有发现未确认时错误执行。薄弱点是 service ticket 策略：

- `cancel_car_rental`、`update_excursion` 被系统判定为更高风险并创建工单，但评测预期认为可以只确认后执行。
- 这说明升级策略需要从 chunk-level risk 改为独立的 escalation policy。

### 哪些 case 表明 embedding / chunking / prompt 仍然不足？

- “行程单能报销吗？”误命中景点行程，说明 `行程` 这个词在中文里有歧义。
- “退到别的银行卡可以吗？”误命中支付政策，说明退款渠道和支付工具需要更明确的 chunk metadata。
- “我已经 check in 了能全额退吗？”误命中机票退款，说明酒店入住和航班值机的中英文混写需要更强语义模型。

## 6. 当前系统最弱的 3 个点

1. 自然语言意图识别还不够企业级，尤其是多意图、含糊表达和相邻业务域。
2. 纯咨询类高风险问题还没有统一创建 service ticket，handoff 仍偏回答策略而非流程控制。
3. 当前默认 `BAAI/bge-m3` 提升了召回，但也暴露了更保守的 risk chunk 命中和 service ticket 策略问题。

## 7. 下一步最值得优化的 3 个方向

1. 将 E2E evaluator 接入真实 LangGraph tool call trace，评估模型是否选择了正确工具，而不是只评估规则 orchestrator。
2. 在 `BAAI/bge-m3` 之上增加 query router 和多意图拆分，降低相邻 policy 干扰。
3. 新增独立 escalation policy，把 `requires_human_review`、`risk_level`、service ticket 创建、人工升级话术拆成可配置规则。

## 8. 面试讲述方式

这个项目不只展示“我会搭 RAG”，而是展示一个企业客服 Agent 的完整评估闭环：

- 知识库治理：从单文件 FAQ 拆成结构化 policy KB。
- 检索评测：用 114 条多类型 query 量化 top1/top3/MRR。
- 流程安全：用 40 条 guardrail case 验证写操作不会绕过确认。
- 端到端评测：用 30 条自然语言场景暴露真实业务短板。
- 审计闭环：写操作、工单、备注、摘要都有数据痕迹，可用于后续质检和运营分析。
