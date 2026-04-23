# Retriever Evaluation V2

## 1. Evaluation Setup

- Eval cases: 114
- Top K: 3
- Embedding provider: `local_hash`
- Embedding model: `BAAI/bge-m3`

## 2. Overall Metrics

| metric | value |
| --- | --- |
| top1_accuracy | 0.7895 |
| top3_accuracy | 0.9123 |
| MRR | 0.8421 |
| filtered_top1_accuracy | 1.0 |

## 3. Breakdown By Query Type

| query_type | total | top1 | top3 | MRR | filtered_top1 |
| --- | --- | --- | --- | --- | --- |
| direct | 42 | 0.9286 | 0.9762 | 0.9524 | 1.0 |
| multi_intent | 13 | 0.4615 | 0.7692 | 0.5769 | 1.0 |
| noisy | 9 | 0.8889 | 0.8889 | 0.8889 | 1.0 |
| paraphrase | 22 | 0.6818 | 0.9091 | 0.7803 | 1.0 |
| risky | 28 | 0.7857 | 0.8929 | 0.8333 | 1.0 |

## 4. Breakdown By Difficulty

| difficulty | total | top1 | top3 | MRR | filtered_top1 |
| --- | --- | --- | --- | --- | --- |
| easy | 24 | 1.0 | 1.0 | 1.0 | 1.0 |
| hard | 35 | 0.6857 | 0.8571 | 0.7571 | 1.0 |
| medium | 55 | 0.7636 | 0.9091 | 0.8273 | 1.0 |

## 5. Breakdown By Service

| service | total | top1 | top3 | MRR | filtered_top1 |
| --- | --- | --- | --- | --- | --- |
| booking | 12 | 0.6667 | 0.6667 | 0.6667 | 1.0 |
| car_rental | 12 | 0.9167 | 1.0 | 0.9583 | 1.0 |
| excursion | 12 | 0.8333 | 0.9167 | 0.8611 | 1.0 |
| flight | 54 | 0.7593 | 0.9259 | 0.8333 | 1.0 |
| hotel | 12 | 0.9167 | 0.9167 | 0.9167 | 1.0 |
| payment | 12 | 0.75 | 1.0 | 0.8472 | 1.0 |

## 6. Error Analysis

- 多意图和高风险 query 最容易错，因为一个问题里同时出现退票、改签、酒店、租车等多个相邻业务意图。
- 相邻 policy 的误命中主要发生在退款、票价规则、支付退款之间，以及酒店/租车/景点三个 `booking_policy` 类型之间。
- `local_hash` embedding 更依赖词面重叠，遇到口语化、英文缩写或隐含业务语义时不如语义向量模型稳定。

## 7. Failed Or Weak Cases

| query | expected | top_policy | top_section | snippet |
| --- | --- | --- | --- | --- |
| 我想退票，不行的话帮我改签到明天下午 | refund_policy | ticket_change_policy | 多次改签 | 如果票价条件允许，已改签后的行程可以再次改签。 |
| 退到别的银行卡可以吗？ | refund_policy | payment_policy | 3-D Secure | 在欧盟经济区发行的信用卡和借记卡，可能需要进行 3-D Secure 认证。 3-D Secure 是一个额外认证步骤，用于提升支付安全并降低欺诈风险。 如果旅客尚未注册，通常需要通过发卡银行... |
| 退票政策里哪些地方需要人工确认？ | refund_policy | hotel_policy | 部分退款 | 部分退款仅在以下场景可考虑： - 提前退房且酒店确认可退。 - 因航班取消或不可抗力导致无法入住。 - 酒店无法履约，例如无法提供已确认房型。 部分退款金额需要人工确认。 |
| 行程单能报销吗？ | invoice_policy | excursion_policy | 查询与预订 | 旅客可以根据城市、推荐名称或关键词查询景点和行程推荐。 预订前应确认： - 推荐项目名称。 - 城市或集合地点。 - 活动日期和时间。 - 参与人数。 - 是否存在年龄、身体状况、天气或语言限... |
| 第三方买的票能在官网吗？ | booking_platform_policy | ticket_change_policy | 不能在线改签的机票或预订 | - 包含特殊服务的预订，例如动物运输、医疗设备运输、特殊运动器材运输等。 - 团体预订中的机票。 - 预订舱位与票价代码不一致的机票。 - 在线兑换预订当前不能通过 swiss.com 改签。... |
| 旅行社订的票为什么不能直接改？ | booking_platform_policy | ticket_change_policy | 旅行社和套餐预订 | 通过旅行社购买的航班预订可以在线更改，但旅行社可能无法访问新的电子机票。 如果航班属于旅行社购买的套餐，在线改签通常只处理航班预订，不处理套餐中包含的酒店、租车等其他服务。 |
| 我在 App 找不到酒店订单怎么办？ | booking_platform_policy | hotel_policy | Agent 回答边界 | Agent 可以说明一般规则和发起查询、预订、修改或取消流程。 在没有酒店确认规则和订单价格时，Agent 不应承诺具体退款金额。 |
| 团体票、第三方票和普通票处理方式有什么不同？ | booking_platform_policy | fare_rules | 团体票价 | 团体预订在机票出票前通常可以免费更改为任何票价选项，前提是相同价格仍然可用。 因此，经济灵活票价对团体可能没有额外好处，当前 FAQ 表示不提供给团体。 |
| 我已经 check in 了能全额退吗？ | hotel_policy | refund_policy | 航司取消航班 | 如果航司取消航班，旅客可能有资格获得全额退款或改订其他航班。 待人工确认： - 恶劣天气、政治动荡等特殊情况是否属于航司免责场景。 - 不同司法辖区下的补偿规则。 |
| 景点票当天没去还能退吗？ | excursion_policy | payment_policy | POWERPAY 发票 | 按发票支付场景下，个人发票通常会在约 24 至 48 小时后通过电子邮件发送。 如果个人发票按时支付，通常不会产生额外费用。 如果未按时支付，未付款项可能汇总为月度账户对账单。月度发票可能产生... |

