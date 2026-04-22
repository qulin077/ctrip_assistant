# RAG Ingestion Implementation Report

## 1. 新增与修改文件

本次实现聚焦知识库 ingestion、chunk 生成、向量索引和 retriever 接入，没有修改 LangGraph 主流程，也没有改数据库工具逻辑。

新增文件：

- `tools/build_kb_chunks.py`：读取 `kb/metadata/policy_index.jsonl`，解析政策 markdown，生成结构化 chunks。
- `tools/kb_embeddings.py`：提供本地 `local_hash` embedding 和可选 OpenAI-compatible embedding 封装。
- `tools/policy_vector_store.py`：封装本地向量索引的构建、加载、过滤和检索。
- `tools/build_vector_index.py`：从 `kb/processed/chunks.jsonl` 构建持久化向量索引。
- `tools/test_policy_retriever.py`：提供 5 个典型客服问题的检索验证。
- `tools/evaluate_policy_retriever.py`：运行政策检索评测集，输出命中率报告。
- `kb/metadata/retriever_eval_set.jsonl`：政策检索评测集。
- `kb/processed/chunks.jsonl`：结构化 chunk 输出。
- `kb/processed/chunk_stats.md`：chunk 统计。
- `kb/processed/vector_store/chunks.jsonl`：向量索引使用的 chunk 快照。
- `kb/processed/vector_store/vectors.npy`：本地向量矩阵。
- `kb/processed/vector_store/manifest.json`：索引元信息。

修改文件：

- `project_config.py`：新增 KB 路径和 embedding 配置；让 `dotenv` 缺失时不影响本地脚本运行。
- `tools/retriever_vector.py`：从单文件 `order_faq.md` 检索升级为结构化 KB 向量检索。
- `graph_chat/assistant.py`：轻量补充系统规则，要求状态变更类工具调用前先查询政策。
- `.env.example`：配置为 MiniMax OpenAI-compatible LLM，并保留 embedding provider 配置。
- `README.md`：补充 MiniMax、embedding、知识库构建和评测说明。

## 2. Chunk 生成策略

chunk 生成脚本优先按语义结构切分，而不是直接按固定长度切分：

- 先读取 `policy_index.jsonl` 中的政策清单。
- 对每个 markdown 文件解析 YAML front matter。
- 正文按 markdown 标题拆分为 section。
- section 内再按段落、列表块、规则条款拆分。
- 对过长内容在同一 section 内按中文句末符号继续拆分。
- 每个 chunk 保留政策级 metadata 和 section 标题。

每条 chunk 至少包含：

- `chunk_id`
- `policy_id`
- `title`
- `service`
- `policy_type`
- `source`
- `review_status`
- `requires_human_review`
- `file_path`
- `section_title`
- `chunk_text`

在规则明显时，额外补充：

- `risk_level`
- `requires_confirmation`
- `allowed_action`

例如包含“人工处理、待人工确认”的 chunk 会被标记为较高风险；包含“改签、取消、退款、发票”等内容的 chunk 会标记可支持的动作类型。

## 3. Chunk 统计

本次共生成 `86` 个 chunk。

整体统计：

- 平均长度：`95` 字符
- 最短长度：`16` 字符
- 最长长度：`228` 字符

各 policy chunk 数量：

| Policy | Chunks |
| --- | ---: |
| `fare_rules` | 13 |
| `payment_policy` | 11 |
| `refund_policy` | 11 |
| `ticket_change_policy` | 11 |
| `booking_platform_policy` | 10 |
| `car_rental_policy` | 8 |
| `hotel_policy` | 8 |
| `excursion_policy` | 7 |
| `invoice_policy` | 7 |

chunk 数最多的是 `fare_rules`，其次是 `payment_policy`、`refund_policy` 和 `ticket_change_policy`。这说明票价、支付、退款、改签类政策是当前知识库中信息密度最高的部分。

## 4. 向量索引实现

向量索引输出目录：

- `kb/processed/vector_store/`

索引文件：

- `vectors.npy`：chunk 向量矩阵。
- `chunks.jsonl`：与向量一一对应的 chunk 快照。
- `manifest.json`：索引元信息。

当前默认 embedding provider 是 `local_hash`：

- 不依赖网络。
- 不依赖 OpenAI 或 LangChain 包。
- 适合本地验证 ingestion 和 retriever 链路。
- 结果可复现。

正式 embedding 推荐 `BAAI/bge-m3`：

- provider：`sentence_transformers`
- model：`BAAI/bge-m3`
- 适合中文和多语言政策检索。
- 不需要 API Key，但需要安装 `sentence-transformers` 并下载模型。

