# ctrip_assistant 项目从头到尾讲解

这个项目是一个“携程/瑞士航空客户服务助手”示例项目。它不是单纯的 RAG 问答机器人，而是一个 LangGraph 工具调用型智能体：用户在命令行里提出旅行相关需求，LLM 根据问题决定是否调用工具，然后工具去 SQLite 数据库里查航班、改签、退票、订酒店、订租车、订景点，或者从本地 FAQ 文档中检索政策信息，最后再由 LLM 汇总成自然语言回答。

一句话概括：

```text
用户问题 -> LangGraph assistant 节点 -> LLM 判断是否调用工具 -> SQLite/FAQ/网络搜索工具执行 -> 工具结果回到 LLM -> 输出回答
```

## 1. 项目结构

```text
ctrip_assistant/
├── PROJECT_EXPLANATION.md       # 本说明文档
├── order_faq.md                 # 航司订单/支付/改签/发票 FAQ 文档
├── travel_new.sqlite            # 运行时使用的 SQLite 旅行数据库
├── travel2.sqlite               # 备份数据库，每次测试前复制到 travel_new.sqlite
├── graph_chat/
│   ├── 第一个流程图.py           # 主入口：构建并运行 LangGraph 对话流程
│   ├── assistant.py             # Assistant 节点、LLM、工具列表
│   ├── state.py                 # LangGraph 状态定义
│   ├── draw_png.py              # 绘制流程图
│   ├── log_utils.py             # 日志工具
│   └── graph1.png               # 已生成的流程图图片
├── tools/
│   ├── init_db.py               # 重置数据库并把示例日期更新到当前时间附近
│   ├── flights_tools.py         # 航班查询、改签、退票工具
│   ├── hotels_tools.py          # 酒店查询、预订、修改、取消工具
│   ├── car_tools.py             # 租车查询、预订、修改、取消工具
│   ├── trip_tools.py            # 景点/旅行推荐查询、预订、修改、取消工具
│   ├── retriever_vector.py      # order_faq.md 的内存向量检索工具
│   ├── tools_handler.py         # ToolNode fallback 和输出打印
│   └── location_trans.py        # 中文城市名转英文城市名
└── logs/                        # 日志目录
```

核心代码主要集中在两块：

- `graph_chat/`：负责 LangGraph 对话流程。
- `tools/`：负责所有可被 LLM 调用的业务工具。

## 2. 数据集是什么

这个项目的数据集有两类：结构化数据库和非结构化 FAQ 文档。

## 2.1 SQLite 旅行数据库

项目中有两个 SQLite 文件：

```text
travel_new.sqlite
travel2.sqlite
```

两个数据库的表结构和行数一致。它们的用途不同：

- `travel2.sqlite`：备份库，相当于原始数据快照。
- `travel_new.sqlite`：运行时工作库，工具实际读写这个数据库。

`tools/init_db.py` 现在通过 `project_config.py` 读取数据库路径：

```python
local_file = str(TRAVEL_DB_PATH)
backup_file = str(TRAVEL_DB_BACKUP_PATH)
```

每次主流程启动时，`update_dates()` 会先用 `travel2.sqlite` 覆盖 `travel_new.sqlite`，然后把航班和预订日期整体平移到当前时间附近，这样测试“未来航班”“3 小时内不可改签”等规则时不会因为原始数据过期而失效。

数据库表和行数如下：

```text
aircrafts_data          9
airports_data           115
boarding_passes         579686
bookings                262788
car_rentals             10
flights                 33121
hotels                  10
seats                   1339
ticket_flights          1045726
tickets                 366733
trip_recommendations    10
```

这些表可以分成几组：

- 航空基础数据：`aircrafts_data`、`airports_data`、`seats`
- 航班业务数据：`flights`、`tickets`、`ticket_flights`、`boarding_passes`、`bookings`
- 旅行扩展服务：`hotels`、`car_rentals`、`trip_recommendations`

其中 `flights` 表结构是：

```text
flight_id
flight_no
scheduled_departure
scheduled_arrival
departure_airport
arrival_airport
status
aircraft_code
actual_departure
actual_arrival
```

`tickets` 表结构是：

```text
ticket_no
book_ref
passenger_id
```

