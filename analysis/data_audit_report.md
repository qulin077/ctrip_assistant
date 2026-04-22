# ctrip_assistant 数据审计报告

生成时间：2026-04-22

本报告只分析数据，不改动核心业务逻辑。审计范围包括项目根目录下的 `travel_new.sqlite`、`travel2.sqlite` 和 `order_faq.md`。本次优先分析 `travel_new.sqlite`，并将其全量表数据导出为 CSV，便于用 Excel 查看。

## 0. 文件检查结果

| 文件 | 状态 | 说明 |
| --- | --- | --- |
| `travel_new.sqlite` | 存在 | 运行时工作库，本次主分析对象，约 109MB |
| `travel2.sqlite` | 存在 | 原始备份库，表结构和行数与 `travel_new.sqlite` 一致 |
| `order_faq.md` | 存在 | 当前 FAQ/政策知识库，约 29KB |

已生成的辅助文件：

| 文件/目录 | 用途 |
| --- | --- |
| `analysis/raw_inventory.json` | 脚本生成的原始数据库/FAQ 盘点数据 |
| `analysis/raw_inventory.md` | 原始盘点摘要 |
| `analysis/exports/samples/` | 每张表前 5 行样例 CSV |
| `analysis/exports/travel_new_csv/` | `travel_new.sqlite` 全量 CSV 导出，可用 Excel 打开 |
| `tools/analyze_sqlite.py` | 本次新增的只读分析脚本 |

运行过的分析命令：

```bash
python3 tools/analyze_sqlite.py --export-full-csv
```

# 1. 数据库概览

## 1.1 表清单与行数

`travel_new.sqlite` 共 11 张业务表。

| 表名 | 行数 | 业务含义 |
| --- | ---: | --- |
| `aircrafts_data` | 9 | 飞机型号基础数据 |
| `airports_data` | 115 | 机场基础数据 |
| `boarding_passes` | 579686 | 登机牌/座位分配数据 |
| `bookings` | 262788 | 订单/预订主记录 |
| `car_rentals` | 10 | 租车服务数据 |
| `flights` | 33121 | 航班数据 |
| `hotels` | 10 | 酒店服务数据 |
| `seats` | 1339 | 飞机座位配置 |
| `ticket_flights` | 1045726 | 机票和航班的关联表，包含舱位和票价 |
| `tickets` | 366733 | 机票/乘客数据 |
| `trip_recommendations` | 10 | 景点/旅行推荐数据 |

## 1.2 关键表 schema 摘要

### flights

航班主表，描述每个航班的时刻、机场、状态和机型。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `flight_id` | INTEGER | 航班 ID，可作为航班主键使用 |
| `flight_no` | TEXT | 航班号，如 `LX0136` |
| `scheduled_departure` | TIMESTAMP | 计划起飞时间 |
| `scheduled_arrival` | TIMESTAMP | 计划到达时间 |
| `departure_airport` | TEXT | 出发机场三字码 |
| `arrival_airport` | TEXT | 到达机场三字码 |
| `status` | TEXT | 航班状态 |
| `aircraft_code` | TEXT | 机型代码 |
| `actual_departure` | TIMESTAMP | 实际起飞时间 |
| `actual_arrival` | TIMESTAMP | 实际到达时间 |

航班状态分布：

| 状态 | 数量 |
| --- | ---: |
| Arrived | 16707 |
| Scheduled | 15383 |
| On Time | 518 |
| Cancelled | 414 |
| Departed | 58 |
| Delayed | 41 |

### tickets

机票主表，关联订单和乘客。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ticket_no` | TEXT | 机票号，可作为机票主键使用 |
| `book_ref` | TEXT | 订单号，关联 `bookings.book_ref` |
| `passenger_id` | TEXT | 乘客 ID |

### ticket_flights

机票和航班的多对多关联表。一张票可对应一个或多个航段，一个航班也对应多个乘客机票。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ticket_no` | TEXT | 机票号，关联 `tickets.ticket_no` |
| `flight_id` | INTEGER | 航班 ID，关联 `flights.flight_id` |
| `fare_conditions` | TEXT | 舱位/票价条件 |
| `amount` | INTEGER | 票价金额 |

票价条件分布：

