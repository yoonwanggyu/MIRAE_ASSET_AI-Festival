from typing import List
from datetime import datetime, timedelta
from typing import Dict, Callable, List

from utils import *
    
# 1. 유틸: 연산자 함수 테이블
OPS: Dict[str, Callable] = {
    ">":  lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<":  lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "range": lambda a, min_val, max_val: min_val <= a <= max_val
}

def apply_operator(df, operator, value, min_value=None, max_value=None):
    """
    데이터프레임에 operator 조건을 적용하는 함수
    """
    if operator == "range":
        return (df >= min_value) & (df <= max_value)
    else:
        return OPS[operator](df, value)

# 2. 유틸: yfinance 에서 필요한 칼럼
FIELD_COLS = {
    "change_rate":        "Close",
    "volume_change_rate": "Volume",
    "volume_abs":         "Volume",
    "price":              "Close",
}

DATE_RANGE = {
    "change_rate":        2,
    "volume_change_rate": 2,
    "volume_abs":         1,
    "price":              1,
}

def screen_stocks(q: dict) -> List[str]:
    """
    q : LLM JSON 파싱 결과.
    반환 : 모든 조건을 동시에 만족하는 종목 코드 리스트(중복 제거·정렬).
    """

    print(f"LLM의 질문 분석 결과 : {q}")

    # 조사할 시장
    tickers  = get_tickers(q)
    if not tickers:
        return []

    # 조건 수
    num_conditions = len(q['conditions'])
    print(f"조건 수 = 반복문 횟수 : {num_conditions}")

    condition_results: List[List[str]] = []

    stock_names = {}
    # 조건 수 만큼 개별적으로 돌기
    for i in range(num_conditions):

        print(f"{i+1}번째 반복문 돌아가는 중----------------------")

        date_range = DATE_RANGE[q['conditions'][i]['field']]
        print(f"date_range : {date_range}")

        # 거래량 / 종가 계산 컬럼 가져오기
        need_col = FIELD_COLS[q['conditions'][i]['field']]
        print(f"필요한 컬럼 : {need_col}")

        # 질문에 있는 날짜
        tgt_date  = datetime.strptime(q["date"], "%Y-%m-%d")
        print(f"타킷 날짜 : {tgt_date}")

        # 주말·휴일 여유
        start_dt  = tgt_date - timedelta(days=5)            
        print(f"조회 시작 날짜 : {start_dt}")

        # 끝 날짜
        end_dt    = tgt_date + timedelta(days=1)          
        print(f"조희 끝 날짜 : {end_dt}")

        # 배치 다운로드
        data = download_in_batches(tickers, start_dt, end_dt, batch_size=200)

        # 거래량 / 종가 계산 컬럼만 있는 데이터프레임
        only_need_col = data.xs(need_col, level=1, axis=1)

        # 전날 대비 거래량 / 등락률 계산
        if date_range == 2:
            only_need_col_edit = only_need_col.pct_change() * 100
            final_data = only_need_col_edit.iloc[-1]
            final_data = final_data.dropna()
            print("date_range = 2일 때 계산---------------------------")
            print(final_data.head(10))
        else:
            final_data = only_need_col.iloc[-1]
            final_data = final_data.dropna()
            print("date_range = 1일 때 계산---------------------------")
            print(final_data.head(10))

        # 연산자에 따른 계산 다르게
        def apply_operator(df, operator, value, min_value=None, max_value=None):
            """
            데이터프레임에 operator 조건을 적용하는 함수
            """
            if operator == "range":
                return (df >= min_value) & (df <= max_value)
            else:
                return OPS[operator](df, value)
            
        result = apply_operator(final_data, q['conditions'][i]['operator'], q['conditions'][i]['value'], q['conditions'][i]['min_value'], q['conditions'][i]['max_value'])

        # 조건 만족해서 True인 행의 Ticker들
        true_tickers = result[result == True].index.tolist()
        print("조건을 만족하는 ticker들 수:", len(true_tickers))
        # 조건별 결과 저장
        condition_results.append(true_tickers)

    # ---------- 교집합 계산 ----------
    if not condition_results:          # 보호 코드
        return {}

    # 조건이 1개면 그대로, 2개 이상이면 set 교집합
    if len(condition_results) == 1:
        final_tickers = condition_results[0]
    else:
        # map(set, …) 으로 각 리스트를 집합으로 변환 후 reduce 로 교차
        from functools import reduce
        final_tickers = list(
            reduce(set.intersection, map(set, condition_results)))

    print(f"최종 선별된 종목 수: {len(final_tickers)}")

    # 최종 결과를 딕셔너리로 변환
    stock_names = {}
    for ticker in final_tickers:
        clean_ticker = ticker.replace('.KS', '').replace('.KQ', '')
        stock_name = ticker_to_name.get(clean_ticker, ticker)
        stock_names[ticker] = stock_name

    return stock_names
