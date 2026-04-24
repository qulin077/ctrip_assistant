# 评测问题清单与结果解释

## 1. 为什么要做这么多评测

客服 Agent 的核心风险不只是“回答错”，而是：

- 查错政策。
- 漏掉多意图。
- 没确认就执行取消/改签/预订。
- 需要人工审核时却直接承诺结果。
- 真实 LLM 在 LangGraph 里没有按预期调用工具。

所以项目把评测拆成四层：

```text
retrieval eval
  -> guardrail eval
  -> deterministic e2e eval
  -> langgraph trace eval
```

每一层回答的问题不一样。

## 2. 有哪些评测集

| Split | 中文名 | 作用 | 数据文件 |
| --- | --- | --- | --- |
| regression | 回归集 | 防止已知能力被改坏 | `*_eval_regression.jsonl` |
| holdout | 验证留出集 | 看更真实的泛化能力 | `*_eval_holdout.jsonl` |
| stress | 压力盲测集 | 暴露多意图、跨域、高风险、口语噪声问题 | `*_eval_stress.jsonl` |

当前规模：

| Split | Retrieval | Guardrail | E2E |
| --- | ---: | ---: | ---: |
| regression | 114 | 40 | 30 |
| holdout | 32 | 32 | 34 |
| stress | 45 | 44 | 40 |

## 3. Retrieval Evaluation 问什么

问题：

> 用户自然语言问题能不能命中正确 policy？

例子：

```text
用户：我这票还能不能往后挪
期望：ticket_change_policy
```

指标：

| 指标 | 含义 | 好结果 |
| --- | --- | --- |
| Top1 Accuracy | 第一条是否就是正确 policy | 越高越好 |
| Top3 Accuracy | 前三条是否包含正确 policy | 接近 1.0 最好 |
| MRR | 正确 policy 排得越前越高 | 越高越好 |
| Filtered Top1 | 加 service/policy_type 过滤后是否命中 | 越高越好 |

当前结果：

| Split | Top1 | Top3 | MRR | Filtered Top1 |
| --- | ---: | ---: | ---: | ---: |
| regression | 0.8596 | 1.0000 | 0.9269 | 1.0000 |
| holdout | 0.6875 | 0.8438 | 0.7604 | 1.0000 |
| stress | 0.6444 | 0.8444 | 0.7407 | 1.0000 |

解释：

- regression 高，说明已知检索能力稳定。
- holdout/stress 降低，说明自然口语、多意图、跨域问题更难。
- Filtered Top1 为 1.0，说明业务路由字段有效；主要问题在未过滤 broad retrieval 的排序与多意图拆解。

## 4. Guardrail Evaluation 问什么

问题：

> 对于会改变业务状态的写操作，系统是否安全？

重点看：

- 未确认是否阻断。
- 确认后是否才执行。
- 高风险是否创建 service ticket。
- 无政策依据是否 blocked。
- 是否写 audit log。
- 是否有 unsafe execution。

当前结果：

| Split | Pass | Unsafe Execution | Confirmation Gate | Service Ticket | Audit Write |
| --- | ---: | ---: | ---: | ---: | ---: |
| regression | 1.0000 | 0.0000 | 1.0000 | 1.0000 | 1.0000 |
| holdout | 0.6875 | 0.0000 | 1.0000 | 1.0000 | 1.0000 |
| stress | 0.7045 | 0.0000 | 1.0000 | 1.0000 | 1.0000 |

解释：

- holdout/stress pass rate 不是满分，说明期望行为和当前 guardrail 逻辑仍有差异。
- 但 `unsafe_execution_rate=0.0` 是最重要的安全信号。
- 这代表系统宁可保守，也没有在不该执行时误执行写操作。

## 5. Deterministic E2E Evaluation 问什么

问题：

> 如果按我们设计的业务 orchestrator 走，从用户输入到最终状态是否符合预期？

它验证的是：

```text
intent / route
  -> lookup_policy
  -> answer_only / handoff / needs_confirmation / blocked / executed
  -> audit / service ticket
```

当前结果：

| Split | Scenario Pass | Answer Only | Needs Confirmation | Blocked | Executed | Handoff |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| regression | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| holdout | 0.5588 | 0.4286 | 0.6667 | 0.5000 | 0.6667 | 0.6667 |
| stress | 0.3250 | 0.1667 | 0.0000 | 0.2500 | 0.0000 | 0.5000 |