当前本机尚未安装 `sentence-transformers`，因此本次已落盘的 `kb/processed/vector_store/` 仍使用 `local_hash` provider。安装依赖后可执行以下命令重建正式索引：

```bash
EMBEDDING_PROVIDER=sentence_transformers EMBEDDING_MODEL=BAAI/bge-m3 python3 tools/build_vector_index.py
```

同时保留 OpenAI-compatible embedding 扩展点：

- 可通过 `EMBEDDING_PROVIDER=openai` 切换。
- 使用 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`EMBEDDING_MODEL` 配置。
- `langchain_openai` 仅在选择 openai provider 时懒加载。

## 5. Retriever 升级说明

旧版 `tools/retriever_vector.py` 的问题：

- 直接读取单个 `order_faq.md`。
- 启动时即时生成向量。
- 依赖 `langchain_openai`。
- 返回内容只有文本块，缺少 policy metadata。
- 无法按 `service` 或 `policy_type` 过滤。

新版 retriever：

- 加载 `kb/processed/vector_store/` 中的持久化索引。
- 支持结构化检索接口 `lookup_policy_structured(...)`。
- 保留字符串工具接口 `lookup_policy(query)`，便于后续 LangGraph tool 调用兼容。
- 支持 `top_k`、`service`、`policy_type`。
- 返回 `policy_id`、`title`、`section_title`、`service`、`policy_type`、`requires_human_review`、`similarity` 等 metadata。

当前检索排序使用：

- 向量相似度。
- 少量 query 与 chunk 关键词重合加权。

这样可以在没有外部 embedding 模型的情况下，先保证中文政策检索链路可用。

## 6. 测试结果

测试脚本：

```bash
python3 tools/test_policy_retriever.py
```

当前 5 个样例均命中预期 policy：

| Query | Expected Policy | Result |
| --- | --- | --- |
| 我可以在起飞前多久在线改签？ | `ticket_change_policy` | PASS |
| 如果我取消机票，退款用什么货币？ | `refund_policy` | PASS |
| 电子机票可以当发票吗？ | `invoice_policy` | PASS |
| 酒店入住后还能取消吗？ | `hotel_policy` | PASS |
| 租车开始后还能修改吗？ | `car_rental_policy` | PASS |

新增评测集：

```bash
python3 tools/evaluate_policy_retriever.py
```

当前评测集包含 `18` 个问题，覆盖机票改签、退款、发票、支付、票价、平台展示、酒店、租车、景点政策。使用当前本地索引时：

- top1_accuracy: `1.0`
- top3_accuracy: `1.0`

评测报告输出到：

- `analysis/policy_retriever_eval.md`

## 7. MiniMax 配置

项目仍通过 `ChatOpenAI` 调用 OpenAI-compatible 接口，但默认配置已切到 MiniMax：

```text
MINIMAX_API_KEY=your_minimax_api_key
MINIMAX_BASE_URL=https://api.minimaxi.com/v1
MINIMAX_MODEL=MiniMax-M2.7
```

兼容逻辑：

- 如果填写 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`，会优先使用这些显式配置。
- 如果不填 OpenAI 兼容变量，则自动使用 `MINIMAX_API_KEY`、`MINIMAX_BASE_URL`、`MINIMAX_MODEL`。

这样你只需要把 MiniMax API Key 填进 `.env` 的 `MINIMAX_API_KEY` 即可。

## 8. 当前不足

当前版本已经跑通最小 RAG ingestion 和 retriever，但仍有明显限制：

- `local_hash` embedding 只是本地验证方案，语义理解能力弱于真实 embedding 模型。
- chunk 质量依赖 markdown 小标题和段落规范，后续需要更严格的政策模板。
- 目前还没有 reranker，复杂问题可能需要多 chunk 合并和重排。
- `requires_human_review` 只随政策文档继承，还没有结合具体业务动作做动态风险判断。
- 还没有把 retriever 结果接入 assistant 主提示词或 LangGraph 节点。

## 9. 下一步接入 LangGraph 建议

建议按以下顺序推进：

1. 在现有 assistant tool 列表中继续使用 `lookup_policy`，先不改主流程。
2. 在执行改签、取消、退款、酒店/租车修改前，强制调用政策检索工具。
3. 将 `lookup_policy_structured` 的结果写入 assistant 上下文，让模型能看到 `requires_human_review`。
4. 对 `requires_human_review=true` 或 `risk_level=high` 的政策命中，后续接人工升级节点。
5. 替换 `local_hash` 为正式 embedding 模型，并重新构建 `vector_store`。
6. 增加检索评测集，覆盖退款冲突、发票时限、酒店入住后取消、租车起租后修改等高风险问题。