`ticket_flights` 表结构是：

```text
ticket_no
flight_id
fare_conditions
amount
```

酒店、租车和景点推荐是较小的演示数据集。例如：

```text
hotels: id, name, location, price_tier, checkin_date, checkout_date, booked
car_rentals: id, name, location, price_tier, start_date, end_date, booked
trip_recommendations: id, name, location, keywords, details, booked
```

所以，这个 SQLite 数据库是项目最主要的结构化数据集，用来模拟真实旅行系统里的航班订单、机票、登机牌、酒店、租车和景点推荐。

## 2.2 航司 FAQ 文档

第二个数据集是：

```text
order_faq.md
```

它是一份中文航空公司订单政策 FAQ 文档，内容主题包括：

- 发票问题
- 预订和取消
- 预订平台
- 订购发票
- 信用卡支付
- 卡片安全
- 按发票支付
- 欧洲票价概念

这份文档主要用于回答“政策类”问题。例如：

- 如何改签？
- 起飞前多久可以在线改签？
- 什么情况下不能改签？
- 退款用什么货币？
- 电子机票能不能作为发票？
- 信用卡 3-D Secure 是什么？

代码里把它作为一个小型本地向量知识库使用。

## 3. 项目的入口

主入口是：

```text
graph_chat/第一个流程图.py
```

它做了几件事：

1. 创建 LangGraph 状态图。
2. 添加 `assistant` 节点。
3. 添加 `tools` 节点。
4. 设置 `assistant -> tools -> assistant` 的循环。
5. 创建 MemorySaver 保存会话状态。
6. 调用 `update_dates()` 重置数据库时间。
7. 固定一个测试乘客 ID。
8. 进入命令行循环，等待用户输入。

核心代码是：

```python
builder = StateGraph(State)
builder.add_node('assistant', create_assistant_node())
builder.add_node('tools', create_tool_node_with_fallback(part_1_tools))
builder.add_edge(START, "assistant")
builder.add_conditional_edges("assistant", tools_condition)
builder.add_edge("tools", "assistant")
graph = builder.compile(checkpointer=memory)
```

用户输入后：

```python
events = graph.stream({'messages': ('user', question)}, config, stream_mode='values')
```

这会让 LangGraph 以流式事件方式执行整个对话流程。

## 4. 状态 State

状态定义在 `graph_chat/state.py`：

```python
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
```

它只有一个字段：

```text
messages
```

`add_messages` 的作用是：每个节点返回的新消息都会追加到历史消息列表里，而不是覆盖原来的消息。

因此一次工具调用过程会形成类似这样的消息历史：

```text
HumanMessage: 用户问“帮我查一下我的航班”
AIMessage: LLM 决定调用 fetch_user_flight_information
ToolMessage: 工具返回该乘客的航班数据
AIMessage: LLM 根据工具结果回答用户
```

## 5. Assistant 节点

Assistant 节点在 `graph_chat/assistant.py`。

核心类是：

```python
class CtripAssistant:
```

它包装了一个 LangChain `Runnable`，并实现了 `__call__()`，因此可以作为 LangGraph 节点使用。

## 5.1 从 config 中取乘客 ID

主入口里配置了：

```python
config = {
    "configurable": {
        "passenger_id": "3442 587242",
        "thread_id": session_id,
    }
}
```

Assistant 每次执行时会取出这个乘客 ID：

```python
configuration = config.get('configurable', {})
user_id = configuration.get('passenger_id', None)
state = {**state, 'user_info': user_id}
```

这个 `user_info` 会进入系统提示词，让模型知道当前服务对象是谁。航班工具也会从同一个 config 中读取 `passenger_id`，确保只能查改当前用户自己的机票。

## 5.2 防止 LLM 空输出

`CtripAssistant.__call__()` 里有一个 `while True`：

```python
while True:
    result = self.runnable.invoke(state)
    if not result.tool_calls and (not result.content ...):
        messages = state["messages"] + [("user", "请提供一个真实的输出作为回应。")]
        state = {**state, "messages": messages}
    else:
        break
```

含义是：如果模型没有调用工具，也没有给出有效文本，就追加一句“请提供一个真实的输出作为回应。”，让模型重新生成。

