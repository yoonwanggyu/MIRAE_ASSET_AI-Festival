from langgraph.graph import StateGraph, START, END

from langgraph.nodes import *
from langgraph.state import *

def route_tools(state: ChatbotState):
    return state["decision_task"]

def create_agent():
    builder = StateGraph(ChatbotState)

    builder.add_node("decision_task", decision_task)
    builder.add_node("task1_tools", handle_task1_tools)
    builder.add_node("task2_tools", handle_task2_tools)
    builder.add_node("task3_tools", handle_task3_tools)
    builder.add_node("task4_tools", handle_task4_tools)
    builder.add_node("agent_answer", agent_answer)

    builder.add_edge(START, "decision_task")
    builder.add_conditional_edges(
        "decision_task",
        route_tools,
        {"Task1": "task1_tools",
        "Task2": "task2_tools",
        "Task3": "task3_tools",
        "Task4": "task4_tools"}
        )
    builder.add_edge("task1_tools", "agent_answer")
    builder.add_edge("task2_tools", "agent_answer")
    builder.add_edge("task3_tools", "agent_answer")
    builder.add_conditional_edges(
    "task4_tools",
    lambda state: state["redirect_task"] if state.get("redirect_task") else "__else__",
    {
        "Task1": "task1_tools",
        "Task2": "task2_tools",
        "Task3": "task3_tools",
        "__else__": "agent_answer"
    }
)
    builder.add_edge("agent_answer", END)

    graph = builder.compile()

    return graph