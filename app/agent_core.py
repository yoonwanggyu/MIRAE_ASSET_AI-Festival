# app/agent_core.py

from typing import Annotated, Literal, TypedDict
from langchain_core.messages import BaseMessage, ToolMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

# app/prompt.py와 app/tools/__init__.py에서 필요한 요소들을 가져옵니다.
from .prompt import TASK_ROUTER_PROMPT, ANSWER_PROMPT, TASK2_PROMPT, TASK2_FINAL_PROMPT
from .tools import all_tools
from utils import parse_llm_json

# 에이전트가 작업하는 동안 상태를 저장하는 데이터 구조
class AgentState(TypedDict):
    # add_messages는 대화 기록을 새로운 메시지가 들어올 때마다 리스트에 추가합니다.
    messages: Annotated[list, add_messages]

def create_agent_core(llm, checkpointer):
    """'에이전트 코어' (LangGraph)를 생성하고 컴파일하는 함수"""

    # LLM에 도구(Tool) 정보를 바인딩하여, LLM이 도구를 사용할 수 있게 만듭니다.
    llm_with_tools = llm.bind_tools(all_tools)

    # --- 에이전트의 작업 단위(Node) 정의 ---

    # 1. Router: 사용자의 질문에 따라 어떤 Task를 수행할지 결정
    def task_router_node(state: AgentState) -> Literal["task1_tool_node", "task2_tool_node", "general_answer"]:
        question = state["messages"][-1].content
        prompt = TASK_ROUTER_PROMPT.format(question=question)
        
        response = llm.invoke(prompt)
        decision = response.content.strip()
        print(f" decisión del enrutador: {decision}")

        if "Task1" in decision:
            return "task1_tool_node"
        elif "Task2" in decision:
            return "task2_tool_node"
        else:
            # Task 1, 2가 아니면 일반 대화로 간주
            return "general_answer"

    # 2. Tool Node: 결정된 Task에 맞는 도구를 똑똑하게 찾아 실행
    # LangGraph의 ToolNode를 사용하면 LLM이 알아서 적절한 도구를 선택하고 호출합니다.
    task1_tool_node = ToolNode(all_tools)

    # 3. Task2 Node: Task2만의 특별한 처리 로직 수행
    def task2_node(state: AgentState) -> dict:
        question = state["messages"][-1].content
        
        # 1) TASK2_PROMPT를 이용해 질문을 JSON으로 구조화
        json_generation_prompt = TASK2_PROMPT.format(question=question)
        json_response = llm.invoke(json_generation_prompt)
        
        # 2) screen_stocks_by_conditions 도구에 구조화된 JSON 전달
        from .tools.task2_conditional import screen_stocks_by_conditions
        tool_result = screen_stocks_by_conditions.invoke({"llm_analyzed_json_string": json_response.content})
        
        # 3) 최종 답변 프롬프트로 결과 가공
        final_prompt = TASK2_FINAL_PROMPT.format(question=question, tool_result=tool_result)
        final_answer = llm.invoke(final_prompt)
        
        return {"messages": [final_answer]}

    # 4. Final Answer Node: 최종 답변 생성
    def final_answer_node(state: AgentState) -> dict:
        # ToolNode를 거쳐온 경우, 그 결과를 바탕으로 답변 생성
        if isinstance(state["messages"][-1], ToolMessage):
            question = state["messages"][0].content
            tool_result = state["messages"][-1].content
            prompt = ANSWER_PROMPT.format(question=question, tool_result=tool_result)
            response = llm.invoke(prompt)
            return {"messages": [response]}
        
        # 일반 대화로 바로 온 경우
        response = llm.invoke(state["messages"])
        return {"messages": [response]}

    # --- 그래프(작업 흐름) 구성 ---
    builder = StateGraph(AgentState)

    builder.add_node("router", task_router_node)
    builder.add_node("task1_tool_node", task1_tool_node)
    builder.add_node("task2_tool_node", task2_node)
    builder.add_node("general_answer", final_answer_node)

    builder.add_conditional_edges(START, lambda state: "router")
    builder.add_conditional_edges(
        "router",
        lambda state, x: x,
        {
            "task1_tool_node": "task1_tool_node",
            "task2_tool_node": "task2_tool_node",
            "general_answer": "general_answer",
        },
    )
    builder.add_edge("task1_tool_node", "general_answer")
    builder.add_edge("task2_tool_node", END) # Task2는 자체적으로 최종 답변까지 생성
    builder.add_edge("general_answer", END)

    return builder.compile(checkpointer=checkpointer)