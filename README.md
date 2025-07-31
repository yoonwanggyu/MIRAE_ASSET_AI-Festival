<p align="center">
  <img src="사진/KakaoTalk_Photo_2025-07-31-07-36-41.png" alt="FIN" width="100%""/>

<div align=center>
  
**FIN문철**은 투자대법관으로서 정확한 주식 정보 조회와 <br>
투자 판단 지표를 제공하여 사용자의 투자 의사결정을 지원합니다.

1️⃣ 이정 : TASK5 내용 써줘.....<br>
2️⃣ 이정 :표지 사진 넣어줘....<br>
3️⃣ 하윤 : API 사용법 / 구현 과정 써줘...<br>
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
├── 📂 data/                              # 데이터 저장 디렉토리
│   └── 📄 krx_tickers_with_market.csv    # 한국거래소 종목 코드 및 시장 정보
├── 📂 langgraph/                         # LangGraph 기반 AI 에이전트 모듈
│   ├── 📄 agent_core.py                  # 에이전트 핵심 로직 및 워크플로우
│   ├── 📄 nodes.py                       # 그래프 노드 정의 (각 처리 단계)
│   └── 📄 state.py                       # 에이전트 상태 관리 및 데이터 구조
├── 📂 tools/                             # 작업별 도구 모음
│   ├── 📄 task1_tools.py                 # 1단계 작업용 도구들
│   ├── 📄 task2_tools.py                 # 2단계 작업용 도구들
│   └── 📄 task3_tools.py                 # 3단계 작업용 도구들
├── 📄 .gitignore                         # Git 버전 관리 제외 파일 목록
├── 📄 Dockerfile                         # Docker 컨테이너 빌드 설정
├── 📄 data_fetcher.py                    # 외부 데이터 수집 및 처리
├── 📄 llm.py                             # LLM 모델 설정 및 인터페이스
├── 📄 main.py                            # 애플리케이션 진입점 (메인 실행 파일)
├── 📄 prompt.py                          # AI 프롬프트 템플릿 관리
├── 📄 redis_connector.py                 # Redis 캐시 연결 및 관리
├── 📄 utils.py                           # 공통 유틸리티 함수들
└── 📄 requirements.txt                   # Python 패키지 의존성 목록
```

## ⚙️ Tech Stack Overview
- 🧠 **LLM : HyperClova X**<br>
  네이버의 대규모 언어모델로, 한국어에 특화된 고성능 AI 서비스를 제공합니다.<br>
  → 투자 관련 질의응답, 주식 분석, 금융 데이터 해석 등 전문적인 투자 상담 서비스의 핵심 엔진으로 활용

- 🔄 **LangGraph** <br>
  상태 기반 LLM 프레임워크로, 복잡한 에이전트 워크플로우를 유연하게 설계할 수 있습니다.<br>
  → Agentic RAG 흐름(Task 분기 → Tool 호출 -> 답변 생성)을 구현<br>

- ⚡ **Redis** <br>
  고성능 인메모리 데이터 스토어로, 캐싱과 세션 관리를 담당합니다. <br>
  → yfinance 데이터 (2024.01 ~ 2025.07) 데이터 적재 <br>
  
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
1️⃣ 레포지토리 클론
```bash
git clone 
cd your-repo-name
```
2️⃣ 필수 라이브러리 설치
```bash
pip install -r requirements.txt
```

3️⃣ 환경 변수 설정 (.env 파일 생성)<br>
```bash
# GPT API 설정
OPENAI_API_KEY=''

# Neo4J 설정
NEO4J_URI=''
DATABASE=''
AUTH_LINK=''

# Pinecone 설정
PINECONE_API_KEY=''

# Slack MCP 설정
SLACK_BOT_TOKEN=''
SLACK_TEAM_ID=''
```

4️⃣ mcp_client.py 실행을 위한 파이썬 경로 설정
```bash
"command": "본인 로컬 PYTHON 경로"
```

5️⃣ LangGraph 기반 챗봇 로직 실행
```bash
python main.py
```
