# Customer Service Analytics

## 1. 数据资产概览

| Table | Rows |
| --- | --- |
| bookings | 262788 |
| tickets | 366733 |
| ticket_flights | 1045726 |
| flights | 33121 |
| boarding_passes | 579686 |
| hotels | 10 |
| car_rentals | 10 |
| trip_recommendations | 10 |
| action_audit_logs | 129 |
| service_tickets | 104 |

## 2. 订单与服务覆盖

- 唯一乘客数：`366733`
- 航班票号数：`366733`
- 航段票数：`1045726`
- 已预订酒店数：`0`
- 已预订租车数：`0`
- 已预订景点/行程数：`0`

## 3. 票价与航班分布

### 票价条件 Top 10

| Fare Condition | Count |
| --- | --- |
| Economy | 920793 |
| Business | 107642 |
| Comfort | 17291 |

### 出发机场 Top 10

| Airport | Flights |
| --- | --- |
| BSL | 3217 |
| OSL | 2981 |
| HAM | 1900 |
| SHA | 1719 |
| LHR | 1055 |
| DUS | 707 |
| PEK | 689 |
| LIS | 619 |
| MSP | 617 |
| BNE | 610 |

## 4. Guardrail 与审计指标

- 写操作审计记录数：`129`
- 已执行写操作数：`49`
- 被阻止/等待确认数：`80`
- 需要确认的记录数：`129`
- 命中人工复核政策数：`24`
- 高风险记录数：`88`

### 命中政策分布

| Policy | Hits |
| --- | --- |
| car_rental_policy | 32 |
| refund_policy | 24 |
| hotel_policy | 24 |
| excursion_policy | 22 |
| ticket_change_policy | 11 |

## 5. 人工工单指标

- service ticket 总数：`104`

### 工单优先级

| Priority | Count |
| --- | --- |
| high | 104 |

### 工单状态

| Status | Count |
| --- | --- |
| open | 104 |

## 6. 面试讲述重点

- 这个项目不仅能调用工具完成客服动作，还能在写操作前强制查政策、要求确认并记录审计。
- 结构化业务表和 RAG 政策库共同支持客服决策，适合讲数据建模、检索评测和风险控制。
- 审计表和工单表为后续自动化率、人工升级率、风险拦截率等数据科学指标提供数据基础。
