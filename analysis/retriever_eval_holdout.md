# Retriever Evaluation

## 1. Evaluation Setup

- Eval split: `holdout`
- Eval set: `/Users/qulin/Desktop/AI/ai project/ctrip_assistant/kb/metadata/retriever_eval_holdout.jsonl`
- Eval cases: 32
- Top K: 3
- Embedding provider: `sentence_transformers:BAAI/bge-m3`
- Embedding model: `BAAI/bge-m3`

## 2. Overall Metrics

| metric | value |
| --- | --- |
| top1_accuracy | 0.6875 |
| top3_accuracy | 0.8438 |
| MRR | 0.7604 |
| filtered_top1_accuracy | 1.0 |

## 3. Breakdown By Query Type

| query_type | total | top1 | top3 | MRR | filtered_top1 |
| --- | --- | --- | --- | --- | --- |
| ambiguous | 2 | 1.0 | 1.0 | 1.0 | 1.0 |
| mixed | 7 | 0.7143 | 0.8571 | 0.7619 | 1.0 |
| multi_intent | 11 | 0.4545 | 0.7273 | 0.5909 | 1.0 |
| paraphrase | 8 | 0.75 | 0.875 | 0.8125 | 1.0 |
| risky | 4 | 1.0 | 1.0 | 1.0 | 1.0 |

## 4. Breakdown By Difficulty

| difficulty | total | top1 | top3 | MRR | filtered_top1 |
| --- | --- | --- | --- | --- | --- |
| hard | 22 | 0.6364 | 0.8182 | 0.7197 | 1.0 |
| medium | 10 | 0.8 | 0.9 | 0.85 | 1.0 |

## 5. Breakdown By Service

| service | total | top1 | top3 | MRR | filtered_top1 |
| --- | --- | --- | --- | --- | --- |
| booking | 4 | 1.0 | 1.0 | 1.0 | 1.0 |
| car_rental | 4 | 0.75 | 1.0 | 0.875 | 1.0 |
| excursion | 4 | 0.75 | 0.75 | 0.75 | 1.0 |
| flight | 13 | 0.4615 | 0.7692 | 0.6026 | 1.0 |
| hotel | 4 | 1.0 | 1.0 | 1.0 | 1.0 |
| payment | 3 | 0.6667 | 0.6667 | 0.6667 | 1.0 |

## 6. Multi-Intent And Cross-Domain

| subset | total | top1 | top3 | MRR | filtered_top1 |
| --- | --- | --- | --- | --- | --- |
| multi_intent | 12 | 0.5 | 0.75 | 0.625 | 1.0 |
| cross_domain | 5 | 0.2 | 0.6 | 0.4 | 1.0 |

## 7. Error Analysis

- Query router 已显著改善多意图和相邻 policy 的 Top1 表现，但多意图仍是最难类型。
- 仍然存在的相邻 policy 干扰主要发生在退款/支付/发票支付，以及酒店退款/泛化退款之间。
- `BAAI/bge-m3` 提升了语义召回；当前版本叠加 query router 与 broad fallback，在提高 Top1 的同时保留 Top3 候选召回。

## 8. Failed Or Weak Cases

| query | expected | top_policy | top_section | snippet |
| --- | --- | --- | --- | --- |
| 儿童票退改是不是和成人一样 | fare_rules | refund_policy | 不同票价类型的退款差异 | 当前 FAQ 表明： - 灵活类票价通常有更高的改退灵活性。 - 非灵活经济舱票价取消时可能产生取消费用。 - 取消时间越接近出发日期，取消费用可能越高。 - 经济轻便票价中的第一件付费行李费... |
| extra baggage 改签以后还算吗 | fare_rules | ticket_change_policy | 改签后的订单和服务影响 | 改签后，以下信息或服务通常会保留： - 原预订参考号保持不变。 - 座位预订会包含在改签中。 - 特殊餐食会包含在改签中。 - 附加乘客信息 APIS 会包含在改签中。 - 通过瑞士航空购买的... |
| 我用企业卡付的，退票后钱退哪 | payment_policy | refund_policy | 发票支付场景下的退款 | 如果通过按发票支付方式购买机票，取消后的退款或账单调整取决于付款状态： - 如果发票已支付，退款通常通过银行转账处理。 - 如果付款期限未结束且发票未支付或仅部分支付，支付合作方可能发送新的个... |
| 我想把明天的行程和接车都往后挪 | excursion_policy | ticket_change_policy | 客服处理建议 | Agent 在执行改签操作前应先： 1. 查询当前乘客机票。 2. 查询改签政策。 3. 搜索候选航班。 4. 向用户明确新航班、时间和可能影响。 5. 获得用户确认后再执行改签。 涉及特殊服... |
| 不想去了，票和酒店都帮我看怎么少亏点 | refund_policy | hotel_policy | 超时未入住 | 如果旅客未按预订日期入住，酒店可能将订单标记为 no-show。 no-show 订单通常不支持自动退款。 如果旅客因航班延误、取消或紧急情况无法入住，应升级人工处理。 |

## 9. Top1 Misses For Review

| query | expected | top_policy | query_type | difficulty |
| --- | --- | --- | --- | --- |
| 我这张票今天还能改晚一点吗 | ticket_change_policy | fare_rules | paraphrase | medium |
| 机票改不了的话还能直接退吗 | refund_policy | ticket_change_policy | multi_intent | hard |
| 儿童票退改是不是和成人一样 | fare_rules | refund_policy | paraphrase | medium |
| extra baggage 改签以后还算吗 | fare_rules | ticket_change_policy | mixed | hard |
| 订单取消以后 invoice 还能开吗 | invoice_policy | excursion_policy | mixed | hard |
| 我用企业卡付的，退票后钱退哪 | payment_policy | refund_policy | multi_intent | hard |
| 帮我看看航班改签和酒店取消哪个先办 | ticket_change_policy | hotel_policy | multi_intent | hard |
| 如果租车延期，酒店也要多住一天，规则分别是什么 | car_rental_policy | hotel_policy | multi_intent | hard |
| 我想把明天的行程和接车都往后挪 | excursion_policy | ticket_change_policy | multi_intent | hard |
| 不想去了，票和酒店都帮我看怎么少亏点 | refund_policy | hotel_policy | multi_intent | hard |
