# =============================================================================
# llm/clova_client.py
import requests
import asyncio
from typing import Dict, Any

class ClovaClient:
    """네이버 클로바X LLM 클라이언트"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://clovastudio.stream.ntruss.com/testapp/v1/chat-completions/HCX-DASH-001"
        self.headers = {
            "X-NCP-CLOVASTUDIO-API-KEY": api_key,
            "X-NCP-APIGW-API-KEY": api_key,
            "Content-Type": "application/json"
        }
    
    async def generate(self, prompt: str, max_tokens: int = 2000, temperature: float = 0.3) -> str:
        """텍스트 생성"""
        try:
            payload = {
                "messages": [
                    {
                        "role": "system",
                        "content": "당신은 전문적인 투자 분석가입니다. 객관적이고 정확한 분석을 제공하며, 한국어로 응답합니다."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                "topP": 0.8,
                "topK": 0,
                "maxTokens": max_tokens,
                "temperature": temperature,
                "repeatPenalty": 5.0,
                "stopBefore": [],
                "includeAiFilters": True
            }
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None, 
                lambda: requests.post(self.base_url, headers=self.headers, json=payload)
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("status", {}).get("code") == "20000":
                    return result["result"]["message"]["content"]
                else:
                    raise Exception(f"클로바X API 오류: {result.get('status', {}).get('message', 'Unknown error')}")
            else:
                print(f"🔍 API 키 확인: {self.api_key[:10]}..." if self.api_key else "API 키 없음")
                print(f"🔍 응답 내용: {response.text}")
                raise Exception(f"HTTP 오류: {response.status_code}")
                
        except Exception as e:
            raise Exception(f"클로바X 호출 실패: {e}")