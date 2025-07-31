import re, requests, asyncio

from langgraph.state import *
from prompt import *
from tools.task1_tools import *
from tools.task2_tools import *
from tools.task3_tools import *
from tools.task5_tools import *
from utils import *
from langchain_naver import ChatClovaX

async def decision_task(state: ChatbotState):
    """
    LLM이 어떤 Task를 골랐는지 설명을 섞어 출력해도
    'Task1'·'Task2' … 형태로 정확히 추출해 state에 저장.
    """
    clova = ChatClovaX(api_key=state["api_key"], model="HCX-005", temperature=0.2)
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
    clova = ChatClovaX(api_key=state["api_key"], model="HCX-005", temperature=0.2)
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
    clova = ChatClovaX(api_key=state["api_key"], model="HCX-005", temperature=0.2)
    user_query = state["question"]

    messages = [("system", TASK2_PROMPT),("human", user_query)]
    ai_msg = await clova.ainvoke(messages)

    llm_question_analysis = parse_llm_json(ai_msg.content)
    result = answer_task2(llm_question_analysis)
    
    return ChatbotState(task_response=result)

async def handle_task3_tools(state: ChatbotState):
    """
    Task3에 해당하는 노드 함수
    """
    clova = ChatClovaX(api_key=state["api_key"], model="HCX-005", temperature=0.2)
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
    clova = ChatClovaX(api_key=state["api_key"], model="HCX-005", temperature=0.2)
    user_query = state["question"]

    prompt = TASK4_PROMPT.format(
        question=user_query
    )

    messages = [("system", prompt)]
    ai_msg = await clova.ainvoke(messages)
    content = ai_msg.content

    return ChatbotState(task_response=content,
                        messages=[("user", user_query ), ("assistant", content)])

async def handle_task5_tools(state: ChatbotState):
    """
    Task5 투자 판단 분석 도구 함수
    사용자 질문을 바탕으로 투자 분석에 필요한 도구들을 호출하여 종합적인 분석을 수행
    """
    user_query = state["question"]
    api_key=state["api_key"]
    
    REQUEST_ID = f"req-{uuid.uuid4()}"
    url = "https://clovastudio.stream.ntruss.com/testapp/v3/chat-completions/HCX-005"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "X-NCP-CLOVASTUDIO-REQUEST-ID": REQUEST_ID,
        "Content-Type": "application/json"
    }
    data = {
        "model": "HCX-005",
        "messages": [
            {"role": "system", "content": TASK5_TOOLS_PROMPT},
            {"role": "user", "content": user_query}
        ],
        "tools": [{"type": "function", "function": s} for s in task5_functions],
        "tool_choice": "auto"
    }

    response = requests.post(url, headers=headers, json=data)
    result = response.json()

    tool_calls = result['result']['message']['toolCalls']
    
    all_outputs = {}
    final_output = None

    for call in tool_calls:
        fn_name = call["function"]["name"]
        args = call["function"]["arguments"]
        
        if isinstance(args, str):
            args = json.loads(args)

        py_func = task5_py_funcs.get(fn_name)
        if py_func is None:
            raise ValueError(f"Unsupported function: {fn_name}")

        if asyncio.iscoroutinefunction(py_func):
            out = await py_func(**args)
        else:
            out = await asyncio.to_thread(py_func, **args)
        
        all_outputs[fn_name] = out
        final_output = out  

    return ChatbotState(task_response=final_output)

async def agent_answer(state: ChatbotState):
    """
    Task 결과를 토대로 최종 Answer 생성 함수
    """
    clova = ChatClovaX(api_key=state["api_key"], model="HCX-005", temperature=0.2)
    user_query = state["question"]
    task_response = state['task_response']
    decision_task = state['decision_task']

    if decision_task.lower() == 'task5':
        prompt = TASK5_FINAL_PROMPT.format(question = user_query,
                                          tool_result = task_response)
    else:
        prompt = FINAL_ANSWER_PROMPT.format(question = user_query,
                                        task_result = task_response)
        
    messages = [("system", prompt)]
    llm_resp = await clova.ainvoke(messages)
    answer  = llm_resp.content.strip()

    return ChatbotState(answer=answer,
                        messages=[("user", user_query ), ("assistant", answer)])

