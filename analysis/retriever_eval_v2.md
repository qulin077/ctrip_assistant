# Retriever Evaluation V2

## 1. Evaluation Setup

- Eval cases: 114
- Top K: 3
- Embedding provider: `sentence_transformers:BAAI/bge-m3`
- Embedding model: `BAAI/bge-m3`

## 2. Overall Metrics

| metric | value |
| --- | --- |
| top1_accuracy | 0.7982 |
| top3_accuracy | 0.9386 |
| MRR | 0.864 |
| filtered_top1_accuracy | 1.0 |

## 3. Breakdown By Query Type

| query_type | total | top1 | top3 | MRR | filtered_top1 |
| --- | --- | --- | --- | --- | --- |
| direct | 42 | 0.9524 | 1.0 | 0.9762 | 1.0 |
| multi_intent | 13 | 0.3077 | 0.7692 | 0.5385 | 1.0 |
| noisy | 9 | 0.8889 | 0.8889 | 0.8889 | 1.0 |
| paraphrase | 22 | 0.7273 | 0.9091 | 0.8106 | 1.0 |
| risky | 28 | 0.8214 | 0.9643 | 0.881 | 1.0 |

## 4. Breakdown By Difficulty

| difficulty | total | top1 | top3 | MRR | filtered_top1 |
| --- | --- | --- | --- | --- | --- |
| easy | 24 | 0.9167 | 1.0 | 0.9583 | 1.0 |
| hard | 35 | 0.6571 | 0.9143 | 0.7762 | 1.0 |
| medium | 55 | 0.8364 | 0.9273 | 0.8788 | 1.0 |

## 5. Breakdown By Service

| service | total | top1 | top3 | MRR | filtered_top1 |
| --- | --- | --- | --- | --- | --- |
| booking | 12 | 0.5833 | 0.9167 | 0.7361 | 1.0 |
| car_rental | 12 | 1.0 | 1.0 | 1.0 | 1.0 |
| excursion | 12 | 0.9167 | 1.0 | 0.9583 | 1.0 |
| flight | 54 | 0.7593 | 0.9074 | 0.8302 | 1.0 |
| hotel | 12 | 0.8333 | 0.9167 | 0.875 | 1.0 |
| payment | 12 | 0.8333 | 1.0 | 0.9028 | 1.0 |

## 6. Error Analysis

- 多意图和高风险 query 最容易错，因为一个问题里同时出现退票、改签、酒店、租车等多个相邻业务意图。
- 相邻 policy 的误命中主要发生在退款、票价规则、支付退款之间，以及酒店/租车/景点三个 `booking_policy` 类型之间。
- `BAAI/bge-m3` 提升了语义召回，但多意图 query 仍需要 query router 或意图拆分来减少相邻 policy 干扰。

## 7. Failed Or Weak Cases

