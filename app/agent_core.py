# app/agent_core.py
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
def create_agent_core(llm, checkpointer):
    """
    모든 Node 함수는 내부에 정의해 llm 클로저를 안전하게 참조합니다.
    """
    # Task 1용: 툴 기능을 바인딩한 LLM
    llm_with_tools = llm.bind_tools(all_tools)

    # 1) Router Node ─ 사용자 질문 → Task 분류
    def task_router_node(state: AgentState) -> dict:
        question = state["messages"][-1].content
        llm_reply = llm.invoke(
            TASK_ROUTER_PROMPT.format(question=question)
        ).content.strip()

        m = re.search(r"Task\s*([1-4])", llm_reply, re.I)
        task_id = m.group(1) if m else "4"

        node_map = {
            "1": "task1_llm_node",   # ← 새 노드
            "2": "task2_node",
            "3": "general_answer",
            "4": "general_answer",
        }
        return {
            "task_id": task_id,
            "next_node": node_map[task_id],
            "router_raw": llm_reply,
        }

    # 2) Task 1 LLM Node ─ 툴 호출 메시지 생성
    def task1_llm_node(state: AgentState) -> dict:
        question = state["messages"][-1].content
        ai_msg = llm_with_tools.invoke(question)    # AIMessage(tool_calls=…)
        return {"messages": [ai_msg]}

    # 3) Task 1 Tool Node
    task1_tool_node = ToolNode(all_tools)

    # 4) Task 2 Node ─ 조건 검색
    def task2_node(state: AgentState) -> dict:
        question = state["messages"][-1].content
        json_str = llm.invoke(TASK2_PROMPT.format(question=question)).content
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

    # 5) General‑Answer Node
    def general_answer_node(state: AgentState) -> dict:
        last = state["messages"][-1]
        # 툴 결과 요약
        if isinstance(last, ToolMessage):
            human_q = next(
                (m.content for m in reversed(state["messages"]) if m.type == "human"),
                "",
            )
            resp = llm.invoke(
                ANSWER_PROMPT.format(question=human_q, tool_result=last.content)
            )
            return {"messages": [resp]}
        # 일반 대화
        resp = llm.invoke(state["messages"])
        return {"messages": [resp]}

    # ── 그래프 구성 ───────────────────────────────────────
    builder = StateGraph(AgentState)

    builder.add_node("router", task_router_node)
    builder.add_node("task1_llm_node", task1_llm_node)
    builder.add_node("task1_tool_node", task1_tool_node)
    builder.add_node("task2_node", task2_node)
    builder.add_node("general_answer", general_answer_node)

    # Edge
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

    # 컴파일
    return builder.compile(checkpointer=checkpointer)
