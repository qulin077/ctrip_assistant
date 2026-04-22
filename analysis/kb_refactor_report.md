# 知识库重构报告

生成时间：2026-04-22

本次重构只处理知识库层，不改 LangGraph 主流程，不改数据库逻辑，不删除原始 `order_faq.md`。

## 1. 新知识库目录

已新增目录结构：

```text
kb/
  raw/
    policy/
      booking_platform_policy.md
      car_rental_policy.md
      excursion_policy.md
      fare_rules.md
      hotel_policy.md
      invoice_policy.md
      payment_policy.md
      refund_policy.md
      ticket_change_policy.md
  processed/
    .gitkeep
  metadata/
    policy_index.jsonl
```

`order_faq.md` 保留为原始 source，不做删除或覆盖。

## 2. 从原 FAQ 拆分出的文档

从 `order_faq.md` 中提炼、拆分并整理出 6 份政策文档：

| 新文档 | 来源章节 | 主题 |
| --- | --- | --- |
| `kb/raw/policy/ticket_change_policy.md` | `预订和取消`、部分票价相关内容 | 机票改签规则 |
| `kb/raw/policy/refund_policy.md` | `预订和取消`、`按发票支付`、外部取消指南中的概念性信息 | 取消与退款规则 |
| `kb/raw/policy/invoice_policy.md` | `发票问题`、`订购发票` | 发票与电子机票确认 |
| `kb/raw/policy/payment_policy.md` | `信用卡`、`卡片安全`、`按发票支付`、`常见问题：支付` | 支付与信用卡安全 |
| `kb/raw/policy/fare_rules.md` | `发票问题` 中的舱位信息、`常见问题：欧洲票价概念` | 票价、舱位、行李和升级 |
| `kb/raw/policy/booking_platform_policy.md` | `预订平台` | 个人资料、App/桌面差异和团体预订 |

每个文档都已补充 YAML front matter，包含：

- `policy_id`
- `title`
- `service`
- `policy_type`
- `language`
- `source`
- `review_status`
- `requires_human_review`

## 3. 新增的 V1 模拟业务政策文档

当前原 FAQ 基本没有覆盖酒店、租车、景点/行程推荐政策，但项目已有对应工具。为支撑后续 RAG 问答和工具调用，本次新增 3 份 V1 模拟企业内部政策：

| 新文档 | source | 目的 |
| --- | --- | --- |
| `kb/raw/policy/hotel_policy.md` | `internal_mock_policy` | 支持酒店查询、预订、修改、取消问答 |
| `kb/raw/policy/car_rental_policy.md` | `internal_mock_policy` | 支持租车查询、预订、修改、取消问答 |
| `kb/raw/policy/excursion_policy.md` | `internal_mock_policy` | 支持景点/行程推荐查询、预订、改期、取消问答 |

这些文档采用正式、简洁的客服知识库风格，避免营销文案。由于它们是 V1 模拟政策，后续上线前仍需要业务方确认。

## 4. 删除或隔离的内容

以下内容没有直接照搬到新知识库：

### 4.1 外部网页拼接内容

原 FAQ 末尾章节：

```text
如何取消瑞士航空航班：877-5O7-7341 分步指南
```

未作为独立正式政策照搬。

原因：

- 标题含电话号码，疑似 SEO 或外部网页拼接内容。
- 语气和结构不像内部政策文档。
- 内容重复描述取消流程。
- 缺少可验证的官方来源。
- 会污染 RAG 检索结果，降低回答可信度。

处理方式：

- 仅在 `refund_policy.md` 中保留少量概念性提醒，例如不同票价取消规则可能不同。
- 明确标记相关信息“待人工确认”。
- 不保留电话号码。

### 4.2 重复句和噪声

原 FAQ 中 `卡片安全` 的 3-D Secure 问题有重复句：

```text
如果您对3-D Secure的卡片注册有任何疑问，请直接联系您的银行。
如果您对3-D Secure的卡片注册有任何疑问，请直接联系您的银行或卡片发行公司。
```

新文档中已合并为一条标准表达。

### 4.3 主题错位内容

原 `发票问题` 中包含“是否需要重新确认航班”“是否可不预订查询票价”等非发票问题。本次没有把它们放入 `invoice_policy.md`，而是只保留与发票、电子机票确认、票价代码相关的内容。

## 5. 已标记待人工确认的冲突

以下冲突或不确定内容已标记：

| 文档 | 问题 | 处理 |
| --- | --- | --- |
| `invoice_policy.md` | 免费补开发票/确认单期限存在 90 天和 100 天两个口径 | `requires_human_review: true` |
| `invoice_policy.md` | 超期费用是“每笔交易”还是“每张确认”存在口径差异 | 文内标记待人工确认 |
| `refund_policy.md` | 24 小时取消规则来源于疑似外部拼接内容 | `requires_human_review: true` |
| `refund_policy.md` | 不同票价类型的具体退款比例和取消费计算方式不明确 | 文内标记待人工确认 |
| `refund_policy.md` | 航司取消航班时特殊原因下的补偿义务不明确 | 文内标记待人工确认 |

## 6. 知识库索引

已新增：

```text
kb/metadata/policy_index.jsonl
```

每条记录包含：

- `policy_id`
- `title`
- `service`
- `policy_type`
- `source`
- `review_status`
- `requires_human_review`
- `file_path`

这个索引可以作为后续 RAG ingestion 的入口。

## 7. 当前知识库还缺什么

当前知识库已经比原单文件 FAQ 更适合做 RAG，但仍有以下缺口：

1. 缺少真实酒店供应商取消政策。
2. 缺少真实租车供应商保险、押金和证件政策。
3. 缺少真实景点/活动供应商改期和退款政策。
4. 缺少会员权益、投诉处理、人工升级 SOP。
5. 缺少航班异常处理政策，例如延误、取消、备降、行李延误。
6. 缺少政策版本号、生效日期和业务负责人。
7. 缺少 chunk 级 metadata，例如 `allowed_action`、`risk_level`、`requires_confirmation`。

## 8. 后续建议

建议下一步按以下顺序推进：

1. 编写一个 ingestion 脚本，读取 `kb/metadata/policy_index.jsonl`，解析 Markdown front matter，生成 chunk。
2. 给每个 chunk 添加 metadata，支持按 `service` 和 `policy_type` 过滤检索。
3. 把 `tools/retriever_vector.py` 从读取单个 `order_faq.md` 改为读取 `kb/raw/policy/`。
4. 对 `requires_human_review=true` 的政策，在回答中避免给出绝对承诺。
5. 在执行改签、取消、预订类工具前，先检索对应政策并要求用户确认。
6. 后续增加 `kb/processed/chunks.jsonl`，作为可直接进入向量库的中间产物。

## 9. 本次文件变更清单

新增政策文档：

```text
kb/raw/policy/ticket_change_policy.md
kb/raw/policy/refund_policy.md
kb/raw/policy/invoice_policy.md
kb/raw/policy/payment_policy.md
kb/raw/policy/fare_rules.md
kb/raw/policy/booking_platform_policy.md
kb/raw/policy/hotel_policy.md
kb/raw/policy/car_rental_policy.md
kb/raw/policy/excursion_policy.md
```

新增索引：

```text
kb/metadata/policy_index.jsonl
```

新增占位目录文件：

```text
kb/processed/.gitkeep
```

新增报告：

```text
analysis/kb_refactor_report.md
```