## 8. Top1 Misses For Review

| query | expected | top_policy | query_type | difficulty |
| --- | --- | --- | --- | --- |
| 团体票能不能自己在网上换航班？ | ticket_change_policy | fare_rules | paraphrase | medium |
| 我想换日期但不换目的地，应该看什么规则？ | ticket_change_policy | hotel_policy | paraphrase | medium |
| 我想退票，不行的话帮我改签到明天下午 | refund_policy | ticket_change_policy | multi_intent | hard |
| 退到别的银行卡可以吗？ | refund_policy | payment_policy | risky | medium |
| 出票后马上取消是不是肯定免费？ | refund_policy | hotel_policy | risky | hard |
| 我先取消酒店再退机票，两个退款规则一样吗？ | refund_policy | hotel_policy | multi_intent | hard |
| 退票政策里哪些地方需要人工确认？ | refund_policy | hotel_policy | direct | medium |
| 行程单能报销吗？ | invoice_policy | excursion_policy | paraphrase | medium |
| 我过了三个月还能要发票吗？ | invoice_policy | payment_policy | paraphrase | medium |
| 3DS 验证失败订单会成功吗？ | payment_policy | excursion_policy | risky | medium |
| 我能不能用人民币付欧元票价？ | payment_policy | refund_policy | paraphrase | medium |
| 支付失败会不会自动保留座位？ | payment_policy | ticket_change_policy | risky | hard |
| 附加服务买了以后能退吗？ | fare_rules | payment_policy | direct | medium |
| 我想改签并加行李，规则看哪部分？ | fare_rules | ticket_change_policy | multi_intent | hard |
| 欧洲境内票有没有包含座位选择？ | fare_rules | ticket_change_policy | direct | medium |
| 特价票和普通票退改差别大吗？ | fare_rules | refund_policy | paraphrase | medium |
| 第三方买的票能在官网吗？ | booking_platform_policy | ticket_change_policy | paraphrase | medium |
| 旅行社订的票为什么不能直接改？ | booking_platform_policy | ticket_change_policy | risky | medium |
| 我在 App 找不到酒店订单怎么办？ | booking_platform_policy | hotel_policy | multi_intent | hard |
| 团体票、第三方票和普通票处理方式有什么不同？ | booking_platform_policy | fare_rules | multi_intent | hard |
| 我已经 check in 了能全额退吗？ | hotel_policy | refund_policy | risky | hard |
| 先看看酒店能不能取消，再帮我改租车日期 | car_rental_policy | hotel_policy | multi_intent | hard |
| 景点票当天没去还能退吗？ | excursion_policy | payment_policy | noisy | hard |
| 我想改景点日期，不行就取消 | excursion_policy | hotel_policy | multi_intent | hard |
