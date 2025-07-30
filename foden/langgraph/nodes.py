import re

from langgraph.state import *
from llm import *
from prompt import *
from tools.task1_tools import *
from tools.task2_tools import *
from tools.task3_tools import *
from utils import *

async def decision_task(state: ChatbotState):
    """
    LLM이 어떤 Task를 골랐는지 설명을 섞어 출력해도
    'Task1'·'Task2' … 형태로 정확히 추출해 state에 저장.
    """
    user_query = state["question"]

    prompt = TASK_ROUTER_PROMPT.format(question=user_query)
    messages = [("system", prompt)]

    llm_response = await clova.ainvoke(messages)
    raw_text = llm_response.content or ""

    normalized = re.sub(r"\s+", "", raw_text)

    m = re.search(r"task\s*([0-9]+)", normalized, re.IGNORECASE)

    decision = f"Task{m.group(1)}" if m else normalized

    return ChatbotState(decision_task = decision)

async def handle_task1_tools(state: ChatbotState):
    """
    Task1에 해당하는 노드 함수
    """
    user_query = state["question"]

    tool_map = {tool.name: tool for tool in task1_tools}
    llm_with_tools = clova.bind_tools(task1_tools)
    result = await llm_with_tools.ainvoke(user_query)

    answers = []
    if hasattr(result, "tool_calls") and result.tool_calls:
        for tool_call in result.tool_calls:
            tool_name = tool_call['name']
            args = tool_call['args']
            tool = tool_map.get(tool_name)
            if tool is not None:
                answer = await tool.ainvoke(args)
                answers.append(answer)
            else:
                answers.append(f"Tool 결과 없음: {tool_name}")
        answer_str = "\n".join(map(str, answers))
    else:
        answer_str = getattr(result, "content", str(result))
    
    return ChatbotState(task_response=answer_str)

async def handle_task2_tools(state: ChatbotState):
    """
    Task2에 해당하는 노드 함수
    """
    user_query = state["question"]

    messages = [("system", TASK2_PROMPT),("human", user_query)]
    ai_msg = clova.invoke(messages)

    llm_question_analysis = parse_llm_json(ai_msg.content)
    result = answer_task2(llm_question_analysis)
    
    return ChatbotState(task_response=result)

async def handle_task3_tools(state: ChatbotState):
    """
    Task3에 해당하는 노드 함수
    """
    user_query = state["question"]

    tool_map = {tool.name: tool for tool in task3_tools}
    llm_with_tools = clova.bind_tools(task3_tools)
    result = await llm_with_tools.ainvoke(user_query)

    answers = []
    if hasattr(result, "tool_calls") and result.tool_calls:
        for tool_call in result.tool_calls:
            tool_name = tool_call['name']
            args = tool_call['args']
            tool = tool_map.get(tool_name)
            if tool is not None:
                answer = await tool.ainvoke(args)
                answers.append(answer)
            else:
                answers.append(f"Tool 결과 없음: {tool_name}")
        answer_str = "\n".join(map(str, answers))
    else:
        answer_str = getattr(result, "content", str(result))
    
    return ChatbotState(task_response=answer_str)

async def handle_task4_tools(state: ChatbotState):
    """
    Task4: 모호한 의미 해석 및 정량화 유도 응답 생성.
    - LLM이 자체 판단으로 [redirect: TaskX] 태그를 포함하면 해당 Task로 연결 가능.
    - tool은 호출하지 않음.
    """
    user_query = state["question"]

    prompt = TASK4_PROMPT.format(
        question=user_query
    )

    messages = [("system", prompt)]
    ai_msg = clova.invoke(messages)
    content = ai_msg.content

    # 리디렉션 여부 확인
    redirect_task = None
    match = re.search(r"\[redirect:\s*(Task[1-3])\]", content)
    if match:
        redirect_task = match.group(1)
        content = re.sub(r"\[redirect:\s*Task[1-3]\]", "", content).strip()

    return ChatbotState(task_response=content,
                        redirect_task=redirect_task)

async def agent_answer(state: ChatbotState):
    """
    Task 결과를 토대로 최종 Answer 생성 함수
    """
    user_query = state["question"]
    task_response = state['task_response']

    prompt = FINAL_ANSWER_PROMPT.format(question = user_query,
                                        task_result = task_response)
    messages = [("system", prompt)]
    llm_resp = await clova.ainvoke(messages)
    answer  = llm_resp.content.strip()

    return ChatbotState(answer=answer,
                        messages=[("user", user_query ), ("assistant", answer)])