| 舱位 | 数量 | 最小金额 | 最大金额 | 平均金额 |
| --- | ---: | ---: | ---: | ---: |
| Economy | 920793 | 3000 | 74500 | 15959.81 |
| Business | 107642 | 9100 | 203300 | 51143.42 |
| Comfort | 17291 | 19900 | 47600 | 32740.55 |

### boarding_passes

登机牌/座位分配表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ticket_no` | TEXT | 机票号 |
| `flight_id` | INTEGER | 航班 ID |
| `boarding_no` | INTEGER | 登机序号 |
| `seat_no` | TEXT | 座位号 |

### bookings

订单主表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `book_ref` | TEXT | 订单号，可作为订单主键使用 |
| `book_date` | TIMESTAMP | 订单创建时间 |
| `total_amount` | INTEGER | 订单总金额 |

### hotels

酒店扩展服务表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 酒店服务 ID |
| `name` | TEXT | 酒店名称 |
| `location` | TEXT | 城市 |
| `price_tier` | TEXT | 价格层级 |
| `checkin_date` | TEXT | 入住日期 |
| `checkout_date` | TEXT | 退房日期 |
| `booked` | INTEGER | 是否已预订，0/1 |

### car_rentals

租车扩展服务表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 租车服务 ID |
| `name` | TEXT | 租车公司 |
| `location` | TEXT | 城市 |
| `price_tier` | TEXT | 车型/价格层级 |
| `start_date` | TEXT | 开始日期 |
| `end_date` | TEXT | 结束日期 |
| `booked` | INTEGER | 是否已预订，0/1 |

### trip_recommendations

景点/旅行推荐扩展服务表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 推荐 ID |
| `name` | TEXT | 推荐名称 |
| `location` | TEXT | 城市 |
| `keywords` | TEXT | 标签关键词 |
| `details` | TEXT | 详情 |
| `booked` | INTEGER | 是否已预订，0/1 |

### airports_data

机场基础数据表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `airport_code` | TEXT | 机场三字码 |
| `airport_name` | TEXT | 机场名称 |
| `city` | TEXT | 城市 |
| `coordinates` | TEXT | 经纬度字符串 |
| `timezone` | TEXT | 时区 |

### aircrafts_data

飞机型号基础数据表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `aircraft_code` | TEXT | 机型代码 |
| `model` | TEXT | 机型名称 |
| `range` | INTEGER | 航程 |

### seats

座位配置表。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `aircraft_code` | TEXT | 机型代码 |
| `seat_no` | TEXT | 座位号 |
| `fare_conditions` | TEXT | 舱位等级 |

## 1.3 前 5 行样例数据

每张表前 5 行已导出为 CSV：

```text
analysis/exports/samples/
```

全量 CSV 已导出：

```text
analysis/exports/travel_new_csv/
```

全量 CSV 文件大小：

| 文件 | 大小 |
| --- | ---: |
| `aircrafts_data.csv` | 272B |
| `airports_data.csv` | 9.1KB |
| `boarding_passes.csv` | 17MB |
| `bookings.csv` | 12MB |
| `car_rentals.csv` | 543B |
| `flights.csv` | 4.3MB |
| `hotels.csv` | 687B |
| `seats.csv` | 22KB |
| `ticket_flights.csv` | 37MB |
| `tickets.csv` | 13MB |
| `trip_recommendations.csv` | 1.1KB |

# 2. 核心业务数据链路

## 2.1 推断的主外键关系

SQLite schema 中没有显式声明主键和外键约束，但根据字段名和业务含义，可以推断出以下关系：

```text
bookings.book_ref
  -> tickets.book_ref
      -> ticket_flights.ticket_no
          -> flights.flight_id
              -> airports_data.airport_code via departure_airport / arrival_airport
              -> aircrafts_data.aircraft_code
                  -> seats.aircraft_code
          -> boarding_passes via ticket_no + flight_id
