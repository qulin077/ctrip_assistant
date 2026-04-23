# Frontend and Backend Implementation Report

## 1. 新增文件

- `app/__init__.py`
- `app/api.py`
- `frontend/streamlit_app.py`
- `tools/test_api.py`
- `analysis/frontend_backend_report.md`

## 2. 后端设计

后端使用 FastAPI，入口：

```bash
uvicorn app.api:app --reload --port 8000
```

主要接口：

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | 健康检查、数据库存在性、受保护写工具数量 |
| GET | `/api/actions` | 列出受保护写操作 |
| POST | `/api/policy/search` | 结构化政策检索 |
| POST | `/api/actions/execute` | 执行 guarded action |
| GET | `/api/audit/recent` | 查看最近写操作审计日志 |
| GET | `/api/service-tickets` | 查看人工工单 |
| GET | `/api/analytics/summary` | 获取核心业务和 guardrail KPI |
| POST | `/api/analytics/report` | 重新生成业务分析报告 |

后端没有绕过现有业务逻辑，而是复用：

- `lookup_policy_structured`
- `tools/action_guard.py`
- `tools/audit_store.py`
- `tools/customer_analytics.py`

因此 API 调用写操作时，仍然会强制经过：

```text
policy lookup -> confirmation gate -> audit log -> optional service ticket -> original tool
```

## 3. 前端设计

前端使用 Streamlit，入口：

```bash
streamlit run frontend/streamlit_app.py
```

页面包含 4 个 tab：

- `Policy Search`：按 query、service、policy_type 检索政策。
- `Guarded Action`：演示取消机票、改签、酒店/租车/景点写操作的确认门。
- `Audit`：展示最近审计日志和人工工单。
- `Analytics`：展示 `analysis/customer_service_analytics.md` 报告内容。

前端默认连接：

```text
http://127.0.0.1:8000
```

可以在侧边栏修改 API base URL。

## 4. 面试展示价值

这次补齐后，项目可以展示完整闭环：

```text
业务数据库
  -> RAG 政策检索
  -> Guarded write actions
  -> FastAPI service layer
  -> Streamlit dashboard
  -> Audit / service ticket / analytics
```

适合讲：

- 业务数据建模
- RAG 检索评测
- 工具调用和风险控制
- 审计日志和人工升级
- 客服运营指标分析
- 前后端系统集成

## 5. 验证结果

已运行：

```bash
python -m py_compile app/api.py frontend/streamlit_app.py tools/test_api.py
python tools/test_api.py
python tools/test_guarded_actions.py
python tools/evaluate_policy_retriever.py
python tools/customer_analytics.py
```

结果：

- API health 正常。
- Policy search 命中 `hotel_policy`。
- Guarded action 未确认时不会执行写操作。
- 受保护写工具数量：`11`。
- Retriever eval：Top-1 `1.0`，Top-3 `1.0`。
- Analytics report 已生成。

## 6. 当前限制

- Streamlit 前端是 demo dashboard，不是生产级权限系统。
- API 当前没有登录鉴权，默认用于本地面试展示。
- Guarded action 的多轮确认仍依赖工具参数 `user_confirmation`。
- 人工工单目前是 SQLite 表，还没有完整客服后台流转页面。

## 7. 下一步建议

- 增加 `conversation_summaries` 表。
- 在前端增加“会话摘要”和“工单处理”页面。
- 加入 API token 或 session auth。
- 增加 Dockerfile 或一键启动脚本。
