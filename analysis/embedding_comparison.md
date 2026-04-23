# Embedding Comparison

## 1. 对比目标

本次将默认政策检索 embedding 从离线基线 `local_hash` 切换为：

```text
EMBEDDING_PROVIDER=sentence_transformers
EMBEDDING_MODEL=BAAI/bge-m3
```

对比同一套 `kb/metadata/retriever_eval_set_v2.jsonl`，共 114 条问题。

## 2. 总体指标

| Version | Provider / Strategy | Top1 | Top3 | MRR | Filtered Top1 |
| --- | --- | ---: | ---: | ---: | ---: |
| V0 | `local_hash` | 0.7895 | 0.9123 | 0.8421 | 1.0 |
| V1 | `sentence_transformers` + `BAAI/bge-m3` | 0.7982 | 0.9386 | 0.8640 | 1.0 |
| V2 | `BAAI/bge-m3` + query router + broad fallback | 0.8596 | 1.0 | 0.9269 | 1.0 |

## 3. 结论

- `BAAI/bge-m3` 的 Top3 和 MRR 更好，说明语义召回排序更稳，适合 RAG 候选文档召回。
- 单纯换 embedding 后 Top1 只小幅提升，说明主要瓶颈已不只是 embedding，而是多意图 query、相邻 policy 和 metadata 路由。
- 加入 query router 后，Top1 提升到 0.8596，同时 broad fallback 将 Top3 提升到 1.0。
- `filtered_top1_accuracy=1.0` 说明如果业务流程显式传入 `service` / `policy_type`，检索可靠性明显高于纯自然语言裸检索。

## 4. 变化观察

`BAAI/bge-m3` 改善了直接问法、风险问法和部分改写问法。query router 进一步改善了以下问题，但多意图仍是最难类型：

- “我想退票，不行的话帮我改签到明天下午”仍容易在 `refund_policy` 和 `ticket_change_policy` 之间切换。
- “先看看酒店能不能取消，再帮我改租车日期”仍容易受到第二个意图影响。
- “行程单能报销吗？”容易被“行程”误导到景点/行程政策。

## 5. 工程说明

当前环境是 macOS x86，PyTorch wheel 最高可安装到 2.2.2；新版本 transformers 会要求 `torch>=2.6` 才允许走 `torch.load`。由于 `BAAI/bge-m3` 当前没有 safetensors 权重，本项目在 `tools/kb_embeddings.py` 中加入了一个窄范围本地兼容 fallback，用于在该环境中加载官方 `BAAI/bge-m3` 权重。

生产环境建议：

- 使用支持 `torch>=2.6` 的 Python / OS / CPU 架构。
- 或使用提供 safetensors / ONNX 的 embedding 模型。
- 将 embedding 服务独立部署，API 层只依赖 embedding endpoint。

## 6. 下一步

1. 增加 query router，先判断主服务和主政策类型，再做 filtered retrieval。
2. 对多意图 query 做拆分检索，每个意图独立召回 policy。
3. 为 `invoice_policy`、`booking_platform_policy` 增加更多别名词和 metadata，减少相邻 policy 误命中。
