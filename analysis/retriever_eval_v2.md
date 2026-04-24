# Retriever Evaluation

## 1. Evaluation Setup

- Eval split: `regression`
- Eval set: `/Users/qulin/Desktop/AI/ai project/ctrip_assistant/kb/metadata/retriever_eval_regression.jsonl`
- Eval cases: 114
- Top K: 3
- Embedding provider: `sentence_transformers:BAAI/bge-m3`
- Embedding model: `BAAI/bge-m3`

## 2. Overall Metrics

| metric | value |
| --- | --- |
| top1_accuracy | 0.8596 |
| top3_accuracy | 1.0 |
| MRR | 0.9269 |
| filtered_top1_accuracy | 1.0 |

## 3. Breakdown By Query Type

| query_type | total | top1 | top3 | MRR | filtered_top1 |
| --- | --- | --- | --- | --- | --- |
| direct | 42 | 0.9048 | 1.0 | 0.9524 | 1.0 |
| multi_intent | 13 | 0.5385 | 1.0 | 0.7564 | 1.0 |
| noisy | 9 | 0.8889 | 1.0 | 0.9444 | 1.0 |
| paraphrase | 22 | 0.9091 | 1.0 | 0.9545 | 1.0 |
| risky | 28 | 0.8929 | 1.0 | 0.9405 | 1.0 |

## 4. Breakdown By Difficulty

| difficulty | total | top1 | top3 | MRR | filtered_top1 |
| --- | --- | --- | --- | --- | --- |
| easy | 24 | 0.9167 | 1.0 | 0.9583 | 1.0 |
| hard | 35 | 0.7429 | 1.0 | 0.8619 | 1.0 |
| medium | 55 | 0.9091 | 1.0 | 0.9545 | 1.0 |

## 5. Breakdown By Service

| service | total | top1 | top3 | MRR | filtered_top1 |
| --- | --- | --- | --- | --- | --- |
| booking | 12 | 0.9167 | 1.0 | 0.9583 | 1.0 |
| car_rental | 12 | 0.9167 | 1.0 | 0.9583 | 1.0 |
| excursion | 12 | 1.0 | 1.0 | 1.0 | 1.0 |
| flight | 54 | 0.8519 | 1.0 | 0.9259 | 1.0 |
| hotel | 12 | 0.8333 | 1.0 | 0.9028 | 1.0 |
| payment | 12 | 0.6667 | 1.0 | 0.8194 | 1.0 |

## 6. Multi-Intent And Cross-Domain

| subset | total | top1 | top3 | MRR | filtered_top1 |
| --- | --- | --- | --- | --- | --- |
| multi_intent | 13 | 0.5385 | 1.0 | 0.7564 | 1.0 |
| cross_domain | 0 | 0 | 0 | 0 | 0 |

## 7. Error Analysis

- Query router 已显著改善多意图和相邻 policy 的 Top1 表现，但多意图仍是最难类型。
- 仍然存在的相邻 policy 干扰主要发生在退款/支付/发票支付，以及酒店退款/泛化退款之间。
- `BAAI/bge-m3` 提升了语义召回；当前版本叠加 query router 与 broad fallback，在提高 Top1 的同时保留 Top3 候选召回。

## 8. Failed Or Weak Cases

All cases hit expected policy within top 3.

## 9. Top1 Misses For Review

| query | expected | top_policy | query_type | difficulty |
| --- | --- | --- | --- | --- |
| 我想退票，不行的话帮我改签到明天下午 | ticket_change_policy | refund_policy | multi_intent | hard |
| 团体票能不能自己在网上换航班？ | ticket_change_policy | booking_platform_policy | paraphrase | medium |
| 退款会退回原来的支付卡吗？ | refund_policy | payment_policy | direct | easy |
| 按发票支付的订单怎么退款？ | refund_policy | invoice_policy | direct | medium |
| 我退票后税费还能退吗？ | refund_policy | invoice_policy | direct | medium |
| 退到别的银行卡可以吗？ | refund_policy | payment_policy | risky | medium |
| 我先取消酒店再退机票，两个退款规则一样吗？ | refund_policy | hotel_policy | multi_intent | hard |
| 按发票支付是什么意思？ | payment_policy | invoice_policy | direct | easy |
| 我能不能用人民币付欧元票价？ | payment_policy | fare_rules | paraphrase | medium |
| 用公司发票付款后还能退到卡里吗？ | payment_policy | invoice_policy | multi_intent | hard |
| 信用卡扣款和发票支付能混用吗？ | payment_policy | invoice_policy | risky | hard |
| 我想改签并加行李，规则看哪部分？ | fare_rules | ticket_change_policy | multi_intent | hard |
| 我在 App 找不到酒店订单怎么办？ | booking_platform_policy | hotel_policy | multi_intent | hard |
| 我没去住，过了时间还能退钱吗？ | hotel_policy | refund_policy | noisy | hard |
| 我已经 check in 了能全额退吗？ | hotel_policy | refund_policy | risky | hard |
| 先看看酒店能不能取消，再帮我改租车日期 | car_rental_policy | hotel_policy | multi_intent | hard |
