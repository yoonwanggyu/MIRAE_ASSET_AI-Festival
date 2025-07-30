from langchain_naver import ChatClovaX
import os
from dotenv import load_dotenv

load_dotenv()

clova = ChatClovaX(
    api_key=os.getenv('NCP_CLOVASTUDIO_API_KEY'),
    model="HCX-005",
    temperature=0.2,
    max_tokens=None,
    timeout=None
)