```

更具体地说：

| 关系 | 类型 | 说明 |
| --- | --- | --- |
| `bookings.book_ref -> tickets.book_ref` | 1:N | 一个订单可包含多张乘客机票 |
| `tickets.ticket_no -> ticket_flights.ticket_no` | 1:N | 一张票可包含多个航段 |
| `flights.flight_id -> ticket_flights.flight_id` | 1:N | 一个航班对应多张机票 |
| `(ticket_no, flight_id) -> boarding_passes(ticket_no, flight_id)` | 1:0/1 | 已办理登机后产生登机牌 |
| `flights.departure_airport -> airports_data.airport_code` | N:1 | 出发机场 |
| `flights.arrival_airport -> airports_data.airport_code` | N:1 | 到达机场 |
| `flights.aircraft_code -> aircrafts_data.aircraft_code` | N:1 | 飞机型号 |
| `seats.aircraft_code -> aircrafts_data.aircraft_code` | N:1 | 机型座位配置 |

完整性检查结果：

| 检查项 | 异常数量 |
| --- | ---: |
| `ticket_flights` 找不到对应 `tickets` | 0 |
| `ticket_flights` 找不到对应 `flights` | 0 |
| `tickets` 找不到对应 `bookings` | 0 |
| `boarding_passes` 找不到对应 `ticket_flights` | 1 |
| `flights.departure_airport` 找不到对应机场 | 0 |
| `flights.arrival_airport` 找不到对应机场 | 0 |
| `flights.aircraft_code` 找不到对应机型 | 0 |

结论：核心航空订单链路的数据完整性整体很好，只有 1 条登机牌记录无法关联到 `ticket_flights`，对 V1 客服系统影响很小，但后续数据治理应记录并修复。

## 2.2 航班订单链路

航班订单链路是当前项目最核心的数据链路：

```text
bookings
  -> tickets
  -> ticket_flights
  -> flights
  -> boarding_passes
```

面向客服 Agent 时，这条链路支撑以下能力：

- 查询用户有哪些订单和机票
- 查询用户当前航班、出发/到达机场、起降时间
- 查询票价条件和金额
- 查询座位号、登机牌信息
- 改签时校验机票归属和新航班是否合法
- 取消机票时校验乘客身份和票号是否存在

当前代码中的 `fetch_user_flight_information`、`search_flights`、`update_ticket_to_new_flight`、`cancel_ticket` 都围绕这条链路工作。

## 2.3 酒店链路

酒店链路目前非常轻量：

```text
hotels
```

当前表只有 10 条演示数据，没有和乘客、订单、城市行程绑定。它可以支持：

- 按城市/名称查询酒店
- 标记预订
- 修改入住/退房日期
- 取消预订

但从企业级角度看，当前 `hotels.booked` 是全局状态，不区分哪个用户预订了哪间酒店。这适合 demo，不适合真实业务。

## 2.4 租车链路

租车链路类似酒店：

```text
car_rentals
```

当前也只有 10 条演示数据，没有用户维度、订单维度和库存维度。可用于 V1 演示查询/预订/取消，但生产化前需要拆分为服务目录表和用户预订表。

## 2.5 景点/推荐链路

景点/推荐链路：

```text
trip_recommendations
```

它更像目的地推荐目录，而不是严格意义上的订单表。当前 `booked` 字段同样是全局布尔值，不能表达用户级预订状态。

# 3. V1 建议保留的数据表

## 3.1 必须保留

这些表构成旅行客服智能体 V1 的核心能力，应优先保留：

| 表 | 原因 |
| --- | --- |
| `bookings` | 订单主记录，是查询订单和金额的入口 |
| `tickets` | 乘客和机票关系，是用户身份校验的基础 |
| `ticket_flights` | 机票和航段关系，改签/退票离不开 |
| `flights` | 航班搜索、改签候选、状态查询的核心 |
| `boarding_passes` | 查询座位和登机信息需要 |
| `airports_data` | 把机场代码解释为城市/机场名称，改善客服回答可读性 |

## 3.2 可选保留

这些表对体验有帮助，但不是 V1 航班客服闭环的硬依赖：

| 表 | 建议 |
| --- | --- |
| `aircrafts_data` | 可保留，用于展示机型；对改签/退票不是必需 |
| `seats` | 可保留，用于座位配置解释；当前工具暂未深度使用 |
| `hotels` | 可保留，用于演示跨售卖服务 |
| `car_rentals` | 可保留，用于演示跨售卖服务 |
| `trip_recommendations` | 可保留，用于目的地推荐和增值服务 |

## 3.3 V1 可以先不动

以下部分可以先不重构，只在工具层做保护：

- `aircrafts_data` 和 `seats`：先只作为只读基础数据。
- `hotels`、`car_rentals`、`trip_recommendations`：先保留 demo 表结构，但在回答中避免把它们描述成真实库存系统。
- `boarding_passes` 中的 1 条孤立记录：记录为数据质量问题，不必阻塞 V1。

## 3.4 V1 不建议继续沿用的设计

以下设计适合课程 demo，不适合企业级客服系统：

- `hotels.booked`、`car_rentals.booked`、`trip_recommendations.booked` 是全局状态，缺少 `passenger_id`、`booking_id`、`created_at`。
- 航班改签直接更新 `ticket_flights.flight_id`，缺少变更前后记录和审计日志。
- 取消机票当前删除 `ticket_flights` 记录，缺少取消状态、取消原因、退款状态。
- SQLite schema 没有显式主键/外键/索引声明。

# 4. FAQ 文档审计

## 4.1 当前主题结构

`order_faq.md` 当前只有二级标题，没有一级标题。按 `##` 拆分后共有 10 个主题：

