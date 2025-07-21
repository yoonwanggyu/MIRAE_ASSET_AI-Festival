import os
import uuid
import yaml
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Response
from pydantic import BaseModel

from redis.asyncio.cluster import RedisCluster, RedisClusterException
from redis.cluster import ClusterNode
from redis.exceptions import RedisError
from redis.asyncio import Redis

from langchain_naver import ChatClovaX
from langgraph_prebuilt.checkpoint.redis import RedisSaver

# 새로 만든 에이전트 코어 생성 함수를 가져옵니다.
from app.agent_core import create_agent_core, AgentState

# --- FastAPI Lifespan 관리자 ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 API 서버 시작: 리소스를 초기화합니다.")
    load_dotenv()

    config_file = os.getenv("CONFIG_FILE", "config.yaml")
    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    print(f"✅ 설정 파일 로드 완료: {config_file}")

    try:
        redis_config = config['redis_cluster']
        if 'startup_nodes' in redis_config and redis_config['startup_nodes']:
            print("운영 환경 감지: Redis Cluster 클라이언트를 사용합니다.")
            startup_nodes_list = [
                ClusterNode(host=node['host'], port=node['port']) 
                for node in redis_config['startup_nodes']
            ]
            redis_conn = RedisCluster(startup_nodes=startup_nodes_list, decode_responses=True)
        else:
            print("개발 환경 감지: Redis 단일 노드 클라이언트를 사용합니다.")
            redis_conn = Redis(host=redis_config['host'], port=redis_config['port'], decode_responses=True)
        await redis_conn.ping()
        print("✅ Redis 연결 성공")
    except (RedisError, AttributeError) as e:
        print(f"❌ Redis 연결 실패: {e}")
        raise RuntimeError("Redis 연결에 실패했습니다.") from e

    llm = ChatClovaX(api_key=os.getenv('NCP_CLOVASTUDIO_API_KEY'), model="HCX-003", temperature=0.1)
    checkpointer = RedisSaver.from_conn(redis_conn)

    # create_agent_core 함수를 호출하여 그래프(에이전트 코어)를 생성합니다.
    agent_core = create_agent_core(llm, checkpointer)
    app.state.agent_core = agent_core
    app.state.redis = redis_conn
    print("✅ 에이전트 코어 생성 완료")
    
    yield
    
    print("🌙 API 서버 종료: 리소스를 정리합니다.")
    await app.state.redis.close()
    print("✅ Redis 연결 종료")

# --- FastAPI 앱 및 API 모델 정의 ---
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

# --- API 엔드포인트 ---
@app.post("/agent/invoke", response_model=QueryOut, summary="AI 에이전트 호출")
async def agent_invoke(req: QueryIn, fastapi_response: Response):
    if not req.question.strip():
        return QueryOut(answer="질문 내용이 없습니다.")

    agent_core = app.state.agent_core
    config = {"configurable": {"thread_id": req.user_id}}

    try:
        initial_state = AgentState(messages=[("human", req.question)])
        final_state = await agent_core.ainvoke(initial_state, config=config)
        final_answer = final_state["messages"][-1].content
        
        request_id = f"req-{uuid.uuid4()}"
        api_key = os.getenv('NCP_CLOVASTUDIO_API_KEY')
        fastapi_response.headers["Authorization"] = f"Bearer {api_key}"
        fastapi_response.headers["X-NCP-CLOVASTUDIO-REQUEST-ID"] = request_id
        
        return QueryOut(answer=final_answer)
        
    except Exception as e:
        print(f"Agent 처리 중 오류 발생: {e}")
        return QueryOut(answer="죄송합니다, 답변을 처리하는 중 오류가 발생했습니다.")

# --- 서버 실행 ---
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)