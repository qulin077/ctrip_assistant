# End-to-End Scenario Evaluation

## 1. Evaluation Setup

- Eval cases: 30
- Embedding provider: `sentence_transformers:BAAI/bge-m3`
- Embedding model: `BAAI/bge-m3`
- Orchestrator: deterministic evaluator over policy retriever + guarded action core logic.

## 2. Metrics

| metric | value |
| --- | --- |
| scenario_pass_rate | 1.0 |
| answer_only_accuracy | 1.0 |
| needs_confirmation_accuracy | 1.0 |
| blocked_accuracy | 1.0 |
| executed_accuracy | 1.0 |
| handoff_accuracy | 1.0 |
| status_counts | {"answer_only": 4, "handoff": 8, "needs_confirmation": 9, "executed": 8, "blocked": 1} |

## 3. Accuracy By Intent

| intent | pass_rate |
| --- | --- |
| book_car_rental | 1.0 |
| book_hotel | 1.0 |
| cancel_car_rental | 1.0 |
| cancel_excursion | 1.0 |
| cancel_hotel | 1.0 |
| cancel_ticket | 1.0 |
| multi_intent | 1.0 |
| policy_question | 1.0 |
| ticket_change | 1.0 |
| unsupported_write | 1.0 |
| update_car_rental | 1.0 |

## 4. Error Analysis

- 当前 E2E 评测没有直接调用在线大模型，主要评估可重复的业务控制逻辑；这让结果稳定，但不能完全代表真实自然语言 planner。
- 本轮增加 query router 后，多意图场景会优先回答政策和风险，不再直接执行第二个写操作。
- 本轮增加 escalation policy 后，高风险咨询类问题可以稳定进入 handoff/service-ticket 逻辑。
- 后续仍需要接入真实 LangGraph tool call trace，验证在线模型 planner 是否与确定性 orchestrator 一致。

## 5. Failed Or Weak Cases

All E2E scenarios passed expected status, policy, action, ticket, and audit behavior.