## 5.3 LLM 和系统提示词

`create_assistant_node()` 创建 LLM：

```python
llm = ChatOpenAI(
    temperature=OPENAI_TEMPERATURE,
    model=OPENAI_MODEL,
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_BASE_URL
)
```

系统提示词大意是：

```text
你是携程瑞士航空公司的客户服务助理。
优先使用提供的工具搜索航班、公司政策和其他信息来帮助用户查询。
搜索时要坚持，如果第一次搜索没有结果，要扩大查询范围。
当前用户是 {user_info}
当前时间是 {time}
```

然后将 LLM 和工具绑定：

```python
runnable = primary_assistant_prompt | llm.bind_tools(part_1_tools)
```

这一步非常关键：绑定工具后，模型不只是生成文本，还可以生成结构化工具调用请求。

## 6. 工具列表

`assistant.py` 中的 `part_1_tools` 是整个助手能调用的工具集合：

```python
part_1_tools = [
    *optional_tools,
    fetch_user_flight_information,
    search_flights,
    lookup_policy,
    update_ticket_to_new_flight,
    cancel_ticket,
    search_car_rentals,
    book_car_rental,
    update_car_rental,
    cancel_car_rental,
    search_hotels,
    book_hotel,
    update_hotel,
    cancel_hotel,
    search_trip_recommendations,
    book_excursion,
    update_excursion,
    cancel_excursion,
]
```

可以分为五类：

```text
网络搜索：TavilySearchResults
政策检索：lookup_policy
航班工具：fetch_user_flight_information, search_flights, update_ticket_to_new_flight, cancel_ticket
租车工具：search_car_rentals, book_car_rental, update_car_rental, cancel_car_rental
酒店工具：search_hotels, book_hotel, update_hotel, cancel_hotel
景点工具：search_trip_recommendations, book_excursion, update_excursion, cancel_excursion
```

## 7. Graph 流程是什么

这个项目的 LangGraph 流程非常短，但很典型。

流程图可以理解为：

```text
START
  ↓
assistant
  ↓
是否有 tool_calls？
  ├── 没有：结束本轮，直接回复用户
  └── 有：进入 tools 节点
          ↓
       执行工具
          ↓
       工具结果追加到 messages
          ↓
       回到 assistant
          ↓
       LLM 读取工具结果并继续判断
```

实际边定义是：

```python
builder.add_edge(START, "assistant")
builder.add_conditional_edges("assistant", tools_condition)
builder.add_edge("tools", "assistant")
```

`tools_condition` 是 LangGraph 预置条件函数。它会检查 assistant 输出的 AIMessage 里有没有 `tool_calls`：

- 有工具调用：跳转到 `tools`。
- 没有工具调用：结束。

因此，这个图天然支持多次工具调用。例如用户说：

```text
我想把我的航班改到明天下午，并帮我订苏黎世的酒店
```

可能流程是：

```text
assistant
  -> fetch_user_flight_information
  -> assistant
  -> search_flights
  -> assistant
  -> lookup_policy
  -> assistant
  -> update_ticket_to_new_flight
  -> assistant
  -> search_hotels
  -> assistant
  -> book_hotel
  -> assistant
  -> 最终回答
```

## 8. 工具错误处理

`tools/tools_handler.py` 创建了带 fallback 的工具节点：

```python
return ToolNode(tools).with_fallbacks(
    [RunnableLambda(handle_tool_error)],
    exception_key="error"
)
```

如果工具执行报错，`handle_tool_error()` 会把错误包装成 `ToolMessage`：

```python
ToolMessage(
    content=f"错误: {repr(error)}\n请修正您的错误。",
    tool_call_id=tc["id"],
)
```

这样 LLM 能看到工具错误，并有机会修正参数后重新调用工具。

例如模型调用酒店工具时传错字段，工具节点不会让整个程序直接崩掉，而是把错误反馈给模型。

## 9. 航班工具

航班工具在 `tools/flights_tools.py`。

## 9.1 查询当前用户航班

```python
fetch_user_flight_information(config)
```

它从 config 中读取：

```python
passenger_id = configuration.get("passenger_id", None)
```

然后查询多张表：

