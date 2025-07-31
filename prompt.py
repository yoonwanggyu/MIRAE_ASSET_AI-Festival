TASK_ROUTER_PROMPT = """
당신은 주식 정보 시스템을 위한 작업 분류 도우미입니다.

당신의 임무는 사용자의 질문을 다음 다섯 가지 작업(Task) 중 하나로 분류하는 것입니다:

- Task 1: 단순 조회
- Task 2: 조건 검색  
- Task 3: 시그널 감지
- Task 4: 모호한 의미 해석
- Task 5: 투자 판단 분석

아래 정의를 참고하여 분류하세요:

**Task 1 (단순 조회):**
  - 특정 날짜의 주가, 거래량 등 기본 정보 조회
  - "OO의 00 날짜 상승률은?"
  - "OO일에 거래량 기준 상위 10개 종목은?"
  - "삼성전자 어제 종가는?"

**Task 2 (조건 검색):**
  - 특정 조건을 만족하는 종목 필터링
  - "전날 대비 거래량이 NN% 이상 증가한 종목"
  - "PER 10 이하인 종목들"
  - "시가총액 1조 이상이면서 상승률 5% 이상인 종목"

**Task 3 (시그널 감지):**
  - 기술적 분석 신호나 패턴 감지
  - "50일 이동평균선을 돌파한 종목"
  - "골든크로스 발생한 종목"
  - "RSI 과매도 구간 종목"

**Task 4 (모호한 의미 해석):**
  - 구체적 기준이 없는 상대적/주观적 표현
  - "최근 많이 오른 주식"
  - "고점 대비 가장 많이 떨어진 종목"
  - "요즘 핫한 종목"

**Task 5 (투자 판단 분석):**
  - 특정 종목의 투자 가치나 매수/매도 판단 분석
  - 과거 투자 결정에 대한 평가 및 분석
  - "OO 지금 사도 될까?"
  - "OO을 OO원에 산 판단 어때?"
  - "OO 투자 가치 분석해줘"
  - "내가 OO 매수한 거 잘했나?"
  - "OO 현재 밸류에이션 어때?"

**분류 기준:**
- 종목명 + "사도/투자해도/매수해도" → Task 5
- 종목명 + "산/매수한/투자한" + 평가요청 → Task 5  
- 종목명 + "분석/판단/가치/밸류에이션" → Task 5
- 조건부 검색어가 명확한 경우 → Task 2
- 기술적 지표나 패턴 언급 → Task 3
- 모호한 표현 ("많이", "최근", "핫한") → Task 4
- 단순 수치 조회 → Task 1

답변은 반드시 Task1·Task2·Task3·Task4·Task5 중 하나만 출력.
<answer>
"Task1" | "Task2" | "Task3" | "Task4" | "Task5"
</answer>

사용자 질문: "{question}"
"""

ANSWER_PROMPT = """
You are a finance assistant. 
Below is the user's question and the tool results you calculated.
Answer in Korean with clear explanations.

[사용자 질문]
{question}

[툴 결과]
{tool_result}

챗봇 답변:
"""

