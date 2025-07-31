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
├── 📄 .gitignore                         # 제외 파일 목록
├── 📄 Dockerfile                         # Docker 컨테이너 빌드 설정
├── 📄 data_fetcher.py                    # Redis 데이터 수집 및 처리
├── 📄 main.py                            # 메인 실행 파일
├── 📄 prompt.py                          # AI 프롬프트 템플릿 관리
├── 📄 redis_connector.py                 # Redis 캐시 연결 및 관리
├── 📄 utils.py                           # 공통 유틸리티 함수들
├── 📄 upload_to_redis.py                 # Redis 데이터 업로드 스크립트
└── 📄 requirements.txt                   # Python 패키지 의존성 목록
```

## ⚙️ System Architecture
<p align="center">
  <img src="사진/sys_arch.png" alt="FIN" width="100%""/>

### ⚒️ Tech Stack Overview
- 🧠 **LLM : HyperClova X**<br>
  네이버의 대규모 언어모델로, 한국어에 특화된 고성능 AI 서비스를 제공합니다.<br>
  → 투자 관련 질의응답, 주식 분석, 금융 데이터 해석 등 전문적인 투자 상담 서비스의 핵심 엔진으로 활용

- 🔄 **LangGraph** <br>
  상태 기반 LLM 프레임워크로, 복잡한 에이전트 워크플로우를 유연하게 설계할 수 있습니다.<br>
  → Agentic RAG 흐름(Task 분기 → Tool 호출 -> 답변 생성)을 구현<br>

- ⚡ **NCloud Cloud DB for Cache(Redis Cluster)** <br>
  고성능 인메모리 데이터 스토어로, 캐싱과 세션 관리를 담당합니다. <br>
  → yfinance 데이터 (2024.01 ~ 2025.07) 데이터 적재 <br>
  → 발전 방향:
    - 대화 세션 관리를 통한 메모리 캐싱
    - 배치 컨테이너 구축 및 데이터 TTL 설정으로, 최근 주식 데이터를 주기적으로 업데이트

- 🏦 **Yahoo Finance API** <br>
  Yahoo Finance의 공개 API를 활용한 Python 라이브러리로, 실시간 및 과거 주식 데이터를 제공합니다. <br>
  → Redis에 캐싱된 데이터가 없을 경우 yfinance API를 호출하여 데이터 로드 <br>

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
  <img src="사진/C46F42F9-43EA-4169-95B1-05CCE65E79BE.jpeg" alt="LangGraph flowchart" width="600"/>
</p>

## 🔄 Flow Details
🎯 **Decision Task**
- 목적: 사용자 질문을 적절한 Task로 분류
- 구현: 프롬프트 엔지니어링을 통한 라우팅<br>

⚙️ **Task Tools (Task1 ~ Task3)**
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

## 📊 YFinance API 사용 예시

### 🔧 기본 설치 및 임포트
```python
pip install yfinance
import yfinance as yf
```

### 📈 단일 종목 데이터 조회
```python
# 삼성전자 주가 데이터 조회 (KOSPI: .KS)
samsung = yf.download("005930.KS", start="2024-01-01", end="2024-12-31")
print(samsung.head())

# 네이버 주가 데이터 조회 (KOSDAQ: .KQ)
naver = yf.download("035420.KQ", start="2024-01-01", end="2024-12-31")
print(naver.head())
```

### 🔄 다중 종목 동시 조회
```python
# 여러 종목을 리스트로 전달하여 동시 조회
tickers = ["005930.KS", "035420.KQ", "000660.KS"]  # 삼성전자, 네이버, SK하이닉스
data = yf.download(tickers, start="2024-01-01", end="2024-12-31", 
                   group_by="ticker", progress=False, threads=True)
print(data.head())
```

### ⚡ 실시간 데이터 조회
```python
# 실시간 주가 정보 조회
ticker = yf.Ticker("005930.KS")
info = ticker.info
print(f"현재가: {info.get('currentPrice')}")
print(f"시가총액: {info.get('marketCap')}")
print(f"거래량: {info.get('volume')}")
```

### 📊 프로젝트에서의 활용 패턴
```python
# data_fetcher.py에서 사용되는 패턴
def fetch_from_yfinance(tickers, start_dt, end_dt) -> pd.DataFrame:
    """yfinance API를 통해 데이터를 다운로드합니다."""
    return yf.download(
        tickers=tickers, 
        start=start_dt, 
        end=end_dt, 
        interval="1d",
        group_by="ticker", 
        progress=False, 
        threads=True, 
        auto_adjust=False,
    )
```

### 🎯 주요 파라미터 설명
- `tickers`: 조회할 종목 코드 (단일 문자열 또는 리스트)
- `start/end`: 조회 시작/종료 날짜 (YYYY-MM-DD 형식)
- `interval`: 데이터 간격 ("1d", "1wk", "1mo" 등)
- `group_by`: 다중 종목 시 그룹화 방식 ("ticker" 권장)
- `progress`: 진행률 표시 여부
- `threads`: 멀티스레딩 사용 여부 (성능 향상)
- `auto_adjust`: 자동 조정 여부 (배당금, 분할 등 반영)

### ⚠️ 주의사항
- Yahoo Finance는 공식 API가 아니므로 안정성 보장 없음
- 과도한 요청 시 일시적 차단 가능성
- 한국 주식은 `.KS`(KOSPI), `.KQ`(KOSDAQ) 접미사 필수
- 실시간 데이터는 시장 운영 시간에만 정확함