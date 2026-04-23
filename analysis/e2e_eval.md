# End-to-End Scenario Evaluation

## 1. Evaluation Setup

- Eval cases: 30
- Embedding provider: `sentence_transformers:BAAI/bge-m3`
- Embedding model: `BAAI/bge-m3`
- Orchestrator: deterministic evaluator over policy retriever + guarded action core logic.

## 2. Metrics

| metric | value |
| --- | --- |
| scenario_pass_rate | 0.4333 |
| answer_only_accuracy | 0.5 |
| needs_confirmation_accuracy | 0.6667 |
| blocked_accuracy | 0.0 |
| executed_accuracy | 0.625 |
| handoff_accuracy | 0.0 |
| status_counts | {"answer_only": 2, "handoff": 6, "needs_confirmation": 13, "executed": 8, "blocked": 1} |

## 3. Accuracy By Intent

| intent | pass_rate |
| --- | --- |
| book_car_rental | 0.0 |
| book_hotel | 0.0 |
| cancel_car_rental | 0.0 |
| cancel_excursion | 1.0 |
| cancel_hotel | 1.0 |
| cancel_ticket | 1.0 |
| multi_intent | 0.3333 |
| policy_question | 0.2 |
| ticket_change | 1.0 |
| unsupported_write | 0.0 |
| update_car_rental | 1.0 |

## 4. Error Analysis

- 当前 E2E 评测没有直接调用在线大模型，主要评估可重复的业务控制逻辑；这让结果稳定，但不能完全代表真实自然语言 planner。
- 高风险咨询类问题最容易暴露短板：当前系统能给出谨慎状态，但纯咨询场景还没有真正落 service ticket。
- 多意图问题依赖轻量规则识别，后续需要用 LangGraph 返回的结构化 tool call 作为评测输入。

## 5. Failed Or Weak Cases

| case_id | input | expected_status | actual_status | expected_policy | actual_policy | expected_ticket | actual_ticket |
| --- | --- | --- | --- | --- | --- | --- | --- |
| E002 | 电子机票可以当发票吗？ | handoff | handoff | invoice_policy | invoice_policy | True | False |
| E003 | 酒店入住后还能取消吗？ | handoff | handoff | hotel_policy | hotel_policy | True | False |
| E004 | 租车开始后还能修改吗？ | handoff | needs_confirmation | car_rental_policy | car_rental_policy | True | True |
| E005 | 机票退了钱按什么币种退？ | handoff | handoff | refund_policy | refund_policy | True | False |
| E012 | 预订酒店 1 | needs_confirmation | needs_confirmation | hotel_policy | hotel_policy | False | True |
| E013 | 确认预订酒店 1 | executed | executed | hotel_policy | hotel_policy | False | True |
| E014 | 取消租车 1 | needs_confirmation | needs_confirmation | car_rental_policy | car_rental_policy | False | True |
| E015 | 确认取消租车 1 | executed | executed | car_rental_policy | car_rental_policy | False | True |
| E021 | 先看看酒店能不能取消，再帮我改租车日期 | answer_only | needs_confirmation | hotel_policy | car_rental_policy | True | True |
| E022 | 我想退票，不行的话帮我改签到明天下午 | answer_only | needs_confirmation | refund_policy | ticket_change_policy | True | False |
| E023 | 直接帮我改乘客姓名 | blocked | blocked | None | None | True | False |
| E024 | 第三方买的票让你直接取消可以吗？ | handoff | needs_confirmation | booking_platform_policy | refund_policy | True | True |
| E025 | 补开发票到底是 90 天还是 100 天？ | handoff | handoff | invoice_policy | invoice_policy | True | False |
| E026 | 活动开始后我迟到了能退款吗？ | handoff | handoff | excursion_policy | excursion_policy | True | False |
| E027 | 帮我预订租车 1 | needs_confirmation | needs_confirmation | car_rental_policy | car_rental_policy | False | True |
| E028 | 确认预订租车 1 | executed | executed | car_rental_policy | car_rental_policy | False | True |
| E030 | 公司报销要原件，系统里的电子票够不够？ | handoff | handoff | invoice_policy | invoice_policy | True | False |
