import uuid

from graph_chat.workflow import create_graph
from tools.init_db import update_dates
from tools.tools_handler import _print_event

graph = create_graph()

#
# draw_graph(graph, 'graph1.png')

session_id = str(uuid.uuid4())
update_dates()  # 每次测试的时候：保证数据库是全新的，保证，时间也是最近的时间

# 配置参数，包含乘客ID和线程ID
config = {
    "configurable": {
        # passenger_id用于我们的航班工具，以获取用户的航班信息
        "passenger_id": "3442 587242",
        # 检查点由session_id访问
        "thread_id": session_id,
    }
}

_printed = set()  # set集合，避免重复打印

# 执行工作流
while True:
    question = input('用户：')
    if question.lower() in ['q', 'exit', 'quit']:
        print('对话结束，拜拜！')
        break
    else:
        events = graph.stream({'messages': ('user', question)}, config, stream_mode='values')
        for event in events:
            _print_event(event, _printed)