| 主题 | 起始行 | 字符数 | 编号项数量 | 业务分类 |
| --- | ---: | ---: | ---: | --- |
| 发票问题 | 1 | 415 | 6 | 发票政策 + 航班查询/票价基础问题 |
| 预订和取消 | 25 | 1541 | 19 | 改签政策 + 取消限制 |
| 预订平台 | 79 | 803 | 10 | 预订平台使用规则 |
| 订购发票 | 102 | 373 | 0 | 发票政策 |
| 信用卡 | 117 | 301 | 0 | 支付与信用卡 |
| 卡片安全 | 140 | 441 | 0 | 支付安全 |
| 按发票支付 | 158 | 1322 | 0 | 发票/账单支付 |
| 常见问题：支付 | 212 | 424 | 0 | 支付与货币转换 |
| 常见问题：欧洲票价概念 | 237 | 1302 | 0 | 票价规则 + 行李 + 升级 |
| 如何取消瑞士航空航班：877-5O7-7341 分步指南 | 284 | 3492 | 0 | 疑似外部网页拼接内容，噪声较高 |

## 4.2 按业务知识分类

| 分类 | 涉及章节 |
| --- | --- |
| 改签政策 | `预订和取消`、`常见问题：欧洲票价概念` |
| 取消/退款政策 | `预订和取消`、`按发票支付`、`如何取消瑞士航空航班...` |
| 发票政策 | `发票问题`、`订购发票`、`按发票支付` |
| 支付与信用卡 | `信用卡`、`卡片安全`、`常见问题：支付`、`按发票支付` |
| 票价规则 | `发票问题` 中的票价类别、`常见问题：欧洲票价概念` |
| 预订平台 | `预订平台` |
| 酒店/租车/附加服务政策 | 仅在 `预订和取消` 和 `常见问题：欧洲票价概念` 中零散出现，内容不足 |

## 4.3 内容重复问题

主要重复点：

- 发票相关内容分散在 `发票问题`、`订购发票`、`按发票支付`，且 90/100 天免费重发确认的口径不一致。
- 支付相关内容分散在 `信用卡`、`卡片安全`、`常见问题：支付`、`按发票支付`。
- 取消/退款内容在 `预订和取消`、`按发票支付`、最后一段外部取消指南中重复。
- `卡片安全` 中“如果您对 3-D Secure 的卡片注册有任何疑问...”连续出现两次，属于明显重复句。

## 4.4 噪声和不标准问题

当前 FAQ 不适合直接作为企业知识库上线，原因如下：

1. `如何取消瑞士航空航班：877-5O7-7341 分步指南` 包含电话号码，并且标题像 SEO 网页内容，不像官方政策文本。
2. 最后一节篇幅过长，内容泛化、重复、步骤化但缺少结构化规则字段，不适合直接做 RAG chunk。
3. 有些编号都写成 `1.`，Markdown 渲染可自动编号，但作为切分依据时不够稳定。
4. `发票问题` 中混入“是否需要重新确认航班”“能否不预订查询票价”等非发票问题。
5. 90 天/100 天免费重发确认口径冲突，需要业务确认。
6. 酒店、租车、附加服务政策缺失，无法支撑现有工具的企业级客服回答。

## 4.5 不适合直接检索的部分

最不适合直接做 RAG chunk 的部分：

- `如何取消瑞士航空航班：877-5O7-7341 分步指南`：3492 字符，像外部网页拼接，包含电话号码、SEO 标题、重复取消步骤。
- `按发票支付`：1322 字符，包含多个问题，但没有按小标题/问答切细。
- `常见问题：欧洲票价概念`：1302 字符，混合票价、行李、升级、同日改签，需要拆成多个主题。
- `预订和取消`：1541 字符，虽然相关性高，但应该拆为“可改签条件”“不可改签条件”“改签后影响”“特殊场景”。

