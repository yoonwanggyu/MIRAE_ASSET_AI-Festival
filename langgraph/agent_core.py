# /langgraph/agent_core.py

from langgraph.graph import StateGraph, END
from .state import ChatbotState
from .nodes import *

# Task 분기 로직
def route_tasks(state: ChatbotState):
    """Task 결정 값에 따라 다음 노드로 분기합니다."""
    decision = state.get("decision_task")
    if decision == "Task1":
        return "handle_task1_tools"
    elif decision == "Task2":
        return "handle_task2_tools"
    elif decision == "Task3":
        return "handle_task3_tools"
    elif decision == "Task4":
        return "handle_task4_tools"
    elif decision == "Task5:
        return "handle_task5_tools"
    else:
        return "agent_answer"

# 그래프 정의
workflow = StateGraph(ChatbotState)

# 노드 추가
workflow.add_node("decision_task", decision_task)
workflow.add_node("handle_task1_tools", handle_task1_tools)
workflow.add_node("handle_task2_tools", handle_task2_tools)
workflow.add_node("handle_task3_tools", handle_task3_tools)
workflow.add_node("handle_task4_tools", handle_task4_tools)
workflow.add_node("handle_task5_tools", handle_task5_tools)
workflow.add_node("agent_answer", agent_answer)

# 엣지(연결) 설정
workflow.set_entry_point("decision_task")

# 조건부 엣지 (Task 라우팅)
workflow.add_conditional_edges(
    "decision_task",
    route_tasks,
    {
        "handle_task1_tools": "handle_task1_tools",
        "handle_task2_tools": "handle_task2_tools",
        "handle_task3_tools": "handle_task3_tools",
        "handle_task4_tools": "handle_task4_tools",
        "handle_task5_tools": "handle_task5_tools",
        "agent_answer": "agent_answer", # Task4 등 바로 답변으로 가는 경우
    }
)

# Task 처리 후 답변 생성 노드로 연결
workflow.add_edge("handle_task1_tools", "agent_answer")
workflow.add_edge("handle_task2_tools", "agent_answer")
workflow.add_edge("handle_task3_tools", "agent_answer")
workflow.add_edge("handle_task4_tools", END)
workflow.add_edge("handle_task5_tools", "agent_answer")
workflow.add_edge("agent_answer", END)

# 그래프 컴파일
agent_graph = workflow.compile()

print("✅ Agent Core (Graph) compiled successfully!")