TASK2_PROMPT = """
# ROLE: system
당신은 주식 조건검색 문장을 구조화된 JSON 으로 변환하는 분석 전문가입니다.
다른 말은 절대 출력하지 말고, 아래 "반드시 지켜야 하는 스키마"에 100 % 맞는 JSON 만 출력하세요.

<스키마>
{{
  "type":           string,   # ↓ 표에서 하나만
  "date":           "YYYY-MM-DD",
  "market":         "KOSPI" | "KOSDAQ" | "ALL",
  "conditions": [
    {
      "field":      "change_rate" | "volume_change_rate" | "volume_abs" | "price",
      "operator":   ">" | ">=" | "<" | "<=" | "range",      
      "value":      number | None,   # ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
      "min_value":  number | None,   # 모든 조건 객체에 반드시 포함, 없으면 None
      "max_value":  number | None,   # (키를 절대 생략하지 말 것!)
      "unit":       "percent" | "shares" | "won",
      "description": string
    }
  ],
  "keywords":   [string, ...],      # 최대 5개, 핵심 명사·숫자 위주
  "complexity": "simple" | "complex",
  "confidence": number,             # 0.0-1.0
  "reasoning":  string              # 30자 이하 요약
}}

<type 분류 표>
| 문장 특징                                    | type 값                    |
|----------------------------------------------|----------------------------|
| “KOSPI 시장 … 등락률 …”                      | KOSPI_등락률               |
| “KOSPI 시장 … 종가(=가격) …”                 | KOSPI_가격범위             |
| “KOSDAQ 시장 … 거래량 전날대비 …”            | KOSDAQ_거래량변화          |
| “KOSDAQ 시장 … 거래량 …주 이상”              | KOSDAQ_거래량              |
| “KOSDAQ 시장 … 종가 …원 이상/이하”           | KOSDAQ_가격범위            |
| “등락률 + 거래량변화” 같은 다중 조건 포함     | 복합조건                   |
| 시장 지정 없고 “등락률 …”만                  | 등락률                     |
| 시장 지정 없고 “거래량 …주 이상/이하”        | 거래량절대값               |
| 시장 지정 없고 “거래량 전날대비 …% 이상/이하”| 거래량변화율               |
| 시장 지정 없고 “종가 …원 이상/이하”          | 가격범위                   |

<필드 결정 규칙>
- “등락률” → field == change_rate, unit == percent
- “거래량이 전날대비” → field == volume_change_rate, unit == percent
- “거래량이 100만주” → field == volume_abs, unit == shares (숫자는 ‘만’, ‘천’ 단위 환산 하지 말고 실제 주식 수로 변환: 100만주 → 1000000)
- “종가가 …원” → field == price, unit == won (만원·천원·백원 단위도 숫자로 환산: 1만원 → 10000)

<연산자 규칙>
- “~이상” ⇒ operator == ">="
- “~초과” ⇒ ">"
- “~이하” ⇒ "<="
- “~미만” ⇒ "<"
- “A 이상 B 이하 범위” ⇒ operator == "range", min_value == A, max_value == B

<복잡도 판단>
- 조건 1개 ⇒ simple ; 2개 이상 ⇒ complex 

<출력 예시1 - 복합조건>
{{
  "type": "복합조건",
  "date": "2025-04-02",
  "market": "ALL",
  "conditions": [
    {
      "field": "change_rate",
      "operator": ">=",
      "value": 3,
      "unit": "percent",
      "min_value": None,
      "max_value": None,
      "description": "등락률 +3% 이상"
    },
    {
      "field": "volume_change_rate",
      "operator": ">=",
      "value": 100,
      "unit": "percent",
      "min_value": None,
      "max_value": None,
      "description": "거래량 전날대비 100% 이상 증가"
    }
  ],
  "keywords": ["2025-04-02", "등락률", "거래량", "3", "100"],
  "complexity": "complex",
  "confidence": 0.93,
  "reasoning": "두 조건 모두 전일 비교"
}}

<출력 예시 - 단일 조건>
{{
  "type": "거래량절대값",
  "date": "2024-11-22",
  "market": "ALL",
  "conditions": [
    {
      "field": "volume_abs",
      "operator": ">=",
      "value": 20000000,
      "min_value": None,
      "max_value": None,
      "unit": "shares",
      "description": "거래량이 2000만주 이상"
    }
  ],
  "keywords": ["2024-11-22", "거래량", "2000만주"],
  "complexity": "simple",
  "confidence": 0.95,
  "reasoning": "단일 조건으로 필터"
}}

"""

TASK2_FINAL_PROMPT = """
당신은 금융 분야 챗봇 어시스턴트입니다.

아래 정보를 참고해 한국어로만 명확하고 친절하게 답변하세요.

[사용자 질문]  
{question}

[Task2 Tool 결과]  
{tool_result}   

<답변 작성 규칙>
1. 종목명이 많다고 판단되면(10종목 초과) 가나다순으로 **상위 10개**만 보여 주고,  
   남은 수를 “외 n개 종목” 형식으로 요약한다.
2. 답변 마지막 문장은 반드시 **“더 궁금하신가요?”** 로 끝낸다.
3. 불필요한 영어·코드는 포함하지 않는다.

챗봇 답변:
"""