## 4.6 是否适合作为单文件知识库直接检索

结论：不建议继续作为单文件知识库直接检索。

原因：

- 主题混杂，检索命中后容易把不相关政策塞给 LLM。
- chunk 粒度不均衡，有的章节 300 字，有的 3500 字。
- 存在重复和疑似非官方外部内容，会降低回答可信度。
- 缺少 metadata，无法按业务场景过滤，例如 `policy_type=refund`、`channel=online`、`service=flight`。

V1 可以暂时保留 `order_faq.md` 作为 raw source，但应该尽快拆成多文件、多 metadata 的知识库。

## 4.7 建议拆分后的知识库结构

建议新增如下结构：

```text
kb/
  raw/
    policy/
      ticket_change_policy.md
      refund_policy.md
      invoice_policy.md
      payment_policy.md
      fare_rules.md
      booking_platform_policy.md
      baggage_policy.md
      upgrade_policy.md
      hotel_policy.md
      car_rental_policy.md
      excursion_policy.md
    faq/
      customer_common_questions.md
  processed/
    chunks.jsonl
    metadata_schema.md
```

建议每个政策文档都包含 YAML front matter：

```yaml
---
policy_id: ticket_change_policy
service: flight
policy_type: change
source: order_faq.md
language: zh-CN
effective_date: unknown
requires_human_review: true
---
```

建议拆分规则：

- `ticket_change_policy.md`：可改签条件、不可改签条件、起飞前 3 小时限制、改签后座位/餐食/APIS 是否保留。
- `refund_policy.md`：取消、退款、退款币种、退款渠道、已发票/未发票场景。
- `invoice_policy.md`：电子机票确认、发票申请、90/100 天规则冲突待确认。
- `payment_policy.md`：信用卡、安全码、3-D Secure、按发票支付、货币转换。
- `fare_rules.md`：舱位、票价概念、经济轻便/经典/灵活。
- `booking_platform_policy.md`：个人资料、App/桌面功能差异、团体预订。
- `baggage_policy.md`：第一件行李、额外行李、经济轻便行李限制。
- `hotel_policy.md`、`car_rental_policy.md`、`excursion_policy.md`：当前 FAQ 缺失，需要补充。

# 5. 面向企业化升级的数据改造建议

## 5.1 建议新增数据库表

为了从 demo Agent 升级为企业级旅行客服系统，建议新增以下表。

### service_sessions

记录一次用户客服会话。

建议字段：

```text
session_id
passenger_id
channel
started_at
ended_at
status
handoff_required
handoff_reason
```

用途：

- 支撑多轮对话追踪。
- 统计用户从提问到解决的完整链路。
- 作为人工升级入口。

### service_tickets

记录客服工单。

建议字段：

```text
ticket_id
session_id
passenger_id
intent
priority
status
assigned_agent_id
created_at
resolved_at
resolution_summary
```

用途：

- 当 Agent 不能处理、政策冲突、用户投诉时创建工单。
- 支撑人工客服接管。

### conversation_summaries

记录会话摘要。

建议字段：

```text
summary_id
session_id
passenger_id
summary
open_questions
resolved_actions
created_at
model_name
```

用途：

- 长对话压缩。
- 人工客服快速接手。
- 会话质检。

### action_audit_logs

记录所有工具写操作。

建议字段：

```text
action_id
session_id
passenger_id
tool_name
target_table
target_id
before_state_json
after_state_json
requested_by
confirmed_by_user
created_at
status
error_message
```

用途：

- 改签、取消、酒店/租车预订都要可审计。
- 方便回滚、追责和质检。

### customer_profiles

补充乘客画像。

建议字段：

```text
passenger_id
name
email
phone
loyalty_level
preferred_language
created_at
updated_at
```

用途：

- 当前 `tickets` 只有 `passenger_id`，缺少真实客服必需的联系方式和偏好。

### service_orders

抽象酒店、租车、景点等扩展服务订单。

建议字段：

```text
service_order_id
passenger_id
service_type
service_item_id
status
start_date
end_date
created_at
updated_at
```

用途：

- 替代 `hotels.booked`、`car_rentals.booked`、`trip_recommendations.booked` 这种全局状态。

