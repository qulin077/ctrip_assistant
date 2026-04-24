# 评测协议与结果解读

## 1. 测评效果在哪里看

本项目的评测效果主要看 `analysis/` 目录下这些报告：

| 评测层 | 报告路径 | 主要看什么 |
| --- | --- | --- |
| Retrieval Regression | `analysis/retriever_eval_v2.md` | 已知检索集是否稳定，Top3 是否仍能命中 |
| Retrieval Holdout | `analysis/retriever_eval_holdout.md` | 更自然问法下，检索 Top1 / Top3 是否还能稳住 |
| Retrieval Stress | `analysis/retriever_eval_stress.md` | 多意图、口语、跨域、高风险表达下的检索弱点 |
| Guardrail Regression | `analysis/guardrail_eval.md` | 写操作保护链路是否仍然全通过 |
| Guardrail Holdout | `analysis/guardrail_eval_holdout.md` | 更真实写操作输入下，确认、审计、工单是否稳定 |
| Guardrail Stress | `analysis/guardrail_eval_stress.md` | 高风险、非法动作、多意图写操作下是否会误执行 |
| E2E Regression | `analysis/e2e_eval.md` | 已知端到端场景是否仍然保持 1.0 |
| E2E Holdout | `analysis/e2e_eval_holdout.md` | 真实用户表达下，确定性 orchestrator 的泛化表现 |
| E2E Stress | `analysis/e2e_eval_stress.md` | 最难场景下，当前系统暴露出的 planner / routing 缺口 |
| LangGraph Trace | `analysis/langgraph_trace_eval.md` | 真实 LangGraph + LLM planner 的工具调用路径、顺序和半自动评分 |

当前一组关键结果如下：

| Split | Retrieval | Guardrail | E2E | 解读 |
| --- | --- | --- | --- | --- |
| Regression | Top1=0.8596, Top3=1.0 | Pass=1.0, Unsafe=0.0 | Pass=1.0 | 已知回归集稳定，说明已有功能没有被改坏 |
| Holdout | Top1=0.6875, Top3=0.8438 | Pass=0.6875, Unsafe=0.0 | Pass=0.5588 | 更真实问法下，系统开始暴露泛化问题 |
| Stress | Top1=0.6444, Top3=0.8444 | Pass=0.7045, Unsafe=0.0 | Pass=0.3250 | 多意图、跨域和高风险输入仍是主要短板 |

这组结果的重点不是“所有集都满分”，而是把不同问题分层暴露出来：

- Regression 证明系统没有回退。
- Holdout 更接近真实泛化效果。
- Stress 专门暴露复杂客服场景下的失败点。
- Guardrail 的 unsafe execution 始终为 0，是当前最重要的安全信号。

## 2. 三层评测集的定位

本项目不再只使用一套 controlled eval set，而是拆成三层：

| Split | 中文名称 | 作用 | 数据路径 | 如何解读 |
| --- | --- | --- | --- | --- |
| regression | 可控回归集 | 开发阶段防止已知能力退化 | `kb/metadata/retriever_eval_regression.jsonl`, `kb/metadata/guardrail_eval_regression.jsonl`, `kb/metadata/e2e_eval_regression.jsonl` | 高分说明旧能力稳定，不代表真实泛化 |
| holdout | 验证留出集 | 每轮改动后做更真实的泛化验证 | `kb/metadata/retriever_eval_holdout.jsonl`, `kb/metadata/guardrail_eval_holdout.jsonl`, `kb/metadata/e2e_eval_holdout.jsonl` | 比 regression 更可信，但不应该频繁手工调规则刷分 |
| stress | 盲测压力集 | 最终验证和面试展示，专门测试难例 | `kb/metadata/retriever_eval_stress.jsonl`, `kb/metadata/guardrail_eval_stress.jsonl`, `kb/metadata/e2e_eval_stress.jsonl` | 用来暴露多意图、冲突、高风险、跨域、噪声输入下的边界 |

## 3. 为什么 Regression 1.0 不等于真实泛化

Controlled Regression Suite 是稳定、可重复、确定性的。它和当前 evaluator、query router、guardrail 逻辑有较强的一致性，所以很适合做“改动后有没有破坏旧能力”的检查。

但是它不能证明真实泛化。真实客服用户会这样提问：

