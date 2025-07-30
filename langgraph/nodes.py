import re

from langgraph.state import *
from llm import *
from prompt import *
from tools.task1_tools import *
from tools.task2_tools import *
from utils import *
import datetime

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
    print(f"DEBUG: Final decision_task: '{decision}'")
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
    print(f"DEBUG: Final answer_str in handle_task1_tools: '{answer_str}'")
    return ChatbotState(task_response=answer_str)

async def handle_task2_tools(state: ChatbotState):
    """
    Task2에 해당하는 노드 함수
    """
    user_query = state["question"]

    messages = [("system", TASK2_PROMPT),("human", user_query)]
    ai_msg = clova.invoke(messages)

    llm_question_analysis = parse_llm_json(ai_msg.content)

    tool_map = {tool.name: tool for tool in task2_tools}
    llm_with_tools = clova.bind_tools(task2_tools)
    result = await llm_with_tools.ainvoke(llm_question_analysis)

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
    print(f"DEBUG: Final answer_str in handle_task2_tools: '{answer_str}'")
    return ChatbotState(task_response=answer_str)

async def agent_answer(state: ChatbotState):
    """
    Task 결과를 토대로 최종 Answer 생성 함수
    """
    user_query = state["question"]
    task_response = state['task_response']

    current_date = datetime.date.today().strftime("%Y-%m-%d") # 현재 날짜 가져오기

    prompt = FINAL_ANSWER_PROMPT.format(question = user_query,
                                        task_result = task_response,
                                        current_date = current_date)
    messages = [("system", prompt)]
    llm_resp = await clova.ainvoke(messages)
    answer  = llm_resp.content.strip()

    return ChatbotState(answer=answer,
                        messages=[("user", user_query ), ("assistant", answer)])

