from langgraph.checkpoint.memory import MemorySaver
from langgraph.constants import START
from langgraph.graph import StateGraph
from langgraph.prebuilt import tools_condition

from graph_chat.assistant import create_assistant_node, part_1_tools
from graph_chat.state import State
from tools.tools_handler import create_tool_node_with_fallback


def create_graph():
    builder = StateGraph(State)
    builder.add_node("assistant", create_assistant_node())
    builder.add_node("tools", create_tool_node_with_fallback(part_1_tools))
    builder.add_edge(START, "assistant")
    builder.add_conditional_edges("assistant", tools_condition)
    builder.add_edge("tools", "assistant")
    return builder.compile(checkpointer=MemorySaver())
