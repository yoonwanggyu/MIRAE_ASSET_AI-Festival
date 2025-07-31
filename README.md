<p align="center">
  <img src="사진/KakaoTalk_Photo_2025-07-31-07-36-41.png" alt="FIN" width="100%""/>

<div align=center>
  
**FIN문철**은 투자대법관으로서 정확한 주식 정보 조회와 <br>
투자 판단 지표를 제공하여 사용자의 투자 의사결정을 지원합니다.

1️⃣ 이정 : TASK5 내용 써줘.....<br>
2️⃣ 이정 :표지 사진 넣어줘....<br>

</div>

## 🏆 Competition
**제 9회 미래에셋증권 AI Festival**

## 🗓️ Timeline
2025.06.25 ~ 2025.07.31

## 👪 Team
**이하윤** ([hayo0n](https://github.com/hayo0n)) · **김이정** ([shashamalone](https://github.com/shashamalone)) · **윤왕규** ([yoonwanggyu](https://github.com/yoonwanggyu)) 

## 📚 Project Structure

```plaintext
📦 프로젝트 루트
├── 📂 data/
│   └── 📄 krx_tickers_with_market.csv
├── 📂 langgraph/
│   ├── 📄 agent_core.py
│   ├── 📄 nodes.py
│   └── 📄 state.py
├── 📂 tools/
│   ├── 📄 task1_tools.py
│   ├── 📄 task2_tools.py
│   └── 📄 task3_tools.py
├── 📄 .gitignore
├── 📄 Dockerfile
├── 📄 data_fetcher.py
├── 📄 llm.py
├── 📄 main.py
├── 📄 prompt.py
└── 📄 redis_connector.py
└── 📄 utils.py
└── 📄 requirements.txt
```

## ⚙️ Tech Stack Overview
- 🧠 **LLM : HyperClova X**<br>
  네이버의 대규모 언어모델로, 한국어에 특화된 고성능 AI 서비스를 제공합니다.<br>
  → 투자 관련 질의응답, 주식 분석, 금융 데이터 해석 등 전문적인 투자 상담 서비스의 핵심 엔진으로 활용

- 🔄 **LangGraph** <br>
  상태 기반 LLM 프레임워크로, 복잡한 에이전트 워크플로우를 유연하게 설계할 수 있습니다.<br>
  → Agentic RAG 흐름(Task 분기 → Tool 호출 -> 답변 생성)을 구현<br>

- ⚡ **NCloud Cloud DB for Cache(Redis Cluster)** <br>
  고성능 인메모리 데이터 스토어로, 캐싱과 세션 관리를 담당합니다. <br>
  → yfinance 데이터 (2024.01 ~ 2025.07) 데이터 적재 <br>
  
- 🚀 **FastAPI**<br>
Python ASGI 웹 프레임워크 – 타입 힌트 기반 자동 문서화 & 고성능 비동기 처리를 지원합니다.<br>
→ /agent · /health 엔드포인트 구현, CORS 미들웨어·lifespan 훅으로 Redis 연결·해제 자동 관리

- ☁️ **NCloud IaaS (Ubuntu VM)**<br>
네이버클라우드 VPC 환경의 가상머신: Public Subnet(공인 IP) + Private Subnet(Redis Cluster) 구성되어 있습니다.<br>
→ 애플리케이션 서버(uvicorn) 를 IaaS 인스턴스에 배포, VPC 내부에서 Redis Cluster 접속
- 🐳 **Docker** <br>
  컨테이너화를 통한 일관된 개발 및 배포 환경을 제공합니다.<br>
  → 애플리케이션과 Redis를 컨테이너로 구성하여 환경 독립성과 배포 편의성 확보 <br>

## 🗺️ LangGraph Execution Flow
<p align="center">
  <img src="사진/KakaoTalk_Photo_2025-07-31-06-52-44.png" alt="LangGraph flowchart" width="600"/>
</p>

## 🔄 Flow Details
🎯 **Decision Task**
- 목적: 사용자 질문을 적절한 Task로 분류
- 구현: 프롬프트 엔지니어링을 통한 라우팅<br>

⚙️ **Task Tools**
- 통합: Langchain Tool 데코레이터를 활용하여 HyperClova X와 연동
- 동작: HyperClova X가 사용자 질문을 분석하여 적합한 도구를 자동 선택 및 실행<br>
- 구성: 각 Task 특성에 맞는 전용 도구 세트<br>
  ```bash
  Task 1: 8개 도구
  answer_stock_query, answer_market_index,answer_market_ranking,answer_stock_compare,answer_market_stock_compare,answer_market_ratio,answer_market_compare
  ```
  ```bash
  Task 2: 1개 도구
  answer_task2
  ```
  ```bash
  Task 3: 5개 도구  
  rsi, detect_cross, price_vs_adj_ma, bollinger_bands, get_high_volume_stocks
  ```
🔧 **Specialized Technology (Task 5)**

## 🚀 API 사용법
**1️⃣ 서버 기동**
```bash
docker build -t agent-m .
docker rm -f agent-m
docker run -d -p 8000:8000 --env-file .env --name agent-m agent-m
```
**2️⃣ 헬스 체크**
```bash
curl http://49.50.128.78:8000/health
```
상태 반환 확인
```
{"status":"ok"}
```

**3️⃣ 질문 호출**
```bash
curl -G --data-urlencode "question=2025-02-25에 RSI가 30 이하인 종목은?" \ 
  http://49.50.128.78:8000/agent \
  -H "Authorization: Bearer $NCP_CLOVASTUDIO_API_KEY" \
  -H "X-NCP-CLOVASTUDIO-REQUEST-ID: req-001"
```

## 🏗️ 구현 과정
