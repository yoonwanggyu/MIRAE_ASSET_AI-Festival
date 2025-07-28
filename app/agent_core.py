# app/agent_core.py
"""
LangGraph 기반 금융 에이전트 코어 ― 2025‑07‑28 리팩터

변경 요약
---------
1) Router 노드
   • <answer>"Task1|2|3|4"</answer> 패턴을 정규식으로 추출해
     state["task_id"] = "1|2|3|4"
     state["next_node"] = "..._node"
     형태의 dict 반환

2) 그래프 분기
   • START → router (단일 edge)
   • router → conditional_edges( state["next_node"] )

3) Task1·2 전용 노드 유지
   • Task3·4 ⇒ general_answer 로 포워딩
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


# ─────────────────────────────────────────────────────────────
#  상태 정의
# ─────────────────────────────────────────────────────────────
class AgentState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    task_id: str            # "1" | "2" | "3" | "4"
    next_node: str          # 라우팅용 실제 그래프 노드명
    router_raw: str         # LLM 원본 출력 (디버그용)


# ─────────────────────────────────────────────────────────────
#  1. Router Node
# ─────────────────────────────────────────────────────────────
def task_router_node(state: AgentState) -> dict:
    """사용자 질문을 Task1~4 중 하나로 분류해 next_node를 결정한다."""
    question: str = state["messages"][-1].content
    prompt = TASK_ROUTER_PROMPT.format(question=question)
    llm_reply: str = llm.invoke(prompt).content.strip()

    # <answer>"Task1"</answer> 형식에서 TaskN 추출
    m = re.search(r'Task\s*([1-4])', llm_reply, re.IGNORECASE)
    task_id = m.group(1) if m else "4"        # 안전장치: 매칭 실패 ⇒ Task4

    node_map = {
        "1": "task1_tool_node",
        "2": "task2_tool_node",
        "3": "general_answer",   # 시그널 감지 도구 미구현
        "4": "general_answer",   # 모호한 질문 → 직접 답변
    }
    next_node = node_map[task_id]

    return {
        "task_id": task_id,
        "next_node": next_node,
        "router_raw": llm_reply,
    }


# ─────────────────────────────────────────────────────────────
#  2. Task‑1 Node (단순 조회: ToolNode)
# ─────────────────────────────────────────────────────────────
task1_tool_node = ToolNode(all_tools)


# ─────────────────────────────────────────────────────────────
#  3. Task‑2 Node (조건 검색: 커스텀 파이프라인)
# ─────────────────────────────────────────────────────────────
def task2_node(state: AgentState) -> dict:
    question = state["messages"][-1].content

    # (1) LLM → 조건 JSON
    json_prompt = TASK2_PROMPT.format(question=question)
    json_str = llm.invoke(json_prompt).content
    query_json = parse_llm_json(json_str)  # utils.py

    # (2) 조건 검색 도구 호출
    from app.tools.task2_conditional import screen_stocks_by_conditions

    tool_result = screen_stocks_by_conditions.invoke(
        {"llm_analyzed_json_string": query_json}
    )

    # (3) LLM 최종 정리
    final_prompt = TASK2_FINAL_PROMPT.format(
        question=question, tool_result=tool_result
    )
    answer_msg = llm.invoke(final_prompt)

    return {"messages": [answer_msg]}


# ─────────────────────────────────────────────────────────────
#  4. General‑Answer Node
# ─────────────────────────────────────────────────────────────
def general_answer_node(state: AgentState) -> dict:
    """
    • ToolMessage 가 마지막이면 → ANSWER_PROMPT 로 요약
    • 그렇지 않으면 LLM 에게 바로 답변 생성
    """
    last_msg = state["messages"][-1]

    if isinstance(last_msg, ToolMessage):
        # 사용자 질문(마지막 Human) 찾기
        human_msgs = [m for m in state["messages"] if m.type == "human"]
        question = human_msgs[-1].content if human_msgs else ""

        prompt = ANSWER_PROMPT.format(
            question=question,
            tool_result=last_msg.content,
        )
        resp = llm.invoke(prompt)
        return {"messages": [resp]}

    # ToolMessage 없으면 그대로 이어서 답변
    resp = llm.invoke(state["messages"])
    return {"messages": [resp]}


# ─────────────────────────────────────────────────────────────
#  5. 그래프 빌더
# ─────────────────────────────────────────────────────────────
def create_agent_core(llm, checkpointer):
    builder = StateGraph(AgentState)

    # ▸ 노드 추가
    builder.add_node("router", task_router_node)
    builder.add_node("task1_tool_node", task1_tool_node)
    builder.add_node("task2_tool_node", task2_node)
    builder.add_node("general_answer", general_answer_node)

    # ▸ 엣지 정의
    builder.add_edge(START, "router")           # 시작 → 라우터

    # 라우터 분기 (state["next_node"] 값으로 이동)
    builder.add_conditional_edges(
        "router",
        lambda s: s["next_node"],
        {
            "task1_tool_node": "task1_tool_node",
            "task2_tool_node": "task2_tool_node",
            "general_answer":  "general_answer",
        },
    )

    # Task1 완료 → General Answer (툴 결과 요약)
    builder.add_edge("task1_tool_node", "general_answer")

    # Task2 는 내부에서 이미 최종 메시지 생성 → END
    builder.add_edge("task2_tool_node", END)

    # General Answer → END
    builder.add_edge("general_answer", END)

    # 컴파일 & 반환
    return builder.compile(checkpointer=checkpointer)
