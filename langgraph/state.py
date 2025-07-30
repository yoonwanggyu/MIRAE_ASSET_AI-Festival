from typing import Annotated, List, TypedDict
from langgraph.graph.message import add_messages

class ChatbotState(TypedDict):
    question: Annotated[str, "Question"]  
    decision_task: Annotated[str, "Decision_task"]
    task_response: Annotated[str, "Task_Response"]
    answer: Annotated[str, "Final_Answer"]  
    messages: Annotated[List, add_messages] 
    api_key: Annotated[str, "API_Key"]