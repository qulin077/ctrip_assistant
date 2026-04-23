# 模型与系统迭代过程报告

## 1. 迭代主线

这个项目的迭代不是简单“换一个模型”，而是围绕企业客服 Agent 的真实问题逐步升级：

```text
FAQ baseline
  -> 结构化 policy KB
  -> local_hash baseline
  -> BAAI/bge-m3 embedding
  -> query router
  -> escalation policy
  -> 三层评测闭环
```

## 2. V0：local_hash baseline

### 问题

早期需要一个离线可运行 baseline，验证知识库 chunk、向量索引和 retriever 链路是否能跑通。

### 方案

使用 `local_hash` embedding 做 smoke test，不依赖外部模型。

### 结果

| Metric | Value |
| --- | ---: |
| Retrieval Top1 | 0.7895 |
| Retrieval Top3 | 0.9123 |
| MRR | 0.8421 |

### 结论

local_hash 可以验证工程链路，但对同义改写、口语化和跨业务语义不够稳定。

## 3. V1：切换到 BAAI/bge-m3

### 问题

中文政策问答里存在大量同义表达，例如：

- “改签” vs “换日期” vs “往后挪”
- “发票” vs “报销” vs “确认单”
- “退款货币” vs “退到什么币种”

local_hash 更偏词面匹配，语义召回有限。

### 方案

切换到：

```text
sentence_transformers + BAAI/bge-m3
```

### 结果

| Metric | local_hash | BAAI/bge-m3 | Change |
| --- | ---: | ---: | ---: |
| Top1 | 0.7895 | 0.7982 | +0.0087 |
| Top3 | 0.9123 | 0.9386 | +0.0263 |
| MRR | 0.8421 | 0.8640 | +0.0219 |

### 结论

bge-m3 提升了语义召回和排序质量，尤其是 Top3 和 MRR。但 Top1 提升有限，说明瓶颈不只是 embedding，而是业务意图识别和相邻 policy 干扰。

## 4. V1 暴露的新问题

### 多意图

例如：

```text
我想退票，不行的话帮我改签到明天下午
```

这句话同时包含：

- refund_policy
- ticket_change_policy

单次向量检索只能返回一个主 policy，容易摇摆。

### 相邻 policy

例如：

- 退款 vs 支付
- 发票 vs 发票支付
- 酒店取消 vs 泛化退款
- 行程单 vs 景点行程

这些词在中文里天然重叠，单靠 embedding 很难稳定区分。

### 过度升级

Guardrail 早期根据 top3 chunk 中是否包含 `risk_level=high` 来创建工单。结果普通酒店/租车预订也可能因为 top3 里混入高风险 chunk 被过度升级。

## 5. V2：Query Router + Escalation Policy

### 解决多意图与相邻 policy

新增 `tools/escalation_policy.py` 中的 `infer_route_hint()`：

- 根据关键词推断 `service`
- 推断 `policy_type`
- 识别是否多意图

检索策略改为：

```text
filtered_top1
  + broad_top3_fallback
```

也就是：

1. 用业务过滤抢第一条，提高 Top1。
2. 再用全局召回补足候选，避免 Top3 召回下降。

### 解决 handoff 与过度升级

新增独立 `should_create_service_ticket()` 和 `should_handoff_policy_question()`：

- refund / invoice 等待人工确认政策会升级。
- 第三方、团体、入住后、起租后、活动开始后、全额退等高风险语言会升级。
- 普通预订/取消不会因为 top3 里混入高风险 chunk 就自动建工单。

## 6. V2 结果

| Metric | V1 bge-m3 | V2 Router + Escalation | Change |
| --- | ---: | ---: | ---: |
| Retrieval Top1 | 0.7982 | 0.8596 | +0.0614 |
| Retrieval Top3 | 0.9386 | 1.0000 | +0.0614 |
| MRR | 0.8640 | 0.9269 | +0.0629 |
| Guardrail Pass | 0.7500 | 1.0000 | +0.2500 |
| Unsafe Execution | 0.0000 | 0.0000 | 0 |
| E2E Pass | 0.4333 | 1.0000 | +0.5667 |

## 7. 学习能力与工程能力体现

这个迭代过程可以体现：

1. **先做 baseline**
   不是一上来追求复杂模型，而是先用 local_hash 跑通可复现实验。

2. **用指标发现问题**
   bge-m3 提升了 Top3，但 Top1 仍受多意图影响；guardrail 安全但工单触发过度保守。

3. **不是盲目换模型**
   发现瓶颈后没有继续堆 embedding，而是增加 query router 和 escalation policy。

4. **工程化落地**
   改动不是写在 prompt 里，而是独立模块、稳定接口、可测试、可复用。

5. **评测闭环**
   每次改动后重新跑 Retrieval、Guardrail、E2E 三层评测，用数字验证收益和副作用。

## 8. 面试表达

可以这样讲：

> 我一开始用 local_hash 做离线 baseline，确保 RAG ingestion 和 vector store 可以复现。随后切换到 BAAI/bge-m3，Top3 从 0.9123 提升到 0.9386，MRR 从 0.8421 提升到 0.8640。但我发现 Top1 提升不大，错误主要来自多意图和相邻 policy，而不是 embedding 本身。于是我加了 query router，用业务字段做 filtered top1，再用 broad retrieval 保留 top3 召回，最终 Top1 提升到 0.8596，Top3 到 1.0。与此同时，我把 service ticket 判断从 chunk risk 中拆出为独立 escalation policy，使 guardrail pass rate 从 0.75 提升到 1.0，E2E pass rate 从 0.4333 提升到 1.0，同时 unsafe execution rate 始终保持 0。

