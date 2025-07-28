# app/agent_core.py
"""
LangGraph 기반 금융 에이전트 코어 – 2025‑07‑28 no‑checkpoint 버전
✂️ Redis 체크포인터 완전히 제거
"""

from __future__ import annotations
import re
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from app.prompt import (
    TASK_ROUTER_PROMPT,
    ANSWER_PROMPT,
    TASK2_PROMPT,
    TASK2_FINAL_PROMPT,
)
from app.tools import all_tools
from app.utils import parse_llm_json


# ────────────────────────────────────────────────
# 상태 정의
# ────────────────────────────────────────────────
class AgentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    task_id: str
    next_node: str
    router_raw: str


# ────────────────────────────────────────────────
# 그래프 빌더
# ────────────────────────────────────────────────
def create_agent_core(llm):
    """
    ⚠️ checkpointer 매개변수 제거
    """
    llm_with_tools = llm.bind_tools(all_tools)

    # 1) Router
    def task_router_node(state: AgentState) -> dict:
        question = state["messages"][-1].content
        reply = llm.invoke(TASK_ROUTER_PROMPT.format(question=question)).content.strip()

        m = re.search(r"Task\s*([1-4])", reply, re.I)
        task_id = m.group(1) if m else "4"
        node_map = {
            "1": "task1_llm_node",
            "2": "task2_node",
            "3": "general_answer",
            "4": "general_answer",
        }
        return {"task_id": task_id, "next_node": node_map[task_id], "router_raw": reply}

    # 2) Task‑1 LLM
    def task1_llm_node(state: AgentState) -> dict:
        ai = llm_with_tools.invoke(state["messages"][-1].content)
        return {"messages": [ai]}

    # 3) Task‑1 Tool
    task1_tool_node = ToolNode(all_tools)

    # 4) Task‑2
    def task2_node(state: AgentState) -> dict:
        q = state["messages"][-1].content
        json_str = llm.invoke(TASK2_PROMPT.format(question=q)).content
        query_json = parse_llm_json(json_str)

        from app.tools.task2_conditional import screen_stocks_by_conditions
        tool_result = screen_stocks_by_conditions.invoke(
            {"llm_analyzed_json_string": query_json}
        )

        answer_msg = llm.invoke(
            TASK2_FINAL_PROMPT.format(question=q, tool_result=tool_result)
        )
        return {"messages": [answer_msg]}

    # 5) General Answer
    def general_answer_node(state: AgentState) -> dict:
        last = state["messages"][-1]
        if isinstance(last, ToolMessage):
            human_q = next(
                (m.content for m in reversed(state["messages"]) if m.type == "human"),
                "",
            )
            resp = llm.invoke(
                ANSWER_PROMPT.format(question=human_q, tool_result=last.content)
            )
            return {"messages": [resp]}
        return {"messages": [llm.invoke(state["messages"])]}

    # ── 그래프 구성 ──────────────────────────────────
    builder = StateGraph(AgentState)

    builder.add_node("router", task_router_node)
    builder.add_node("task1_llm_node", task1_llm_node)
    builder.add_node("task1_tool_node", task1_tool_node)
    builder.add_node("task2_node", task2_node)
    builder.add_node("general_answer", general_answer_node)

    builder.add_edge(START, "router")
    builder.add_conditional_edges(
        "router",
        lambda s: s["next_node"],
        {
            "task1_llm_node": "task1_llm_node",
            "task2_node": "task2_node",
            "general_answer": "general_answer",
        },
    )
    builder.add_edge("task1_llm_node", "task1_tool_node")
    builder.add_edge("task1_tool_node", "general_answer")
    builder.add_edge("task2_node", END)
    builder.add_edge("general_answer", END)

    # ✅ checkpointer 전달 X
    return builder.compile()
