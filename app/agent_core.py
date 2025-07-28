# app/agent_core.py
"""
LangGraph 기반 금융 에이전트 코어 – 2025‑07‑28 hot‑fix
• Node 함수들을 create_agent_core() 내부로 이동해 llm 클로저 문제 해결
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


# ────────────────────────────────────────────────────────────
#  상태 정의
# ────────────────────────────────────────────────────────────
class AgentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    task_id: str
    next_node: str
    router_raw: str


# ────────────────────────────────────────────────────────────
#  그래프 빌더
# ────────────────────────────────────────────────────────────
def create_agent_core(llm, checkpointer):
    """
    ⚠️ 모든 Node 함수를 이 함수 안에 정의한다 → llm 변수 클로저 해결  [#]
    """
    # ───────── 1) Router Node ─────────
    def task_router_node(state: AgentState) -> dict:
        question = state["messages"][-1].content
        llm_reply = llm.invoke(
            TASK_ROUTER_PROMPT.format(question=question)
        ).content.strip()

        m = re.search(r"Task\s*([1-4])", llm_reply, re.I)
        task_id = m.group(1) if m else "4"

        node_map = {
            "1": "task1_tool_node",
            "2": "task2_tool_node",
            "3": "general_answer",
            "4": "general_answer",
        }
        next_node = node_map[task_id]

        return {
            "task_id": task_id,
            "next_node": next_node,
            "router_raw": llm_reply,
        }

    # ───────── 2) Task‑1 Node (ToolNode) ─────────
    task1_tool_node = ToolNode(all_tools)

    # ───────── 3) Task‑2 Node (조건 검색) ─────────
    def task2_node(state: AgentState) -> dict:
        question = state["messages"][-1].content

        json_str = llm.invoke(
            TASK2_PROMPT.format(question=question)
        ).content
        query_json = parse_llm_json(json_str)

        from app.tools.task2_conditional import screen_stocks_by_conditions
        tool_result = screen_stocks_by_conditions.invoke(
            {"llm_analyzed_json_string": query_json}
        )

        answer_msg = llm.invoke(
            TASK2_FINAL_PROMPT.format(
                question=question, tool_result=tool_result
            )
        )
        return {"messages": [answer_msg]}

    # ───────── 4) General Answer Node ─────────
    def general_answer_node(state: AgentState) -> dict:
        last_msg = state["messages"][-1]

        # 툴 결과 요약
        if isinstance(last_msg, ToolMessage):
            human_q = next(
                (m.content for m in reversed(state["messages"]) if m.type == "human"),
                "",
            )
            resp = llm.invoke(
                ANSWER_PROMPT.format(
                    question=human_q,
                    tool_result=last_msg.content,
                )
            )
            return {"messages": [resp]}

        # 일반 대화
        resp = llm.invoke(state["messages"])
        return {"messages": [resp]}

    # ───────── 5) 그래프 구성 ─────────
    builder = StateGraph(AgentState)

    builder.add_node("router", task_router_node)
    builder.add_node("task1_tool_node", task1_tool_node)
    builder.add_node("task2_tool_node", task2_node)
    builder.add_node("general_answer", general_answer_node)

    builder.add_edge(START, "router")

    builder.add_conditional_edges(
        "router",
        lambda s: s["next_node"],
        {
            "task1_tool_node": "task1_tool_node",
            "task2_tool_node": "task2_tool_node",
            "general_answer": "general_answer",
        },
    )

    builder.add_edge("task1_tool_node", "general_answer")
    builder.add_edge("task2_tool_node", END)
    builder.add_edge("general_answer", END)

    return builder.compile(checkpointer=checkpointer)
