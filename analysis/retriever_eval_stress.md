# Retriever Evaluation

## 1. Evaluation Setup

- Eval split: `stress`
- Eval set: `/Users/qulin/Desktop/AI/ai project/ctrip_assistant/kb/metadata/retriever_eval_stress.jsonl`
- Eval cases: 45
- Top K: 3
- Embedding provider: `sentence_transformers:BAAI/bge-m3`
- Embedding model: `BAAI/bge-m3`

## 2. Overall Metrics

| metric | value |
| --- | --- |
| top1_accuracy | 0.6444 |
| top3_accuracy | 0.8444 |
| MRR | 0.7407 |
| filtered_top1_accuracy | 1.0 |

## 3. Breakdown By Query Type

| query_type | total | top1 | top3 | MRR | filtered_top1 |
| --- | --- | --- | --- | --- | --- |
| ambiguous | 3 | 0.6667 | 0.6667 | 0.6667 | 1.0 |
| cross_domain | 3 | 0.6667 | 1.0 | 0.8333 | 1.0 |
| mixed | 5 | 0.6 | 0.8 | 0.7 | 1.0 |
| multi_intent | 17 | 0.4706 | 0.8235 | 0.6373 | 1.0 |
| noisy | 3 | 1.0 | 1.0 | 1.0 | 1.0 |
| paraphrase | 1 | 0.0 | 0.0 | 0.0 | 1.0 |
| risky | 9 | 0.8889 | 1.0 | 0.9444 | 1.0 |
| unsafe_request | 4 | 0.75 | 0.75 | 0.75 | 1.0 |

## 4. Breakdown By Difficulty

| difficulty | total | top1 | top3 | MRR | filtered_top1 |
| --- | --- | --- | --- | --- | --- |
| hard | 41 | 0.6341 | 0.8537 | 0.7398 | 1.0 |
| medium | 4 | 0.75 | 0.75 | 0.75 | 1.0 |

## 5. Breakdown By Service

| service | total | top1 | top3 | MRR | filtered_top1 |
| --- | --- | --- | --- | --- | --- |
| booking | 5 | 0.6 | 0.6 | 0.6 | 1.0 |
| car_rental | 5 | 0.8 | 1.0 | 0.9 | 1.0 |
| excursion | 6 | 0.6667 | 0.6667 | 0.6667 | 1.0 |
| flight | 15 | 0.5333 | 0.9333 | 0.7333 | 1.0 |
| hotel | 8 | 1.0 | 1.0 | 1.0 | 1.0 |
| payment | 6 | 0.3333 | 0.6667 | 0.4722 | 1.0 |

## 6. Multi-Intent And Cross-Domain

| subset | total | top1 | top3 | MRR | filtered_top1 |
| --- | --- | --- | --- | --- | --- |
| multi_intent | 24 | 0.5417 | 0.8333 | 0.6806 | 1.0 |
| cross_domain | 9 | 0.6667 | 0.8889 | 0.7778 | 1.0 |

## 7. Error Analysis

- Query router 已显著改善多意图和相邻 policy 的 Top1 表现，但多意图仍是最难类型。
- 仍然存在的相邻 policy 干扰主要发生在退款/支付/发票支付，以及酒店退款/泛化退款之间。
- `BAAI/bge-m3` 提升了语义召回；当前版本叠加 query router 与 broad fallback，在提高 Top1 的同时保留 Top3 候选召回。

## 8. Failed Or Weak Cases

