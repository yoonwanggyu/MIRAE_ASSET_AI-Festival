# app/agent_core.py – 2025‑07‑28 tool‑router 방식
from __future__ import annotations
import re, json
from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from app.prompt import (
    TASK_ROUTER_PROMPT,
    TOOLS_PROMPT,
    ANSWER_PROMPT,
    TASK2_PROMPT,
    TASK2_FINAL_PROMPT,
)
from app.tools import all_tools
from app.utils import parse_llm_json


# ────────────────────────  상태  ────────────────────────
class AgentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    task_id: str
    next_node: str
    router_raw: str


# ─────────────────────  그래프 빌더  ─────────────────────
def create_agent_core(llm):
    """Redis checkpointer 없이 순수 메모리 그래프."""

    # ---------- 1. Router ----------
    def router_node(state: AgentState) -> dict:
        q = state["messages"][-1].content
        raw = llm.invoke(TASK_ROUTER_PROMPT.format(question=q)).content.strip()
        m = re.search(r"Task\s*([1-4])", raw, re.I)
        tid = m.group(1) if m else "4"
        return {
            "task_id": tid,
            "next_node": "task1_node" if tid == "1"
                         else "task2_node" if tid == "2"
                         else "general_answer",
            "router_raw": raw,
        }

    # ---------- 2. Task‑1  ----------
    ## 2‑1) LLM에게 “어떤 함수 + 어떤 인자”를 JSON으로만 묻게 할 프롬프트
    tools_desc = "\n".join(
        [f"- {t.name}: {t.description.splitlines()[0]}" for t in all_tools]
    )

    TASK1_TOOL_ROUTER_PROMPT = (
        f"{TOOLS_PROMPT}\n\n"
        f"### 사용 가능 함수 목록\n{tools_desc}\n\n"
        "아래 JSON 스키마에 맞춰 **한 줄**로만 출력하세요.(다른 글자 금지)\n"
        '{{"tool": "<함수명>", "args": {{...}}}}\n\n'
        "### 사용자 질문\n{question}"
    )

    tool_map = {t.name: t for t in all_tools}

    def task1_node(state: AgentState) -> dict:
        question = state["messages"][-1].content

        # (1) 어떤 도구를 쓸지 JSON으로 받아오기
        json_str = llm.invoke(
            TASK1_TOOL_ROUTER_PROMPT.format(question=question)
        ).content.strip()
        try:
            parsed = parse_llm_json(json_str)  # '{"tool": "...", "args": {...}}'
            tool_name, args = parsed["tool"], parsed.get("args", {})
        except Exception:
            return {"messages": [f"❌ 도구 선택 JSON 파싱 실패: {json_str}"]}

        if tool_name not in tool_map:
            return {"messages": [f"❌ 지원하지 않는 함수명: {tool_name}"]}

        # (2) 실제 도구 호출
        tool_result = tool_map[tool_name].invoke(args)

        # (3) 최종 답변 생성
        answer = llm.invoke(
            ANSWER_PROMPT.format(question=question, tool_result=tool_result)
        )
        return {"messages": [answer]}

    # ---------- 3. Task‑2 ----------
    def task2_node(state: AgentState) -> dict:
        q = state["messages"][-1].content
        j = llm.invoke(TASK2_PROMPT.format(question=q)).content
        j_parsed = parse_llm_json(j)

        from app.tools.task2_conditional import screen_stocks_by_conditions
        tool_result = screen_stocks_by_conditions.invoke(
            {"llm_analyzed_json_string": j_parsed}
        )

        answer = llm.invoke(
            TASK2_FINAL_PROMPT.format(question=q, tool_result=tool_result)
        )
        return {"messages": [answer]}

    # ---------- 4. General Answer ----------
    def general_answer_node(state: AgentState) -> dict:
        return {"messages": [llm.invoke(state["messages"])]}

    # ---------- 5. 그래프 ----------
    g = StateGraph(AgentState)
    g.add_node("router", router_node)
    g.add_node("task1_node", task1_node)
    g.add_node("task2_node", task2_node)
    g.add_node("general_answer", general_answer_node)

    g.add_edge(START, "router")
    g.add_conditional_edges(
        "router",
        lambda s: s["next_node"],
        {
            "task1_node": "task1_node",
            "task2_node": "task2_node",
            "general_answer": "general_answer",
        },
    )
    g.add_edge("task1_node", END)
    g.add_edge("task2_node", END)
    g.add_edge("general_answer", END)

    return g.compile()
