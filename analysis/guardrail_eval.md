# Guardrail Evaluation

## 1. Evaluation Setup

- Eval split: `regression`
- Eval set: `/Users/qulin/Desktop/AI/ai project/ctrip_assistant/kb/metadata/guardrail_eval_regression.jsonl`
- Eval cases: 40
- Embedding provider: `sentence_transformers:BAAI/bge-m3`
- Embedding model: `BAAI/bge-m3`
- Execution mode: guarded action logic with dry-run executor, audit/service ticket side effects enabled.

## 2. Metrics

| metric | value |
| --- | --- |
| scenario_pass_rate | 1.0 |
| confirmation_gate_hit_rate | 1.0 |
| unsafe_execution_rate | 0.0 |
| service_ticket_trigger_rate | 1.0 |
| audit_log_write_rate | 1.0 |
| status_counts | {"needs_confirmation": 16, "executed": 16, "blocked": 8} |
| multi_intent_cases | 0 |
| multi_intent_pass_rate | 0 |
| cross_domain_cases | 0 |
| cross_domain_pass_rate | 0 |

## 3. Pass Rate By Case Type

| case type | pass rate |
| --- | --- |
| confirmed_write | 1.0 |
| high_risk_confirmed | 1.0 |
| high_risk_unconfirmed | 1.0 |
| no_policy_match | 1.0 |
| unconfirmed_write | 1.0 |

## 4. Error Analysis

- 本轮将 service ticket 触发从 top3 chunk risk 中拆出，改为独立 escalation policy，减少普通预订/取消被过度升级。
- 无政策依据 case 仍会阻断并升级人工，这是面向企业系统的安全倾向；知识库覆盖不足会直接影响自动化率。
- 如果出现 unsafe execution，应优先检查确认词识别和写工具是否绕过 `guarded_action_structured`。

## 5. Failed Or Weak Cases

All guardrail cases passed expected status, execution, confirmation, and ticket behavior.
