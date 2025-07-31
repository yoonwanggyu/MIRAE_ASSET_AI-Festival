from langchain_naver import ChatClovaX
import os, uuid
from dotenv import load_dotenv

load_dotenv('/Users/yoon/MIRAE_ASSET_AI-Festival/.env')

clova = ChatClovaX(
    api_key=os.getenv('NCP_CLOVASTUDIO_API_KEY'),
    model="HCX-005",
    temperature=0.2,
    max_tokens=None,
    timeout=None
)

# Function Calling 호출 API
API_KEY = os.getenv('NCP_CLOVASTUDIO_API_KEY')
REQUEST_ID = f"req-{uuid.uuid4()}"

url = "https://clovastudio.stream.ntruss.com/testapp/v3/chat-completions/HCX-005"
headers = {

    "Authorization": f"Bearer {API_KEY}",
    "X-NCP-CLOVASTUDIO-REQUEST-ID": REQUEST_ID,
    "Content-Type": "application/json"
}