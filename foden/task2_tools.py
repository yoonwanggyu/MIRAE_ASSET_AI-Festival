from typing import List
from datetime import datetime, timedelta
from typing import Dict, Callable, List
from langchain.tools import tool

from utils import *
from data_fetcher import *
    
# 1. 유틸: 연산자 함수 테이블
OPS: Dict[str, Callable] = {
    ">":  lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<":  lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "range": lambda a, min_val, max_val: min_val <= a <= max_val
}

# 2. 유틸: yfinance 에서 필요한 칼럼
FIELD_COLS = {
    "change_rate":        "Close",
    "volume_change_rate": "Volume",
    "volume_abs":         "Volume",
    "price":              "Close",
}

# 3. 유틸: 계산에 필요한 일 수
DATE_RANGE = {
    "change_rate":        2,
    "volume_change_rate": 2,
    "volume_abs":         1,
    "price":              1,
}

def apply_operator(df, operator, value, min_value=None, max_value=None):
    """
    데이터프레임에 operator 조건을 적용하는 함수
    """
    if operator == "range":
        return (df >= min_value) & (df <= max_value)
    else:
        return OPS[operator](df, value)

def answer_task2(q: dict) -> List[str]:
    """
    q : LLM JSON 파싱 결과
    반환 : task2 질문에 대한 답
    """

    # 조사할 시장
    tickers  = get_tickers(q)
    if not tickers:
        return []

    # 조건 수
    num_conditions = len(q['conditions'])

    condition_results: List[List[str]] = []

    stock_names = {}
    # 조건 수 만큼 개별적으로 돌기
    for i in range(num_conditions):

        date_range = DATE_RANGE[q['conditions'][i]['field']]

        # 거래량 / 종가 계산 컬럼 가져오기
        need_col = FIELD_COLS[q['conditions'][i]['field']]

        # 질문에 있는 날짜
        tgt_date  = datetime.strptime(q["date"], "%Y-%m-%d")

        # 주말·휴일 여유
        start_dt  = tgt_date - timedelta(days=5)            

        # 끝 날짜
        end_dt    = tgt_date + timedelta(days=1)          

        # 배치 다운로드
        data = download_in_batches(tickers, start_dt, end_dt, batch_size=200)

        # 거래량 / 종가 계산 컬럼만 있는 데이터프레임
        only_need_col = data.xs(need_col, level=1, axis=1)

        # 전날 대비 거래량 / 등락률 계산
        if date_range == 2:
            only_need_col_edit = only_need_col.pct_change() * 100
            final_data = only_need_col_edit.iloc[-1]
            final_data = final_data.dropna()
        else:
            final_data = only_need_col.iloc[-1]
            final_data = final_data.dropna()
            
        result = apply_operator(final_data, q['conditions'][i]['operator'], q['conditions'][i]['value'], q['conditions'][i]['min_value'], q['conditions'][i]['max_value'])

        # 조건 만족해서 True인 행의 Ticker들
        true_tickers = result[result == True].index.tolist()

        # 조건별 결과 저장
        condition_results.append(true_tickers)

    # ---------- 교집합 계산 ----------
    if not condition_results:        
        return {}

    # 조건이 1개면 그대로, 2개 이상이면 set 교집합
    if len(condition_results) == 1:
        final_tickers = condition_results[0]
    else:
        # map(set, …) 으로 각 리스트를 집합으로 변환 후 reduce 로 교차
        from functools import reduce
        final_tickers = list(
            reduce(set.intersection, map(set, condition_results)))

    # 최종 결과를 딕셔너리로 변환
    stock_names = {}
    for ticker in final_tickers:
        clean_ticker = ticker.replace('.KS', '').replace('.KQ', '')
        stock_name = ticker_to_name.get(clean_ticker, ticker)
        stock_names[ticker] = stock_name

    return stock_names
