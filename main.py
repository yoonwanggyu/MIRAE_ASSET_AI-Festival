import uvicorn
from fastapi import FastAPI, Header, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from contextlib import asynccontextmanager
from langchain_naver import ChatClovaX
import os
from dotenv import load_dotenv

load_dotenv()

# 애플리케이션 로직 및 상태 객체 임포트
from langgraph.agent_core import agent_graph
from langgraph.state import ChatbotState

# 수정된 Redis 커넥터 함수 임포트
from redis_connector import connect_to_redis, close_redis_connection

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 애플리케이션의 시작과 종료 시점에 실행될 로직을 관리합니다.
    """
    # 애플리케이션 시작 시
    print("--- 애플리케이션 시작 ---")
    connect_to_redis()
    yield
    # 애플리케이션 종료 시
    print("--- 애플리케이션 종료 ---")
    close_redis_connection()

# --- FastAPI 앱 설정 (lifespan 적용) ---
app = FastAPI(
    title="금융 AI 에이전트 API",
    description="LangGraph로 구현된 주식 정보 조회 및 분석 에이전트입니다.",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 응답 모델 정의 ---
class AnswerResponse(BaseModel):
    answer: str

# --- API 엔드포인트 정의 ---
@app.get("/health", status_code=200)
def health_check():
    """서버가 정상적으로 실행 중인지 확인하는 간단한 엔드포인트입니다."""
    return {"status": "ok"}

@app.get("/agent", response_model=AnswerResponse, summary="금융 질문 처리 (GET)")
async def invoke_agent(
    question: str,
    Authorization: Optional[str] = Header(None),
    X_NCP_CLOVASTUDIO_REQUEST_ID: Optional[str] = Header(None)
):
    """
    사용자의 질문을 URL 쿼리 파라미터로 받아 AI 에이전트를 실행하고 답변을 반환합니다.
    """
    try:
        api_key = Authorization.replace("Bearer ", "") if Authorization else os.getenv("NCP_CLOVASTUDIO_API_KEY")
        initial_state = ChatbotState(question=question, messages=[], api_key=api_key)
        final_state = await agent_graph.ainvoke(initial_state)

        answer = final_state.get("answer", "오류: 답변을 생성하지 못했습니다.")
        return AnswerResponse(answer=answer)
    except Exception as e:
        print(f"에이전트 실행 중 오류 발생: {e}")
        # 실제 오류 메시지를 클라이언트에게 반환하여 디버깅에 용이하게 함
        return Response(content=f"Internal Server Error: {e}", status_code=500)

# --- 서버 실행 ---
if __name__ == "__main__":
    print("🚀 FastAPI 서버를 시작합니다.")
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