```sql
tickets
JOIN ticket_flights
JOIN flights
JOIN boarding_passes
```

返回字段包括：

```text
ticket_no
book_ref
flight_id
flight_no
departure_airport
arrival_airport
scheduled_departure
scheduled_arrival
seat_no
fare_conditions
```

这个工具用于回答：

- 我的航班是什么？
- 我的座位是多少？
- 我的票号是什么？
- 我从哪里飞到哪里？

## 9.2 搜索航班

```python
search_flights(
    departure_airport=None,
    arrival_airport=None,
    start_time=None,
    end_time=None,
    limit=20
)
```

它动态拼 SQL：

```sql
SELECT * FROM flights WHERE 1 = 1
```

然后按出发机场、到达机场、起飞时间范围过滤。

## 9.3 改签机票

```python
update_ticket_to_new_flight(ticket_no, new_flight_id, config=config)
```

它做了多层校验：

1. config 中必须有 `passenger_id`。
2. 新航班 ID 必须存在。
3. 新航班起飞时间距离当前时间不能少于 3 小时。
4. 原机票必须存在。
5. 当前乘客必须是这张机票的拥有者。
6. 更新 `ticket_flights.flight_id`。

这比简单更新数据库更安全，因为它避免用户修改别人的机票。

## 9.4 取消机票

```python
cancel_ticket(ticket_no, config=config)
```

它同样检查：

1. config 中必须有乘客 ID。
2. 机票必须存在。
3. 当前乘客必须拥有这张票。

通过后删除：

```sql
DELETE FROM ticket_flights WHERE ticket_no = ?
```

注意：这里删除的是 `ticket_flights` 中的机票航段记录，不是完整删除 `tickets` 表里的票号。

## 10. 酒店工具

酒店工具在 `tools/hotels_tools.py`。

## 10.1 查询酒店

```python
search_hotels(location=None, name=None)
```

它会先调用：

```python
location = transform_location(location)
```

把中文城市名转成英文，比如：

```text
苏黎世 -> Zurich
巴塞尔 -> Basel
```

然后查询：

```sql
SELECT * FROM hotels WHERE 1=1
```

按 `location LIKE ?` 和 `name LIKE ?` 过滤。

## 10.2 预订酒店

```python
book_hotel(hotel_id)
```

执行：

```sql
UPDATE hotels SET booked = 1 WHERE id = ?
```

## 10.3 修改酒店

```python
update_hotel(hotel_id, checkin_date=None, checkout_date=None)
```

更新入住和退房日期。

## 10.4 取消酒店

```python
cancel_hotel(hotel_id)
```

执行：

```sql
UPDATE hotels SET booked = 0 WHERE id = ?
```

## 11. 租车工具

租车工具在 `tools/car_tools.py`。

它和酒店工具结构几乎一样：

```text
search_car_rentals     查询租车
book_car_rental        预订租车
update_car_rental      修改租车开始/结束日期
cancel_car_rental      取消租车
```

查询时同样支持中文城市名转换：

```python
location = transform_location(location)
```

预订和取消本质是更新 `car_rentals.booked` 字段。

## 12. 景点/旅行推荐工具

景点工具在 `tools/trip_tools.py`。

## 12.1 查询推荐

```python
search_trip_recommendations(location=None, name=None, keywords=None)
```

支持按：

- 城市
- 名称
- 关键词

过滤。关键词支持逗号拆分：

```python
keyword_list = keywords.split(",")
keyword_conditions = " OR ".join(["keywords LIKE ?" for _ in keyword_list])
```

例如用户说“苏黎世有什么历史建筑推荐？”，工具可以按 `location=Zurich` 和 `keywords=history,architecture` 查询。

## 12.2 预订、修改、取消推荐

```text
book_excursion(recommendation_id)
update_excursion(recommendation_id, details)
cancel_excursion(recommendation_id)
```

预订和取消也是修改 `booked` 字段，更新则修改 `details` 字段。

## 13. 政策 FAQ 检索

政策检索在 `tools/retriever_vector.py`。

它读取：

```python
with open(ORDER_FAQ_PATH, encoding='utf8') as f:
    faq_text = f.read()
```

然后按二级标题切分：

