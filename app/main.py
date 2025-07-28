# app/main.py
import os
import uuid
import yaml
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Response
from pydantic import BaseModel
from redis.asyncio import Redis, RedisError                # ✔ Redis 계속 사용
from redis.asyncio.cluster import RedisCluster, RedisClusterException
from redis.cluster import ClusterNode

from langchain_naver import ChatClovaX

from app.agent_core import create_agent_core, AgentState

import logging, traceback
logger = logging.getLogger("uvicorn.error")


# ───────────────────────────────────────────────────────
# Lifespan
# ───────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 API 서버 시작: 리소스를 초기화합니다.")
    load_dotenv()

    BASE_DIR = Path(__file__).resolve().parent
    default_cfg = BASE_DIR / "config.yaml"
    config_path = Path(os.getenv("CONFIG_FILE", default_cfg))

    if not config_path.exists():
        raise FileNotFoundError(f"config.yaml not found at {config_path}")

    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    redis_cfg = config["redis_cluster"]
    print("✅ redis 설정 파일 로드 완료")

    # Redis 연결(클러스터 or 싱글)
    try:
        if redis_cfg.get("startup_nodes"):
            nodes = [ClusterNode(n["host"], n["port"]) for n in redis_cfg["startup_nodes"]]
            redis_conn = RedisCluster(startup_nodes=nodes, decode_responses=True)
        else:
            redis_conn = Redis(host=redis_cfg["host"], port=redis_cfg["port"], decode_responses=True)
        await redis_conn.ping()
        print("✅ Redis 연결 성공 (NCP)")
    except (RedisError, RedisClusterException) as e:
        print(f"❌ Redis 연결 실패: {e}")
        raise RuntimeError("Redis 연결에 실패했습니다.")

    # LLM 초기화
    api_key = os.getenv("NCP_CLOVASTUDIO_API_KEY")
    llm = ChatClovaX(api_key=api_key, model="HCX-003", temperature=0.1)

    # ✔ checkpointer 인스턴스 완전 제거
    agent_core = create_agent_core(llm)
    app.state.agent_core = agent_core
    app.state.redis = redis_conn
    print("✅ 에이전트 코어 생성 완료")

    yield

    # 종료
    print("🌙 API 서버 종료: 리소스를 정리합니다.")
    await app.state.redis.close()
    print("✅ Redis 연결 종료")


# ───────────────────────────────────────────────────────
# FastAPI 앱
# ───────────────────────────────────────────────────────
app = FastAPI(
    lifespan=lifespan,
    title="미래에셋 AI 금융 에이전트",
    description="HyperCLOVA X와 LangGraph를 이용한 금융 정보 제공 및 조건 검색 에이전트",
    version="1.0.0"
)

class QueryIn(BaseModel):
    question: str
    user_id: str = "default_user"

class QueryOut(BaseModel):
    answer: str


# ───────────────────────────────────────────────────────
# /agent/invoke
# ───────────────────────────────────────────────────────
@app.post("/agent/invoke", response_model=QueryOut, summary="AI 에이전트 호출")
async def agent_invoke(req: QueryIn, fastapi_response: Response):
    if not req.question.strip():
        return QueryOut(answer="질문 내용이 없습니다.")

    agent_core = app.state.agent_core
    config = {"configurable": {"thread_id": req.user_id}}

    try:
        initial_state = AgentState(messages=[("human", req.question)])
        print(f"🌟 initial_state: {initial_state}")

        final_state = await agent_core.ainvoke(initial_state, config=config)
        print(f"🌟 final_state: {final_state}")

        final_answer = final_state["messages"][-1].content

        # 클로바 X 헤더 전달(선택 사항)
        request_id = f"req-{uuid.uuid4()}"
        api_key = os.getenv("NCP_CLOVASTUDIO_API_KEY")
        fastapi_response.headers["Authorization"] = f"Bearer {api_key}"
        fastapi_response.headers["X-NCP-CLOVASTUDIO-REQUEST-ID"] = request_id

        return QueryOut(answer=final_answer)

    except Exception as e:
        traceback.print_exc()
        logger.exception("Agent 처리 중 예외 발생")
        print(f"Agent 처리 중 오류 발생: {e}")
        return QueryOut(answer=f"오류 발생: {e!r}")


# ───────────────────────────────────────────────────────
# 실행
# ───────────────────────────────────────────────────────
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)
