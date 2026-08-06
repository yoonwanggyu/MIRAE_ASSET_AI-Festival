from typing import Annotated, List, TypedDict
from langgraph.graph.message import add_messages

class ChatbotState(TypedDict, total=False):
    question: Annotated[str, "Question"]
    decision_task: Annotated[str, "Decision_task"]
    task_response: Annotated[str, "Task_Response"]
    answer: Annotated[str, "Final_Answer"]
    messages: Annotated[List, add_messages]
    api_key: Annotated[str, "API_Key"]
    # Task5 전용: 원본 tool 호출 응답과 개별 tool 출력 보관용.
    # 그래프 스키마에 선언되지 않은 키는 노드 간 전달 과정에서 유실되므로 반드시 여기에 둔다.
    tools: Annotated[dict, "Task5_Raw_Tool_Response"]
    tools_response: Annotated[object, "Task5_Final_Tool_Output"]
    all_tool_outputs: Annotated[dict, "Task5_All_Tool_Outputs"]