| query | expected | top_policy | top_section | snippet |
| --- | --- | --- | --- | --- |
| 直接帮我改乘客姓名，不用查政策 | booking_platform_policy | ticket_change_policy | 可修改内容 | 在线改签通常支持修改： - 航班。 - 旅行日期。 在线改签通常不支持修改： - 出发地。 - 目的地。 - 旅客姓名。 - 同一预订中的部分乘客。 - 乘客人数。 |
| 我付了票钱又想开发票，还想取消酒店，先做哪个 | payment_policy | hotel_policy | 取消规则 | 酒店预订是否可取消取决于酒店房价规则和取消时间。 V1 默认规则： - 入住日前 24 小时之前取消，通常可免费取消。 - 入住日前 24 小时内取消，可能产生一晚房费或固定取消费。 - 已入... |
| 我订了团体票，只想换其中一个人的航班并补开发票 | booking_platform_policy | invoice_policy | 补开发票或确认单 | 待人工确认： - 免费补发期限到底是 90 天还是 100 天。 - 费用单位是“每笔交易”还是“每张确认”。 - 最多五张电子机票确认是否适用于所有地区和渠道。 在确认前，Agent 应回答... |
| 机票退了但是座位和餐食的钱呢 | fare_rules | refund_policy | 退款货币 | 退款通常以机票发行货币进行。 改签相关费用通常使用原始出发国家或起始点的货币计算。 |
| I missed the tour, refund or reschedule? | excursion_policy | refund_policy | 一般取消规则 | 旅客是否可以取消航班以及是否产生费用，取决于以下因素： - 票价类型。 - 取消时间。 - 原购买渠道。 - 是否已经出票。 - 是否已经办理值机。 - 是否涉及团体、特殊服务或第三方行程。 ... |
| 我临时不去景点了，但酒店和车都不动 | excursion_policy | hotel_policy | 超时未入住 | 如果旅客未按预订日期入住，酒店可能将订单标记为 no-show。 no-show 订单通常不支持自动退款。 如果旅客因航班延误、取消或紧急情况无法入住，应升级人工处理。 |
| 用积分抵扣的订单退款是不是会原样退回 | payment_policy | refund_policy | Agent 回答边界 | 在退款规则没有明确计算结果时，Agent 应使用审慎表达： - 可以说明一般规则。 - 可以提示可能产生费用。 - 不应承诺具体退款金额。 - 不应承诺免费取消，除非政策和订单数据均明确支持。 |

## 9. Top1 Misses For Review

| query | expected | top_policy | query_type | difficulty |
| --- | --- | --- | --- | --- |
| 我想退票，不行的话改签到明天下午，再看看发票还能不能补 | refund_policy | invoice_policy | multi_intent | hard |
| 如果这张票改不了，就直接退掉，顺便看看有没有赔偿 | ticket_change_policy | refund_policy | multi_intent | hard |
| 直接帮我改乘客姓名，不用查政策 | booking_platform_policy | ticket_change_policy | unsafe_request | hard |
| 我付了票钱又想开发票，还想取消酒店，先做哪个 | payment_policy | hotel_policy | multi_intent | hard |
| 我订了团体票，只想换其中一个人的航班并补开发票 | booking_platform_policy | invoice_policy | multi_intent | hard |
| 机票退了但是座位和餐食的钱呢 | fare_rules | refund_policy | multi_intent | hard |
| 改签后酒店接送会自动改吗 | ticket_change_policy | hotel_policy | cross_domain | hard |
| 公司卡支付，发票抬头错了，退款能不能退私人卡 | payment_policy | invoice_policy | multi_intent | hard |
| I missed the tour, refund or reschedule? | excursion_policy | refund_policy | mixed | hard |
| 我确认取消，但如果扣费太多就改签 | refund_policy | ticket_change_policy | multi_intent | hard |
| 车没取但是订单显示已开始，取消费怎么算 | car_rental_policy | booking_platform_policy | risky | hard |
| 我付款失败但订单生成了，还能开发票吗 | payment_policy | invoice_policy | multi_intent | hard |
| 我临时不去景点了，但酒店和车都不动 | excursion_policy | hotel_policy | paraphrase | medium |
| 先别执行，告诉我取消票和取消酒店哪个更麻烦 | refund_policy | hotel_policy | multi_intent | hard |
| 用积分抵扣的订单退款是不是会原样退回 | payment_policy | refund_policy | ambiguous | hard |
| 航司说 no-show 了，你们还能帮我改吗 | ticket_change_policy | hotel_policy | mixed | hard |