```python
docs = [{"page_content": txt} for txt in re.split(r"(?=\n##)", faq_text)]
```

接着用 Embedding 模型把每段 FAQ 转成向量：

```python
embeddings_model.embed_documents([...])
```

项目里定义了一个非常轻量的向量检索器：

```python
class VectorStoreRetriever:
```

查询时：

1. 把用户问题转成 query embedding。
2. 用点积计算 query 和所有 FAQ 段落的相似度。
3. 取分数最高的 Top-K。

核心代码是：

```python
scores = np.array(embed) @ self._arr.T
top_k_idx = np.argpartition(scores, -k)[-k:]
```

对外暴露的工具是：

```python
@tool
def lookup_policy(query: str) -> str:
```

工具描述里明确说：

```text
查询公司政策，检查某些选项是否允许。
在进行航班变更或其他'写'操作之前使用此函数。
```

所以模型在执行改签、取消等操作前，理论上应该先调用 `lookup_policy()` 查询规则。

## 14. 网络搜索工具

`assistant.py` 里还加入了 Tavily 搜索：

```python
optional_tools = []
if TAVILY_API_KEY:
    os.environ["TAVILY_API_KEY"] = TAVILY_API_KEY
    optional_tools.append(TavilySearchResults(max_results=1))
```

这个工具用于回答本地数据库和 FAQ 中没有的信息。

它需要 Tavily API Key；整理后已经改成可选工具，不配置 `TAVILY_API_KEY` 时不会启用。

## 15. 城市名转换

`tools/location_trans.py` 用来把中文城市名转换成英文：

```python
city_dict = {
    '北京': 'Beijing',
    '上海': 'Shanghai',
    '广州': 'Guangzhou',
    '深圳': 'Shenzhen',
    '成都': 'Chengdu',
    '杭州': 'Hangzhou',
    '巴塞尔': 'Basel',
    '苏黎世': 'Zurich',
}
```

酒店、租车、景点工具里的数据库城市名是英文，所以如果用户输入“苏黎世酒店”，工具需要把“苏黎世”转成 `Zurich` 才能查到。

注意：这个函数没有处理 `None`，如果工具传入 `location=None`，执行：

```python
for char in chinese_city
```

会报错。实际使用时 LLM 通常会传具体城市，但从代码健壮性看，这里可以加一层空值判断。

## 16. 一次完整流程示例

假设用户输入：

```text
帮我查一下我的航班信息
```

流程是：

```text
1. 命令行收到用户问题。
2. graph.stream() 把用户消息加入 State.messages。
3. assistant 节点运行。
4. LLM 看到用户要查航班，生成工具调用 fetch_user_flight_information。
5. tools 节点执行该工具。
6. 工具从 config 中取 passenger_id = "3442 587242"。
7. 工具查询 tickets、ticket_flights、flights、boarding_passes。
8. 工具返回当前乘客的航班、座位、票号等信息。
9. 图从 tools 回到 assistant。
10. LLM 读取工具结果，组织成中文回答。
11. 如果不再需要工具，流程结束。
```

如果用户输入：

```text
我想改签到明天从苏黎世出发的航班
```

可能流程是：

```text
1. assistant 判断需要先查用户当前机票。
2. 调用 fetch_user_flight_information。
3. 回到 assistant。
4. 调用 search_flights 搜索候选航班。
5. 回到 assistant。
6. 调用 lookup_policy 查询改签规则。
7. 回到 assistant。
8. 如果规则允许，调用 update_ticket_to_new_flight。
9. 回到 assistant。
10. 输出改签结果。
```

如果用户输入：

```text
帮我订一个巴塞尔的酒店
```

可能流程是：

```text
1. assistant 调用 search_hotels(location="巴塞尔")。
2. search_hotels 通过 transform_location 转成 Basel。
3. 查询 hotels 表。
4. assistant 根据候选酒店询问用户选择，或直接调用 book_hotel。
5. book_hotel 把对应酒店 booked 改为 1。
6. assistant 输出预订成功信息。
```

## 17. 和普通 RAG 项目的区别

前面分析过的 `sales_chatbot` 更像典型 RAG：

```text
用户问题 -> 向量库检索 -> LLM 回答
```