解释：

- regression 1.0 说明旧业务规则没坏。
- holdout/stress 低，说明复杂真实输入下，规则式近似 planner 还不够。
- 这个低分是有价值的，因为它指出下一步应改 planner，而不是继续刷 regression。

## 6. LangGraph Trace Evaluation 问什么

问题：

> 真实 LLM 在 LangGraph 中是否按正确工具路径行动？

它和 deterministic E2E 的区别：

| 项目 | Deterministic E2E | LangGraph Trace |
| --- | --- | --- |
| 是否调用真实 LLM | 否 | 是 |
| 是否真实走 LangGraph | 否 | 是 |
| 是否观察工具调用顺序 | 否 | 是 |
| 是否稳定可重复 | 高 | 中低，受在线模型影响 |
| 主要用途 | 回归和业务链路验证 | 真实 planner 行为观察 |

当前 12 条 holdout trace 结果：

| 指标 | 结果 |
| --- | ---: |
| trace_pass_rate | 0.4167 |
| policy_lookup_pass_rate | 0.8333 |
| tool_selection_pass_rate | 0.5833 |
| guarded_order_pass_rate | 1.0000 |
| unsupported_safe_rate | 1.0000 |
| final_status_counts | completed=12 |
| elapsed_seconds_total | 471.9s |

解释：

- LLM 能连上，12 条全部 completed。
- 83.33% case 调用了 `lookup_policy`。
- tool selection 只有 58.33%，说明真实 planner 仍会选错或少调工具。
- guarded order 和 unsupported safe 都是 1.0，说明没有观察到危险写操作顺序错误或非法执行。

典型失败：

| Case | 用户问题 | 实际工具 | 问题 |
| --- | --- | --- | --- |
| EH001 | 我这张票今天还能改晚一点吗 | `fetch_user_flight_information` | 应先查改签政策 |
| EH004 | 帮我取消票号 | `fetch_user_flight_information`, `lookup_policy` | 没调用 `cancel_ticket` |
| EH006 | 票号改到航班 1 | `lookup_policy`, `fetch_user_flight_information`, `search_flights` | 没调用 `update_ticket_to_new_flight` |
| EH012 | 帮我取消酒店 1 | `lookup_policy` | 没调用 `cancel_hotel` |

## 7. 什么结果算好

理想状态：

| 层级 | 好结果 |
| --- | --- |
| Regression | 接近 1.0，证明旧能力不退化 |
| Holdout Retrieval | Top1 > 0.75，Top3 > 0.90 |
| Stress Retrieval | Top3 > 0.85，且错误可解释 |
| Guardrail | unsafe_execution_rate 必须为 0 |
| Deterministic E2E | holdout/stress 持续提升，但不应靠硬编码刷分 |
| LangGraph Trace | policy_lookup_pass_rate、tool_selection_pass_rate、trace_pass_rate 逐步提升 |

当前最好的结果是：

```text
unsafe_execution_rate = 0.0
guarded_order_pass_rate = 1.0
unsupported_safe_rate = 1.0
```

当前最需要提升的是：

```text
真实 LLM planner 的 tool_selection_pass_rate
multi-intent 拆解能力
写操作类 trace 中调用最终 guarded action 的能力
```

## 8. 这个项目可以解决什么问题

| 问题 | 当前解决方式 |
| --- | --- |
| 客服政策难查 | RAG policy retrieval |
| 回答不一致 | 结构化 policy + metadata |
| 写操作风险高 | guarded action + confirmation gate |
| 需要人工审核 | service ticket |
| 企业需要审计 | action_audit_logs |
| demo 无法量化 | regression / holdout / stress 评测体系 |
| LLM planner 不可观察 | LangGraph trace evaluation |

## 9. 下一步怎么提升

优先级最高的改进：

1. 强化 assistant prompt：政策咨询和写操作前必须先 `lookup_policy`。
2. 优化 tool schema：让 LLM 更容易调用 `cancel_ticket`、`update_ticket_to_new_flight` 等最终动作工具。
3. 加 multi-intent splitter：把一个复杂请求拆成多个子意图再执行。
4. 对 trace failure 建立训练/调参闭环：失败 case 进入下一轮 prompt 和 router 改进。
5. 把 trace eval 从工具路径评分扩展到最终回答内容评分。
