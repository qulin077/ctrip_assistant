# Enterprise Agent Evaluation Summary

## 1. 评测目标

这个项目的评测不是只看“回答像不像”，而是把企业客服 Agent 拆成三层验证：

- Retrieval Evaluation：政策是否查准，尤其是多意图、口语化和相邻 policy。
- Guardrail Evaluation：写操作是否一定先查政策、先确认、再执行，并完整审计。
- End-to-End Scenario Evaluation：从自然语言输入到最终行为，是否正确回答、确认、执行、阻断或升级人工。

## 2. 评测集规模

| Eval Set | Path | Cases |
| --- | --- | ---: |
| Retrieval V2 | `kb/metadata/retriever_eval_set_v2.jsonl` | 114 |
| Guardrail | `kb/metadata/guardrail_eval_set.jsonl` | 40 |
| E2E | `kb/metadata/e2e_eval_set.jsonl` | 30 |

评测覆盖：

- 直接问法：如“电子机票可以当发票吗？”
- 同义改写：如“行程单能报销吗？”
- 多意图：如“我想退票，不行的话帮我改签到明天下午”
- 高风险/冲突：如“酒店已经入住了还能全额退吗？”
- 噪声和口语化：如“我这票还能不能往后挪一下”
- 无政策依据写操作：如“直接改乘客姓名”

## 3. 当前系统版本

当前默认向量索引：

```text
embedding_provider=sentence_transformers
embedding_model=BAAI/bge-m3
retrieval_strategy=query_router + filtered_top1 + broad_top3_fallback
guardrail_strategy=independent_escalation_policy
```

本轮新增两项关键改进：

1. **Query Router**
   根据用户问题推断 `service`、`policy_type` 和主 policy，用过滤检索抢 Top1，再用全局召回补足 Top3，减少相邻 policy 干扰。

2. **Escalation Policy**
   将 service ticket / handoff 判断从 top3 chunk risk 中拆出，单独根据政策、意图和高风险语言判断，减少普通预订被过度升级。

## 4. 当前评测结果

### Retrieval

| Metric | Value |
| --- | ---: |
| top1_accuracy | 0.8596 |
| top3_accuracy | 1.0 |
| MRR | 0.9269 |
| filtered_top1_accuracy | 1.0 |

解读：

- Query router 将 Top1 从 0.7982 提升到 0.8596。
- broad fallback 让 Top3 从 0.9386 提升到 1.0，保留了召回兜底。
- 多意图 Top1 从 0.3077 提升到 0.5385，但仍是最难类型。

### Guardrail

| Metric | Value |
| --- | ---: |
| scenario_pass_rate | 1.0 |
| confirmation_gate_hit_rate | 1.0 |
| unsafe_execution_rate | 0.0 |
| service_ticket_trigger_rate | 1.0 |
| audit_log_write_rate | 1.0 |

解读：

- 11 个受保护写工具均能稳定走“查政策 -> 确认 -> 执行/阻断 -> 审计”路径。
- 未确认直接执行率为 0。
- 独立 escalation policy 修复了普通酒店/租车/景点操作被 top3 高风险 chunk 误升级的问题。

### End-to-End

| Metric | Value |
| --- | ---: |
| scenario_pass_rate | 1.0 |
| answer_only_accuracy | 1.0 |
| needs_confirmation_accuracy | 1.0 |
| blocked_accuracy | 1.0 |
| executed_accuracy | 1.0 |
| handoff_accuracy | 1.0 |

解读：

- 多意图场景现在先回答政策和风险，不直接执行第二个写操作。
- 高风险咨询类问题可以稳定进入 handoff/service-ticket 逻辑。
- 需要注意：E2E 评测是 deterministic evaluator，不直接调用在线大模型，因此它证明的是业务控制层可靠，不完全等价于真实 LLM planner 表现。

## 5. 指标迭代对比

| Version | Key Change | Retrieval Top1 | Retrieval Top3 | MRR | Guardrail Pass | Unsafe Execution | E2E Pass |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| V0 | local_hash baseline | 0.7895 | 0.9123 | 0.8421 | - | - | - |
| V1 | BAAI/bge-m3 embedding | 0.7982 | 0.9386 | 0.8640 | 0.75 | 0.0 | 0.4333 |
| V2 | query router + escalation policy | 0.8596 | 1.0 | 0.9269 | 1.0 | 0.0 | 1.0 |

这个迭代过程体现了两个判断：

- 单纯换 embedding 有帮助，但不能解决多意图和流程控制。
- 企业级 Agent 的关键提升来自“模型 + 业务路由 + 风控策略 + 评测闭环”的组合。

## 6. 错误分析

### 当前仍最难的 query

多意图仍是 Top1 最难类型，例如：

- “我想退票，不行的话帮我改签到明天下午”
- “先看看酒店能不能取消，再帮我改租车日期”
- “我想改签并加行李，规则看哪部分？”

这些问题需要进一步做 multi-intent splitter，而不是只选一个主 policy。

### 相邻 policy 干扰

仍然存在的相邻干扰：

- `refund_policy` vs `payment_policy`：退款渠道、银行卡、支付方式相互重叠。
- `invoice_policy` vs `payment_policy`：发票支付和开票问题容易混淆。
- `hotel_policy` vs `refund_policy`：入住后退款、no-show 等问题容易被泛化到机票退款。

### 评测边界

- 当前 E2E 是可重复的业务 orchestrator 评测，不直接评估在线 LLM 的 tool planning。
- 下一步应记录真实 LangGraph tool call trace，对比模型选择工具是否符合 evaluator 预期。

## 7. 下一步优化方向

1. 增加 multi-intent splitter，将“退票不行就改签”拆成两个独立 policy lookup。
2. 将 escalation policy 配置化，支持不同业务线独立维护升级规则。
3. 接入真实 LangGraph trace evaluation，评估在线模型在复杂输入下的工具选择稳定性。
4. 增加人工客服处理结果回写，用真实工单结果反哺政策和评测集。

## 8. 面试讲述方式

这个项目最适合讲成一个持续迭代过程：

1. 先做 RAG 和工具调用，打通客服 Agent 主链路。
2. 发现单文件 FAQ 不稳定，于是做知识库治理和 metadata。
3. 发现 embedding baseline 不够稳，于是切换到 BAAI/bge-m3。
4. 发现多意图和相邻 policy 仍然影响 Top1，于是增加 query router。
5. 发现 top3 高风险 chunk 会导致过度升级，于是拆出独立 escalation policy。
6. 最后用三层评测证明改动有效，而不是只靠主观 demo。