### policy_documents

管理知识库文档。

建议字段：

```text
document_id
title
service
policy_type
source_path
version
effective_date
review_status
created_at
updated_at
```

用途：

- 支撑企业知识库治理。
- 支撑按服务、政策类型、版本过滤 RAG。

## 5.2 FAQ 知识库改造建议

建议从“单文件 FAQ”升级为“可治理政策知识库”：

1. 拆分为多 Markdown 文件，每个文件只覆盖一个政策主题。
2. 每个文件加 YAML metadata，至少包含 `service`、`policy_type`、`source`、`effective_date`、`review_status`。
3. RAG chunk 不要简单按字符切，优先按“问题-答案”或“规则条款”切。
4. 对每个 chunk 加 metadata：

```json
{
  "chunk_id": "ticket_change_policy__online_change__001",
  "document_id": "ticket_change_policy",
  "service": "flight",
  "policy_type": "change",
  "allowed_action": "ticket_change",
  "requires_human_review": false,
  "source_section": "预订和取消"
}
```

5. 删除或隔离疑似外部网页拼接内容，尤其是带电话号码的取消指南。
6. 对冲突政策做人工标注，例如发票重发到底是 90 天还是 100 天。

## 5.3 现有工具复用建议

可以继续复用：

| 工具 | 复用建议 |
| --- | --- |
| `fetch_user_flight_information` | V1 必留，是用户航班查询入口 |
| `search_flights` | V1 必留，但建议补充机场/城市转换和时间解析 |
| `lookup_policy` | 保留接口，但底层从单文件内存向量检索升级为正式向量库 |
| `update_ticket_to_new_flight` | 保留核心校验逻辑，但写操作前加用户确认和审计日志 |
| `cancel_ticket` | 保留身份校验逻辑，但不要直接删除记录，改为状态化取消 |
| `search_hotels` / `search_car_rentals` / `search_trip_recommendations` | 可继续作为推荐查询工具 |

需要谨慎改造：

- `book_hotel`、`book_car_rental`、`book_excursion`：当前只是更新全局 `booked=1`，应改成创建用户级服务订单。
- `cancel_hotel`、`cancel_car_rental`、`cancel_excursion`：应改成取消用户级服务订单，而不是更新服务目录。
- `lookup_policy`：当前每次导入模块都会重新 embedding，建议缓存向量库。

## 5.4 适合加摘要、质检、人工升级的位置

建议在 LangGraph 流程中增加以下节点：

```text
assistant
  -> intent_classifier
  -> policy_retriever
  -> tool_planner
  -> user_confirmation_for_write_actions
  -> tools
  -> action_audit_logger
  -> answer_generator
  -> quality_checker
  -> human_handoff_if_needed
```

具体建议：

- 写操作前：必须加 `user_confirmation_for_write_actions`。
- 写操作后：必须写入 `action_audit_logs`。
- 多轮对话后：写入 `conversation_summaries`。
- 政策冲突时：触发人工升级。
- 用户情绪负面、投诉、索赔、航班取消、支付争议：触发人工升级。
- RAG 检索为空或置信度低：先追问澄清，再考虑人工升级。

## 5.5 V1 企业化升级优先级

建议下一步按这个顺序推进：

1. 把 `order_faq.md` 拆成结构化知识库，并加 metadata。
2. 把 `lookup_policy` 底层改成可持久化向量库，例如 FAISS/Chroma/Milvus。
3. 给改签、取消、预订类工具加用户二次确认。
4. 新增 `action_audit_logs`，记录所有写操作。
5. 把酒店/租车/景点的 `booked` 全局字段改造成用户级服务订单。
6. 给 LangGraph 增加人工升级和对话摘要节点。

# 6. 本次导出说明

## 6.1 Excel 可读数据

已将 `travel_new.sqlite` 全量导出为 CSV：

```text
analysis/exports/travel_new_csv/
```

Excel 可以直接打开这些文件。注意 `ticket_flights.csv` 有 1045726 行，加上表头仍低于 Excel 单 sheet 1048576 行限制，但已经非常接近上限。

## 6.2 前 5 行样例

每张表前 5 行样例：

```text
analysis/exports/samples/
```

## 6.3 原始盘点文件

```text
analysis/raw_inventory.json
analysis/raw_inventory.md
```

这两个文件适合后续自动生成文档或做二次分析。