这个 `ctrip_assistant` 更像工具智能体：

```text
用户问题 -> LLM 决策 -> 调用业务工具 -> 数据库读写/FAQ 检索/网络搜索 -> LLM 总结
```

它当然也包含 RAG 部分，也就是 `order_faq.md` 的向量检索；但它的重点不是只做文档问答，而是让 LLM 通过工具操作业务系统。

## 18. 运行方式

推荐运行方式是：

```bash
cd /Users/qulin/Desktop/AI/ai\ project/ctrip_assistant
python -m graph_chat.第一个流程图
```

运行前需要复制 `.env.example` 为 `.env`，并填入 OpenAI 兼容接口的 API Key。`TAVILY_API_KEY` 是可选项，不填时不会启用网络搜索工具。

## 19. 当前代码中值得注意的问题

## 19.1 配置已经抽到 `.env`

原代码中 `graph_chat/assistant.py` 和 `tools/retriever_vector.py` 存在硬编码 API Key。整理后已经改成通过 `project_config.py` 统一读取 `.env`：

```python
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
```

这样上传 GitHub 时不会把真实密钥放进代码。

## 19.2 路径已经集中管理

原代码里多个工具使用 `../travel_new.sqlite` 和 `../order_faq.md`，比较依赖启动目录。整理后新增 `project_config.py`，统一用项目根目录推导路径：

```python
PROJECT_ROOT = Path(__file__).resolve().parent
TRAVEL_DB_PATH = PROJECT_ROOT / "travel_new.sqlite"
ORDER_FAQ_PATH = PROJECT_ROOT / "order_faq.md"
```

## 19.3 `travel_new.sqlite` 会被重置

主入口启动时会调用：

```python
update_dates()
```

这会用 `travel2.sqlite` 覆盖 `travel_new.sqlite`。所以你在一次测试里做的改签、订酒店、订租车，下一次启动会被重置。

这对教学和演示很好，因为每次都有干净数据；但如果要做真实系统，不能这样设计。

## 19.4 `location_trans` 已补充空值判断

整理后已经加了：

```python
if not chinese_city:
    return chinese_city
```

## 19.5 工具修改操作缺少二次确认

例如：

```text
book_hotel
cancel_ticket
update_ticket_to_new_flight
```

这些都是写操作。当前流程中，LLM 可以直接调用它们。真实产品里最好在执行前增加用户确认节点，例如：

```text
我将为你取消票号 xxx 的航班，是否确认？
```

## 19.6 FAQ 向量库每次导入都会重建

`retriever_vector.py` 在模块导入时就会读取 FAQ 并调用 Embedding：

```python
retriever = VectorStoreRetriever.from_docs(docs)
```

这意味着每次启动都会重新请求 Embedding 接口，速度慢，也消耗费用。可以把向量缓存到本地，例如 FAISS、Chroma，或者保存 numpy 向量文件。

## 20. 总结

`ctrip_assistant` 是一个旅行客服工具智能体项目，核心特点是：

- 使用 LangGraph 编排对话流程。
- 使用 ChatOpenAI 兼容接口作为工具调用模型。
- 使用 SQLite 模拟旅行订单业务数据库。
- 使用工具函数完成航班、酒店、租车、景点的查订改退。
- 使用 `order_faq.md` + Embedding 做本地政策 FAQ 检索。
- 使用 Tavily 做网络搜索兜底。
- 使用 MemorySaver 保存同一线程内的消息状态。

它的数据集包括：

```text
1. travel_new.sqlite / travel2.sqlite
   旅行业务数据库，包含航班、机票、订单、登机牌、酒店、租车、景点推荐等表。

2. order_faq.md
   航司订单、支付、发票、改签、退票等政策 FAQ 文档。
```

它的主流程是：

```text
用户输入
  -> assistant 节点
  -> LLM 根据提示词和工具描述决定是否调用工具
  -> tools 节点执行数据库查询/更新、FAQ 检索或网络搜索
  -> 工具结果返回 assistant
  -> LLM 继续调用工具或生成最终回答
  -> 命令行输出
```

所以这个项目最值得关注的不是“向量检索本身”，而是“LLM 如何通过 LangGraph 调用多个业务工具，完成真实客服任务”。
