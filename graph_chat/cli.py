import uuid

from graph_chat.workflow import create_graph
from tools.init_db import update_dates
from tools.tools_handler import _print_event


def main() -> None:
    graph = create_graph()
    session_id = str(uuid.uuid4())
    update_dates()

    config = {
        "configurable": {
            "passenger_id": "3442 587242",
            "thread_id": session_id,
        }
    }
    printed = set()

    while True:
        question = input("用户：")
        if question.lower() in {"q", "exit", "quit"}:
            print("对话结束。")
            break
        events = graph.stream({"messages": ("user", question)}, config, stream_mode="values")
        for event in events:
            _print_event(event, printed)


if __name__ == "__main__":
    main()
