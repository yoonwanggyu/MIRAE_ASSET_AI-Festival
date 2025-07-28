# app/agent_core.py
from __future__ import annotations
import re, json
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from app.prompt import (
    TASK_ROUTER_PROMPT,
    ANSWER_PROMPT,
    TASK1_TOOL_PROMPT,
    TASK2_PROMPT,
    TASK2_FINAL_PROMPT,
)
from app.tools import all_tools
from app.utils import parse_llm_json


class AgentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    task_id: str
    next_node: str
    router_raw: str


def create_agent_core(llm):
    """checkpointer 없는 메모리 그래프."""
    tool_map = {t.name: t for t in all_tools}

    # --- 1. Router -------------------------------------------------------
    def router(state: AgentState) -> dict:
        q = state["messages"][-1].content
        raw = llm.invoke(TASK_ROUTER_PROMPT.format(question=q)).content.strip()
        tid = re.search(r"Task\s*([1-4])", raw, re.I)
        tid = tid.group(1) if tid else "4"
        next_node = {"1": "task1", "2": "task2"}.get(tid, "general")
        return {"task_id": tid, "next_node": next_node, "router_raw": raw}

    # --- 2. Task‑1 : 주가·뉴스 등 단순 툴 호출 ---------------------------

    def task1(state: AgentState) -> dict:
        question = state["messages"][-1].content

        # ① 어떤 함수 쓸지 LLM에 물어봄
        raw = llm.invoke(TASK1_TOOL_PROMPT.format(question=question)).content.strip()
        try:
            call = parse_llm_json(raw)  # 안전 파싱
            tool_name, args = call["tool"], call.get("args", {})
        except Exception:
            return {"messages": [f"❌ 도구 JSON 파싱 실패: {raw}"]}

        if tool_name not in tool_map:
            return {"messages": [f"❌ 지원하지 않는 함수명: {tool_name}"]}

        # ② 도구 실행
        try:
            result = tool_map[tool_name].invoke(args)
        except Exception as e:
            return {"messages": [f"❌ 도구 실행 오류: {e}"]}

        # ③ 결과로 답변 생성
        answer = llm.invoke(
            ANSWER_PROMPT.format(question=question, tool_result=result)
        )
        return {"messages": [answer]}

    # --- 3. Task‑2 : 조건 검색 -------------------------------------------
    def task2(state: AgentState) -> dict:
        q = state["messages"][-1].content
        spec = llm.invoke(TASK2_PROMPT.format(question=q)).content
        spec = parse_llm_json(spec)

        from app.tools.task2_conditional import screen_stocks_by_conditions
        result = screen_stocks_by_conditions.invoke(
            {"llm_analyzed_json_string": spec}
        )

        answer = llm.invoke(
            TASK2_FINAL_PROMPT.format(question=q, tool_result=result)
        )
        return {"messages": [answer]}

    # --- 4. General -------------------------------------------------------
    def general(state: AgentState) -> dict:
        return {"messages": [llm.invoke(state["messages"])]}

    # --- 그래프 구성 ------------------------------------------------------
    g = StateGraph(AgentState)
    g.add_node("router", router)
    g.add_node("task1", task1)
    g.add_node("task2", task2)
    g.add_node("general", general)

    g.add_edge(START, "router")
    g.add_conditional_edges(
        "router",
        lambda s: s["next_node"],
        {"task1": "task1", "task2": "task2", "general": "general"},
    )
    g.add_edge("task1", END)
    g.add_edge("task2", END)
    g.add_edge("general", END)

    return g.compile()