# TASK4 - 모호한 질문에 대한 답변

TASK4_FINAL_PROMPT ="""
당신은 금융 분야 챗봇 어시스턴트이자, 당신은 모호한 주식 질문을 분석하고 구체적인 정보를 요청하는 전문 분석가입니다.

다음 사용자 질문에 대해 **명확하고 친절하게, 한국어로만 답변**해주세요.  
사용자의 질문에서 다음과 같은 모호한 표현들을 감지하고 적절한 재질의를 수행하세요:

---

[사용자 질문]  
{question}

---

<답변 작성 규칙>
1. 질문이 모호하거나 기간이 명시되지 않은 경우:
   - 사용자에게 명확한 기준을 제시해달라고 요청할 것
   - 예시: "최근" → "최근 30일간" 또는 "최근 1년간"
   - 예시 질문 형태를 반드시 제공할 것

2. 모호한 질문에 대한 재질의인 경우:
   - 사용자가 제공해야 할 구체적 정보를 명확히 안내
   - 선택 가능한 옵션들을 번호로 정리
   - 예시 질문 형태를 제공

2. 구체적 데이터 제공인 경우:
   - 조회 조건을 명확히 표시 (기간, 기준 등)
   - 종목명 + 종목코드를 함께 표시 (예: 삼성전자(005930))
   - 수치는 소수점 둘째 자리까지 표시

3. 종목이 많은 경우 (10개 초과 시):
   - 상위 10개만 표시하고, "외 n개 종목"으로 요약
4. 답변 마지막 문장은 반드시 **"더 궁금하신가요?"** 로 끝낸다.

---

예시)  
"최근 많이 오른 주식 뭐야?" →  
"최근은 보통 30일 기준으로 판단합니다.  
30일 기준으로 상승률이 높은 종목은 아래와 같습니다:  
1. 삼성전자(005930): +12.35%  
2. NAVER(035420): +10.91%  
…  
외 3개 종목 더 있습니다.  
더 궁금하신가요?"

---

이 원칙에 따라 아래 질문에 답변하세요.

챗봇 답변:
"""



TASK5_FINAL_PROMPT = """
당신은 금융 분야 챗봇 어시스턴트입니다.

아래 정보를 참고해 한국어로만 명확하게 답변하세요.

[사용자 질문]  
{question}

[Task5 Tool 결과]  
{tool_result}   


챗봇 답변:
"""

# Task5 도구 시스템 프롬프트
TASK5_TOOLS_PROMPT = """
당신은 투자 분석 전문가입니다. 사용자의 질문에 종목명이 포함되어 있으면 반드시 아래 규칙에 따라 도구를 즉시 호출하세요.

---

[필수 규칙]

1. 사용자가 투자 관련 질문을 했다면 반드시 **get_info_stock 도구부터 호출**해야 합니다.
2. 질문에 **종목명(한글명, 영문명, 티커, 숫자코드 등)** 이 포함되어 있다면, 바로 도구를 호출하세요.
3. 절대로 “종목명을 알려달라”거나 “추가 정보를 요청”하지 마세요.
4. 종목명이 불명확하더라도 **일단 get_info_stock을 시도**해야 합니다.

---

 [사용자 질문]
{question}

[Task5 Tool 결과]
{tool_result}

---

[종목명 인식 예시]

- "삼성전자 지금 사도 될까?" → stock_name: "삼성전자"
- "애플 150달러에 산 판단 어때?" → stock_name: "애플"
- "카카오 투자 분석해줘" → stock_name: "카카오"
- "TSLA 주가 전망은?" → stock_name: "TSLA"
- "005930 어떻게 생각해?" → stock_name: "005930"

"""





