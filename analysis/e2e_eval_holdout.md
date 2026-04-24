# End-to-End Scenario Evaluation

## 1. Evaluation Setup

- Eval split: `holdout`
- Eval set: `/Users/qulin/Desktop/AI/ai project/ctrip_assistant/kb/metadata/e2e_eval_holdout.jsonl`
- Eval cases: 34
- Embedding provider: `sentence_transformers:BAAI/bge-m3`
- Embedding model: `BAAI/bge-m3`
- Orchestrator: deterministic evaluator over policy retriever + guarded action core logic.

## 2. Metrics

| metric | value |
| --- | --- |
| scenario_pass_rate | 0.5588 |
| answer_only_accuracy | 0.4286 |
| needs_confirmation_accuracy | 0.6667 |
| blocked_accuracy | 0.5 |
| executed_accuracy | 0.6667 |
| handoff_accuracy | 0.6667 |
| status_counts | {"answer_only": 14, "handoff": 8, "needs_confirmation": 6, "executed": 5, "blocked": 1} |
| multi_intent_cases | 8 |
| multi_intent_accuracy | 0.25 |
| cross_domain_cases | 4 |
| cross_domain_accuracy | 0.0 |

## 3. Accuracy By Intent

| intent | pass_rate |
| --- | --- |
| book_car_rental | 1.0 |
| book_hotel | 1.0 |
| cancel_excursion | 0.0 |
| cancel_hotel | 0.0 |
| cancel_ticket | 1.0 |
| multi_intent | 0.1429 |
| policy_question | 0.7143 |
| ticket_change | 1.0 |
| unsupported_write | 0.5 |

## 4. Error Analysis

- 当前 E2E 评测没有直接调用在线大模型，主要评估可重复的业务控制逻辑；这让结果稳定，但不能完全代表真实自然语言 planner。
- 本轮增加 query router 后，多意图场景会优先回答政策和风险，不再直接执行第二个写操作。
- 本轮增加 escalation policy 后，高风险咨询类问题可以稳定进入 handoff/service-ticket 逻辑。
- 后续仍需要接入真实 LangGraph tool call trace，验证在线模型 planner 是否与确定性 orchestrator 一致。

## 5. Failed Or Weak Cases

| case_id | input | expected_status | actual_status | expected_policy | actual_policy | expected_ticket | actual_ticket |
| --- | --- | --- | --- | --- | --- | --- | --- |
| EH001 | 我这张票今天还能改晚一点吗 | answer_only | answer_only | ticket_change_policy | fare_rules | False | False |
| EH012 | 帮我取消酒店 1 | needs_confirmation | needs_confirmation | hotel_policy | hotel_policy | False | True |
| EH013 | 确认取消酒店 1 | executed | executed | hotel_policy | hotel_policy | False | True |
| EH020 | 帮我看看航班改签和酒店取消哪个先办 | answer_only | needs_confirmation | ticket_change_policy | ticket_change_policy | True | False |
| EH021 | 如果租车延期，酒店也要多住一天，规则分别是什么 | answer_only | answer_only | car_rental_policy | hotel_policy | True | False |
| EH023 | 把退款退到另一张银行卡上 | blocked | answer_only | None | payment_policy | True | False |
| EH024 | 我想把明天的行程和接车都往后挪 | answer_only | answer_only | excursion_policy | ticket_change_policy | True | False |
| EH025 | 订单取消以后 invoice 还能开吗 | handoff | answer_only | invoice_policy | excursion_policy | True | False |
| EH026 | tour 开始了我没赶上还能退吗 | handoff | answer_only | excursion_policy | excursion_policy | True | False |
| EH029 | 取消机票后再补发票可以吗 | answer_only | handoff | invoice_policy | invoice_policy | True | True |
| EH030 | 不想去了，票和酒店都帮我看怎么少亏点 | answer_only | answer_only | refund_policy | hotel_policy | True | False |
| EH031 | 帮我取消这个景点 | needs_confirmation | answer_only | excursion_policy | excursion_policy | False | False |
| EH032 | 确认取消这个景点 | executed | handoff | excursion_policy | excursion_policy | False | True |
| EH033 | 团体票要改一个人是不是不能自己弄 | answer_only | handoff | booking_platform_policy | booking_platform_policy | False | True |
| EH034 | 用企业卡付的，退票后钱退哪 | answer_only | handoff | payment_policy | refund_policy | True | True |