| query | expected | top_policy | top_section | snippet |
| --- | --- | --- | --- | --- |
| 我这票还能不能往后挪一下？ | ticket_change_policy | fare_rules | 附加服务 | 附加选项包括提前座位预订、额外行李等。 对于经济轻便票价，附加选项通常不能随票价一起改签，因为票价本身无法更改。 对于经济经典票价，附加选项通常只能在相同预订中预订。 |
| 我想退票，不行的话帮我改签到明天下午 | refund_policy | ticket_change_policy | 可以在线改签的机票 | 符合以下条件的机票通常可以在线改签： - 机票号码以 `724` 开头。 - 机票不是通过易货或代金券支付。 - 如果机票通过代金券全额支付，部分情况下可能可以在线改签；具体以系统提示为准。 ... |
| 行程单能报销吗？ | invoice_policy | excursion_policy | 退款规则 | 以下场景可能支持退款或部分退款： - 活动供应商取消活动。 - 因恶劣天气导致活动无法进行。 - 活动项目无法按原确认内容提供。 - 旅客在免费取消时间前取消。 以下场景通常不支持自动退款： ... |
| 我想先退票再开发票，顺序有没有限制？ | invoice_policy | excursion_policy | 取消规则 | V1 默认规则： - 活动开始前 24 小时之前取消，通常可免费取消。 - 活动开始前 24 小时内取消，可能产生取消费。 - 活动开始后或旅客未到场，通常不支持自动退款。 具体退款金额以活动... |
| 特价票和普通票退改差别大吗？ | fare_rules | refund_policy | 不同票价类型的退款差异 | 当前 FAQ 表明： - 灵活类票价通常有更高的改退灵活性。 - 非灵活经济舱票价取消时可能产生取消费用。 - 取消时间越接近出发日期，取消费用可能越高。 - 经济轻便票价中的第一件付费行李费... |
| 旅行社订的票为什么不能直接改？ | booking_platform_policy | ticket_change_policy | 旅行社和套餐预订 | 通过旅行社购买的航班预订可以在线更改，但旅行社可能无法访问新的电子机票。 如果航班属于旅行社购买的套餐，在线改签通常只处理航班预订，不处理套餐中包含的酒店、租车等其他服务。 |
| 先看看酒店能不能取消，再帮我改租车日期 | hotel_policy | car_rental_policy | 租车预订 | 旅客可以根据城市、租车公司或车型/价格层级查询租车服务。 预订时应确认： - 取车城市。 - 取车日期。 - 还车日期。 - 租车公司。 - 车型或价格层级。 当前 demo 数据仅以 `bo... |

## 8. Top1 Misses For Review

| query | expected | top_policy | query_type | difficulty |
| --- | --- | --- | --- | --- |
| 我这票还能不能往后挪一下？ | ticket_change_policy | fare_rules | noisy | medium |
| 我想换日期但不换目的地，应该看什么规则？ | ticket_change_policy | hotel_policy | paraphrase | medium |
| 我想退票，不行的话帮我改签到明天下午 | refund_policy | ticket_change_policy | multi_intent | hard |
| 退到别的银行卡可以吗？ | refund_policy | payment_policy | risky | medium |
| 我先取消酒店再退机票，两个退款规则一样吗？ | refund_policy | hotel_policy | multi_intent | hard |
| 行程单能报销吗？ | invoice_policy | excursion_policy | paraphrase | medium |
| 我需要确认单，可以重新开吗？ | invoice_policy | excursion_policy | direct | easy |
| 我过了三个月还能要发票吗？ | invoice_policy | payment_policy | paraphrase | medium |
| 取消订单后还能补开发票吗？ | invoice_policy | refund_policy | multi_intent | hard |
| 我想先退票再开发票，顺序有没有限制？ | invoice_policy | excursion_policy | multi_intent | hard |
| 瑞士和德国的发票要求一样吗？ | invoice_policy | payment_policy | paraphrase | medium |
| 用公司发票付款后还能退到卡里吗？ | payment_policy | refund_policy | multi_intent | hard |
| 支付失败会不会自动保留座位？ | payment_policy | ticket_change_policy | risky | hard |
| 舱位类型会影响退改吗？ | fare_rules | refund_policy | paraphrase | medium |
| 特价票和普通票退改差别大吗？ | fare_rules | refund_policy | paraphrase | medium |
| App 里面能看到所有预订吗？ | booking_platform_policy | hotel_policy | direct | easy |
| 旅行社订的票为什么不能直接改？ | booking_platform_policy | ticket_change_policy | risky | medium |
| 我在 App 找不到酒店订单怎么办？ | booking_platform_policy | hotel_policy | multi_intent | hard |
| 第三方预订能不能让客服直接取消？ | booking_platform_policy | refund_policy | risky | hard |
| 团体票、第三方票和普通票处理方式有什么不同？ | booking_platform_policy | fare_rules | multi_intent | hard |
| 先看看酒店能不能取消，再帮我改租车日期 | hotel_policy | car_rental_policy | multi_intent | hard |
| 我已经 check in 了能全额退吗？ | hotel_policy | excursion_policy | risky | hard |
| 我想改景点日期，不行就取消 | excursion_policy | hotel_policy | multi_intent | hard |
