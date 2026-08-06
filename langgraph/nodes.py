import re, requests, asyncio, json, os
import numpy as np

from langgraph.state import *
from prompt import *
from tools.task1_tools import *
from tools.task2_tools import *
from tools.task3_tools import *
from tools.task5_tools import *
from utils import *
from langchain_naver import ChatClovaX

def make_clova(state: ChatbotState):
    """
    각 노드에서 공통으로 쓰는 ChatClovaX 클라이언트를 생성합니다.
    """
    return ChatClovaX(api_key=state["api_key"], model="HCX-005", temperature=0.2)


async def run_tool_calling_node(state: ChatbotState, tools: list, node_name: str) -> str:
    """
    Task1·Task3처럼 'LLM에 tool을 바인딩 → 호출된 tool 실행 → 결과 문자열 병합'
    패턴을 공유하는 노드의 공통 처리 함수.

    Args:
        state: 현재 ChatbotState
        tools: 바인딩할 LangChain tool 리스트 (예: task1_tools)
        node_name: DEBUG 로그에 표시할 노드 이름

    Returns:
        str: tool 실행 결과를 줄바꿈으로 이어붙인 문자열.
             tool_calls가 없으면 LLM 응답 본문을 그대로 반환.
    """
    clova = make_clova(state)
    user_query = state["question"]

    tool_map = {tool.name: tool for tool in tools}
    llm_with_tools = clova.bind_tools(tools)
    result = await llm_with_tools.ainvoke(user_query)

    if not (hasattr(result, "tool_calls") and result.tool_calls):
        answer_str = getattr(result, "content", str(result))
        print(f"DEBUG: Final answer_str in {node_name}: '{answer_str}'")
        return answer_str

    answers = []
    for tool_call in result.tool_calls:
        tool_name = tool_call['name']
        args = tool_call['args']
        tool = tool_map.get(tool_name)
        if tool is not None:
            answers.append(await tool.ainvoke(args))
        else:
            answers.append(f"Tool 결과 없음: {tool_name}")

    answer_str = "\n".join(map(str, answers))
    print(f"DEBUG: Final answer_str in {node_name}: '{answer_str}'")
    return answer_str


async def decision_task(state: ChatbotState):
    """
    LLM이 어떤 Task를 골랐는지 설명을 섞어 출력해도
    'Task1'·'Task2' … 형태로 정확히 추출해 state에 저장.
    """
    clova = make_clova(state)
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
    answer_str = await run_tool_calling_node(state, task1_tools, "handle_task1_tools")
    return ChatbotState(task_response=answer_str)

async def handle_task2_tools(state: ChatbotState):
    """
    Task2에 해당하는 노드 함수
    """
    clova = make_clova(state)
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
    answer_str = await run_tool_calling_node(state, task3_tools, "handle_task3_tools")
    return ChatbotState(task_response=answer_str)

async def handle_task4_tools(state: ChatbotState):
    """
    Task4: 모호한 의미 해석 및 정량화 유도 응답 생성.
    - LLM이 자체 판단으로 [redirect: TaskX] 태그를 포함하면 해당 Task로 연결 가능.
    - tool은 호출하지 않음.
    """
    clova = make_clova(state)
    user_query = state["question"]

    prompt = TASK4_PROMPT.format(
        question=user_query
    )

    messages = [("system", prompt)]
    ai_msg = await clova.ainvoke(messages)
    content = ai_msg.content

    return ChatbotState(task_response=content,
                        messages=[("user", user_query ), ("assistant", content)])


def convert_numpy_types(obj):
    """numpy 타입을 Python 기본 타입으로 변환"""
    if isinstance(obj, np.float64):
        return float(obj)
    elif isinstance(obj, np.int64):
        return int(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_numpy_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    else:
        return obj
    

CLOVASTUDIO_CHAT_URL = os.getenv(
    "NCP_CLOVASTUDIO_CHAT_URL",
    "https://clovastudio.stream.ntruss.com/testapp/v3/chat-completions/HCX-005",
)

async def handle_task5_tools(state: ChatbotState):
    user_query = state["question"]

    url = CLOVASTUDIO_CHAT_URL
    headers = {
        "Authorization": f"Bearer {state['api_key']}",
        "Content-Type": "application/json; charset=utf-8",
    }

    data = {
        "model": "HCX-005",
        "messages": [
            {"role": "system", "content": TASK5_TOOLS_PROMPT.format(
                question=user_query,
                tool_result=""
            )},
            {"role": "user", "content": user_query}
        ],
        "tools": task5_functions,
        "tool_choice": "auto"
    }

    response = requests.post(url, headers=headers, json=data)

    try:
        result = response.json()
    except Exception as e:
        raise ValueError(f"[JSON 파싱 오류] {e}\n응답 원문: {response.text}")

    # ✅ 응답 구조 점검
    if not result or "result" not in result or result["result"] is None:
        raise ValueError(f"[API 응답 오류] 'result' 없음 또는 None\nresult: {result}")
    
    if "message" not in result["result"] or "toolCalls" not in result["result"]["message"]:
        raise ValueError(f"[API 응답 오류] 'message' 또는 'toolCalls' 없음\nresult: {result['result']}")

    tool_calls = result["result"]["message"]["toolCalls"]

    all_outputs = {}
    final_output = None

    for call in tool_calls:
        fn_name = call["function"]["name"]
        args = call["function"]["arguments"]
        if isinstance(args, str):
            args = json.loads(args)

        py_func = task5_py_funcs.get(fn_name)
        if py_func is None:
            raise ValueError(f"지원하지 않는 함수: {fn_name}")

        if asyncio.iscoroutinefunction(py_func):
            out = await py_func(**args)
        else:
            out = await asyncio.to_thread(py_func, **args)

        out = convert_numpy_types(out)
        all_outputs[fn_name] = out
        final_output = out

    final_output = convert_numpy_types(final_output)
    all_outputs = convert_numpy_types(all_outputs)

    # agent_answer는 task_response를 읽어 TASK5_FINAL_PROMPT를 채우므로,
    # tool 출력을 task_response에도 함께 실어 보낸다.
    return ChatbotState(
        task_response=json.dumps(all_outputs, ensure_ascii=False, default=str),
        tools=convert_numpy_types(result),
        tools_response=final_output,
        all_tool_outputs=all_outputs
    )

async def agent_answer(state: ChatbotState):
    """
    Task 결과를 토대로 최종 Answer 생성 함수
    """
    clova = make_clova(state)
    user_query = state["question"]

    # Task 노드를 거치지 않고 곧바로 이 노드로 라우팅되는 경우(알 수 없는 decision 값)
    # task_response가 아예 없을 수 있으므로 KeyError 대신 빈 결과로 처리한다.
    task_response = state.get('task_response')
    decision_task = state.get('decision_task') or ''

    if task_response is None or task_response == '':
        print(f"DEBUG: agent_answer: task_response 없음 (decision_task='{decision_task}'). 분석 결과 없이 답변 생성.")
        task_response = "분석 결과 없음 (질문을 처리할 수 있는 도구를 찾지 못했습니다)."

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