- 表达很口语：`我这票还能不能往后挪`
- 中英混合：`check in 之后还能不能换航班`
- 多意图：`退票，不行就改签，再看看发票`
- 跨业务域：`先取消酒店，再把租车顺延`
- 带有非法或高风险动作：`直接帮我改乘客姓名，不用查政策`

所以 regression 全是 1.0 只能说明旧路径稳定，不能说明系统已经能处理真实世界里的复杂输入。

## 4. Multi-Intent 是什么

`is_multi_intent=true` 表示一句话里包含多个目标、动作或业务域。

| 类型 | 示例 |
| --- | --- |
| 多个动作 | `退票，不行就改签` |
| 多个业务域 | `先取消酒店，再把租车顺延` |
| 动作加票据/支付 | `退票后还能补开发票吗` |
| 条件流程 | `如果改不了，就直接退掉` |

客服场景里 multi-intent 很重要，因为系统如果只识别第一个动作，可能会：

- 漏掉用户后续真实目标。
- 误执行高风险写操作。
- 没有先解释政策限制。
- 没有在跨域场景中升级人工。

当前 holdout + stress 已新增字段：

- `is_multi_intent`
- `sub_intents`
- `primary_intent`
- `secondary_intents`
- `cross_domain`

这些字段用于单独统计多意图和跨域 case 的表现。

## 5. 当前最可信的部分

当前最可信的是 guardrail 层，尤其是这些指标：

- 写操作是否经过 `guarded_action_structured`
- 未确认时是否阻断执行
- 明确确认后是否才允许执行
- 高风险 case 是否创建 service ticket
- 无政策依据或非法动作是否被 blocked
- unsafe execution rate 是否保持为 0
- audit log 是否稳定写入

从当前报告看，虽然 holdout/stress 的通过率不会满分，但 unsafe execution rate 仍然是 0。这说明系统即使在复杂输入下有泛化不足，也没有直接执行危险动作。

## 6. 当前不能过度解读的部分

E2E 评测目前仍然是 deterministic evaluator，不是完整在线 LLM planner 评测。它可以验证业务控制逻辑，但不完全等同于真实 LangGraph + LLM 的工具选择行为。

因此：

- E2E regression 1.0 不能代表真实模型 planner 一定稳定。
- E2E holdout/stress 低分说明当前 routing / planner 近似逻辑有短板。
- LangGraph trace 评测已经可以真实运行在线 LLM planner，并对工具路径做半自动评分；但它受在线模型延迟、temperature 和 tool-calling 稳定性影响，不应和 deterministic regression 直接等价比较。

`tools/evaluate_langgraph_trace.py` 已经记录这些信息：

- 用户输入
- assistant 是否调用 tool
- 调用了哪些 tool
- 是否先调用 `lookup_policy`
- 是否命中 guarded action
- 最终状态

当前 12 条 holdout trace 已经真实运行完成，结果为：

| 指标 | 结果 |
| --- | ---: |
| trace_pass_rate | 0.4167 |
| policy_lookup_pass_rate | 0.8333 |
| tool_selection_pass_rate | 0.5833 |
| guarded_order_pass_rate | 1.0000 |
| unsupported_safe_rate | 1.0000 |
| final_status_counts | completed=12 |

这说明真实 LLM 已经大多数情况下会查政策，但工具选择仍不稳定：有些写操作请求只查了政策或订单，没有调用最终 guarded action。好消息是没有观察到非法写操作或 guarded action 顺序错误。

## 7. 推荐运行方式

开发改动后先跑 regression：

```bash
python tools/evaluate_retriever_v2.py --split regression
python tools/evaluate_guardrails.py --split regression
python tools/evaluate_e2e.py --split regression
```

每轮策略、router、policy 或 prompt 改动后跑 holdout：

```bash
python tools/evaluate_retriever_v2.py --split holdout
python tools/evaluate_guardrails.py --split holdout
python tools/evaluate_e2e.py --split holdout
```

最终展示或复盘时跑 stress：

```bash
python tools/evaluate_retriever_v2.py --split stress
python tools/evaluate_guardrails.py --split stress
python tools/evaluate_e2e.py --split stress
```

需要看真实 LangGraph 路径时跑：

```bash
python tools/evaluate_langgraph_trace.py --limit 12
```

只想先生成 trace 报告结构时跑：

```bash
python tools/evaluate_langgraph_trace.py --limit 12 --dry-run
```
