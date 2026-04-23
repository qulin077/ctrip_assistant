import os
from datetime import datetime

from langchain_community.tools import TavilySearchResults
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from langchain_openai import ChatOpenAI

from graph_chat.state import State
from project_config import (
    MINIMAX_REASONING_SPLIT,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
    TAVILY_API_KEY,
)
from tools.action_guard import (
    book_car_rental,
    book_excursion,
    book_hotel,
    cancel_car_rental,
    cancel_excursion,
    cancel_hotel,
    cancel_ticket,
    update_car_rental,
    update_excursion,
    update_hotel,
    update_ticket_to_new_flight,
)
from tools.car_tools import search_car_rentals
from tools.flights_tools import fetch_user_flight_information, search_flights
from tools.hotels_tools import search_hotels
from tools.retriever_vector import lookup_policy
from tools.trip_tools import search_trip_recommendations


class CtripAssistant:

    # 自定义一个类，表示流程图的一个节点（复杂的）

    def __init__(self, runnable: Runnable):
        """
        初始化助手的实例。
        :param runnable: 可以运行对象，通常是一个Runnable类型的
        """
        self.runnable = runnable

    def __call__(self, state: State, config: RunnableConfig):
        """
        调用节点，执行助手任务
        :param state: 当前工作流的状态
        :param config: 配置: 里面有旅客的信息
        :return:
        """
        while True:
            # 创建了一个无限循环，它将一直执行直到：从 self.runnable 获取的结果是有效的。
            # 如果结果无效（例如，没有工具调用且内容为空或内容不符合预期格式），循环将继续执行，
            configuration = config.get('configurable', {})
            user_id = configuration.get('passenger_id', None)
            state = {**state, 'user_info': user_id}  # 从配置中得到旅客的ID，也追加到state
            result = self.runnable.invoke(state)
            # 如果，runnable执行完后，没有得到一个实际的输出
            if not result.tool_calls and (  # 如果结果中没有工具调用，并且内容为空或内容列表的第一个元素没有"text"，则需要重新提示用户输入。
                    not result.content
                    or isinstance(result.content, list)
                    and not result.content[0].get("text")
            ):
                messages = state["messages"] + [("user", "请提供一个真实的输出作为回应。")]
                state = {**state, "messages": messages}
            else:  # 如果： runnable执行后已经得到，想要的输出，则退出循环
                break
        return {'messages': result}


# 初始化搜索工具，限制结果数量为2
optional_tools = []
if TAVILY_API_KEY:
    os.environ["TAVILY_API_KEY"] = TAVILY_API_KEY
    optional_tools.append(TavilySearchResults(max_results=1))
# 定义工具列表，这些工具将在与用户交互过程中被调用
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


def create_assistant_node() -> CtripAssistant:
    """
    创建一个助手节点
    :return: 返回一个助手节点对象
    """
    llm_kwargs = {}
    if "minimax" in OPENAI_BASE_URL and MINIMAX_REASONING_SPLIT:
        llm_kwargs["extra_body"] = {"reasoning_split": True}

    llm = ChatOpenAI(
        temperature=OPENAI_TEMPERATURE,
        model=OPENAI_MODEL,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        **llm_kwargs,
    )

    # 创建主要助理使用的提示模板
    primary_assistant_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "您是携程瑞士航空公司的客户服务助理。优先使用提供的工具搜索航班、公司政策和其他信息来帮助用户的查询。"
                "搜索时，请坚持不懈。如果第一次搜索没有结果，扩大您的查询范围。"
                "如果搜索为空，在放弃之前扩展您的搜索。\n\n当前用户:\n<User>\n{user_info}\n</User>"
                "\n在执行任何会改变订单或预订状态的操作前，必须先调用 lookup_policy 查询相关政策。"
                "这些操作包括但不限于：机票改签、机票取消、酒店预订/修改/取消、租车预订/修改/取消、景点预订/修改/取消。"
                "所有写操作工具都带有 user_confirmation 参数；如果用户尚未明确确认，请不要填该参数，让工具返回确认提示。"
                "只有用户明确回复“确认、是、好的、同意、继续”等肯定表达后，才可以再次调用写操作工具并传入 user_confirmation。"
                "如果政策命中显示 requires_human_review 为是，或者政策内容提示需要人工处理，请不要直接承诺结果，应说明需要人工确认。"
                "\n当前时间: {time}.",
            ),
            ("placeholder", "{messages}"),
        ]
    ).partial(time=datetime.now())

    runnable = primary_assistant_prompt | llm.bind_tools(part_1_tools)
    return CtripAssistant(runnable)  # 创建一个类的实例
