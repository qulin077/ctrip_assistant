# Ctrip Assistant

一个基于 LangGraph 的旅行客服小助手 Agent 示例。它可以通过工具调用查询和修改旅行数据库，并使用本地 FAQ 文档做政策检索。

## 功能

- 查询当前乘客航班、票号、座位和航班时间
- 搜索航班并执行改签
- 取消机票
- 查询、预订、修改、取消酒店
- 查询、预订、修改、取消租车
- 查询、预订、修改、取消旅行推荐
- 检索 `order_faq.md` 中的订单、支付、发票、退改签政策
- 可选 Tavily 网络搜索兜底

## 数据集

项目依赖两个本地 SQLite 数据库：

- `travel2.sqlite`：原始备份数据库
- `travel_new.sqlite`：运行时工作数据库

这两个文件各约 109MB，超过 GitHub 普通文件 100MB 限制，因此默认不纳入 Git。运行项目前需要把它们放在项目根目录。

另一个知识库文件是 `order_faq.md`，用于政策类 RAG 检索。

## 配置

复制环境变量示例：

```bash
cp .env.example .env
```

然后填写：

```text
OPENAI_API_KEY=your_openai_compatible_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o
TAVILY_API_KEY=
```

`TAVILY_API_KEY` 是可选项；不填时不会启用网络搜索工具。

## 安装

```bash
pip install -r requirements.txt
```

## 运行

推荐从项目根目录以模块方式运行：

```bash
python -m graph_chat.第一个流程图
```

程序会先用 `travel2.sqlite` 重置 `travel_new.sqlite`，再进入命令行对话。

退出命令：

```text
q
exit
quit
```

## 项目说明

完整代码讲解见：

```text
PROJECT_EXPLANATION.md
```
