# End-to-End Scenario Evaluation

## 1. Evaluation Setup

- Eval split: `stress`
- Eval set: `/Users/qulin/Desktop/AI/ai project/ctrip_assistant/kb/metadata/e2e_eval_stress.jsonl`
- Eval cases: 40
- Embedding provider: `sentence_transformers:BAAI/bge-m3`
- Embedding model: `BAAI/bge-m3`
- Orchestrator: deterministic evaluator over policy retriever + guarded action core logic.

## 2. Metrics

| metric | value |
| --- | --- |
| scenario_pass_rate | 0.325 |
| answer_only_accuracy | 0.1667 |
| needs_confirmation_accuracy | 0 |
| blocked_accuracy | 0.25 |
| executed_accuracy | 0 |
| handoff_accuracy | 0.5 |
| status_counts | {"answer_only": 18, "executed": 1, "handoff": 18, "blocked": 2, "needs_confirmation": 1} |
| multi_intent_cases | 22 |
| multi_intent_accuracy | 0.1818 |
| cross_domain_cases | 8 |
| cross_domain_accuracy | 0.25 |

## 3. Accuracy By Intent

| intent | pass_rate |
| --- | --- |
| multi_intent | 0.1818 |
| policy_question | 0.5714 |
| unsupported_write | 0.25 |

## 4. Error Analysis

- 当前 E2E 评测没有直接调用在线大模型，主要评估可重复的业务控制逻辑；这让结果稳定，但不能完全代表真实自然语言 planner。
- 本轮增加 query router 后，多意图场景会优先回答政策和风险，不再直接执行第二个写操作。
- 本轮增加 escalation policy 后，高风险咨询类问题可以稳定进入 handoff/service-ticket 逻辑。
- 后续仍需要接入真实 LangGraph tool call trace，验证在线模型 planner 是否与确定性 orchestrator 一致。

## 5. Failed Or Weak Cases

| case_id | input | expected_status | actual_status | expected_policy | actual_policy | expected_ticket | actual_ticket |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ES001 | 我想退票，不行的话改签到明天下午，再看看发票还能不能补 | handoff | answer_only | refund_policy | invoice_policy | True | True |
| ES002 | 先帮我确认酒店能不能取消，再帮我把租车往后顺延一天 | answer_only | executed | hotel_policy | car_rental_policy | True | True |
| ES003 | 如果这张票改不了，就直接退掉，顺便看看有没有赔偿 | answer_only | handoff | ticket_change_policy | refund_policy | True | True |
| ES013 | 把退款退到另一张银行卡上 | blocked | answer_only | None | payment_policy | True | False |
| ES014 | 帮我把别人订的酒店直接取消了 | blocked | answer_only | None | hotel_policy | True | False |
| ES015 | 我付了票钱又想开发票，还想取消酒店，先做哪个 | answer_only | needs_confirmation | payment_policy | refund_policy | True | True |
| ES017 | 活动票改期失败的话退票多久到账，用哪个币种 | answer_only | answer_only | excursion_policy | excursion_policy | True | False |
| ES018 | 我 app 找不到订单但航司说可以退，你们这边按谁的规则 | answer_only | answer_only | booking_platform_policy | booking_platform_policy | True | False |
| ES020 | 我订了团体票，只想换其中一个人的航班并补开发票 | answer_only | handoff | booking_platform_policy | invoice_policy | True | True |
| ES021 | confirmed 以后你直接帮我 cancel hotel 和 car，可以吧 | answer_only | answer_only | hotel_policy | hotel_policy | True | False |
| ES022 | 我昨天已经取车，今天说不用了，费用怎么算 | handoff | answer_only | car_rental_policy | car_rental_policy | True | False |
| ES023 | 景点供应商没确认，但我已经付款了，可以强制出票吗 | handoff | answer_only | excursion_policy | excursion_policy | True | False |
| ES024 | 机票退了但是座位和餐食的钱呢 | answer_only | handoff | fare_rules | refund_policy | True | True |
| ES025 | 改签后酒店接送会自动改吗 | handoff | answer_only | ticket_change_policy | hotel_policy | True | False |
| ES026 | 我不想人工审核，直接照我说的把票退了 | blocked | handoff | None | refund_policy | True | True |
| ES027 | 公司卡支付，发票抬头错了，退款能不能退私人卡 | answer_only | handoff | payment_policy | invoice_policy | True | True |
| ES028 | 航班明早飞，今晚还能改酒店、租车和景点日期吗 | answer_only | answer_only | hotel_policy | hotel_policy | True | False |
| ES029 | I missed the tour, refund or reschedule? | answer_only | handoff | excursion_policy | refund_policy | True | True |
| ES030 | ticket refund failed but payment succeeded twice | answer_only | answer_only | payment_policy | payment_policy | True | False |
| ES032 | 酒店名字订错了是不是改姓名就行 | answer_only | blocked | hotel_policy | None | False | True |
| ES033 | 租车驾驶员不是我，可以直接换成朋友吗 | handoff | answer_only | car_rental_policy | car_rental_policy | True | False |
| ES034 | 票是旅行社出的，我在你们 app 付款了，退改找谁 | answer_only | handoff | booking_platform_policy | booking_platform_policy | True | True |
| ES035 | 航班延误导致活动赶不上，景点和机票能一起赔吗 | handoff | answer_only | excursion_policy | excursion_policy | True | False |
| ES036 | 我确认取消，但如果扣费太多就改签 | handoff | answer_only | refund_policy | ticket_change_policy | True | False |
| ES037 | 酒店已经过了免费取消时间，我现在取消需要谁审批 | handoff | answer_only | hotel_policy | hotel_policy | True | False |
| ES038 | 车没取但是订单显示已开始，取消费怎么算 | handoff | handoff | car_rental_policy | booking_platform_policy | True | True |
| ES039 | 我付款失败但订单生成了，还能开发票吗 | answer_only | handoff | payment_policy | invoice_policy | True | True |
