from typing import List
from datetime import datetime, timedelta
from typing import Dict, Callable, List
from langchain.tools import tool
import pandas as pd
import json
import holidays

kr_holidays = holidays.SouthKorea()

from utils import *
from data_fetcher import *
    
# 1. 유틸: 연산자 함수 테이블
OPS: Dict[str, Callable] = {
    ">":  lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<":  lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "range": lambda a, min_val, max_val: (a >= min_val) & (a <= max_val)
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

def apply_operator(series, operator, value, min_value=None, max_value=None):
    """
    데이터프레임에 operator 조건을 적용하는 함수
    """
    if operator == "range":
        if min_value is None or max_value is None:
            raise ValueError("Range operator requires both min_value and max_value.")
        return OPS[operator](series, min_value, max_value)
    else:
        if value is None:
            raise ValueError(f"Operator '{operator}' requires a 'value'.")
        return OPS[operator](series, value)

# @tool("answer_task2", description="여러 조건(거래량, 등락률, 가격 등)에 따라 주식 종목을 스크리닝합니다. 입력은 아래 스키마에 맞는 dict(JSON)입니다.")
def answer_task2(q: dict) -> List[str]:
    """
    [주식 조건검색 스크리닝 함수]
    복수의 조건(등락률, 거래량, 가격 등)에 따라 주식 종목을 필터링하여, 조건을 모두 만족하는 종목명과 티커를 반환합니다.

    Args:
        q (dict): 아래 스키마에 맞는 dict. 예시는 아래 참고.

        스키마:
        {
          "type": string,              # (아래 type 분류 표 참고)
          "date": "YYYY-MM-DD",        # 조회 날짜
          "market": "KOSPI" | "KOSDAQ" | "ALL",  # 시장
          "conditions": [
            {
              "field": "change_rate" | "volume_change_rate" | "volume_abs" | "price",
              "operator": ">" | ">=" | "<" | "<=" | "range",
              "value": number | None,
              "min_value": number | None,
              "max_value": number | None,
              "unit": "percent" | "shares" | "won",
              "description": string
            }
          ],
          "keywords": [string, ...],     # 최대 5개, 핵심 명사·숫자 위주
          "complexity": "simple" | "complex",
          "confidence": number,          # 0.0-1.0
          "reasoning": string            # 30자 이하 요약
        }

        type 분류 표:
            "KOSPI_등락률", "KOSPI_가격범위", "KOSDAQ_거래량변화", "KOSDAQ_거래량", 
            "KOSDAQ_가격범위", "복합조건", "등락률", "거래량절대값", "거래량변화율", "가격범위"

        주요 field와 단위:
        - 등락률 → field: change_rate, unit: percent
        - 거래량 전날대비 → field: volume_change_rate, unit: percent
        - 거래량(100만주 등) → field: volume_abs, unit: shares (100만주 → 1000000)
        - 종가(만원 등) → field: price, unit: won (1만원 → 10000)
        
        연산자:
        - ~이상: '>='
        - ~초과: '>'
        - ~이하: '<='
        - ~미만: '<'
        - 범위: 'range', min_value, max_value 지정

        복잡도:
        - 조건 1개면 simple, 2개 이상이면 complex

    Returns:
        dict: {티커: 종목명, ...}
            - 예시: {"005930.KS": "삼성전자", "035720.KQ": "카카오"}
            - 조건을 만족하는 종목이 없으면 빈 dict 반환

    사용 예시:
    - "2024-07-18에 등락률이 +5% 이상인 종목을 모두 보여줘"
    - "2025-02-18에 종가가 20만원 이상 50만원 이하인 종목을 모두 보여줘"
    - "2025-06-20에 KOSPI 시장에서 거래량이 전날대비 100% 이상 증가한 종목을 모두 보여줘"
    - "2025-05-09에 등락률이 +5% 이상이면서 거래량이 전날대비 150% 이상 증가한 종목을 모두 보여줘"
    """
    print(f"DEBUG: answer_stock_screening called with query: {json.dumps(q, ensure_ascii=False)}")

    target_date_str = q.get("date")
    market_str = q.get("market", "ALL") 
    conditions = q.get("conditions", [])

    if not target_date_str or not conditions:
        print(f"DEBUG: Missing date or conditions in query.")
        return {"error": "날짜 또는 조건을 찾을 수 없습니다."}

    # 조사할 시장의 모든 티커를 가져오기 (utils.get_tickers 사용)
    # utils.get_tickers는 target_date를 인자로 받습니다.
    tickers = get_tickers(market_str, target_date_str)
    
    num_conditions = len(q['conditions'])

    condition_results: List[List[str]] = []

    stock_names = {}

    for i in range(num_conditions):

        date_range = DATE_RANGE[q['conditions'][i]['field']]

        need_col = FIELD_COLS[q['conditions'][i]['field']]

        tgt_date  = datetime.strptime(q["date"], "%Y-%m-%d")

        start_dt  = tgt_date - timedelta(days=5)            

        # 끝 날짜
        end_dt    = tgt_date + timedelta(days=1)          

        # 배치 다운로드
        # data = download_in_batches(tickers, start_dt, end_dt, batch_size=200)
        data = get_historical_data(tickers, start_dt, end_dt) # <---------------------------------Redis로 대체

        # 거래량 / 종가 계산 컬럼만 있는 데이터프레임
        try:
            only_need_col = data.xs(need_col, level=1, axis=1)
            
            if only_need_col.empty:
                print(f"DEBUG: answer_stock_screening: No data found for column '{need_col}'")
                return {"error": f"필요한 컬럼 '{need_col}'에 대한 데이터가 없습니다."}
            
            data.index = only_need_col.index.strftime("%Y-%m-%d")  
            tgt_date = pd.to_datetime(tgt_date).strftime("%Y-%m-%d")
            if tgt_date not in data.index:
                return f"{tgt_date} : {kr_holidays.get(tgt_date)}임으로 해당 날짜의 데이터가 존재하지 않습니다."
        except (KeyError, IndexError) as e:
            print(f"DEBUG: answer_stock_screening: Error processing data for column '{need_col}': {e}")
            return {"error": f"데이터 처리 중 오류가 발생했습니다: {e}"}

        # 전날 대비 거래량 / 등락률 계산
        try:
            if date_range == 2:
                only_need_col_edit = only_need_col.pct_change() * 100
                if len(only_need_col_edit) > 0:
                    final_data = only_need_col_edit.iloc[-1]
                    final_data = final_data.dropna()
                else:
                    print(f"DEBUG: answer_stock_screening: No data available for change rate calculation")
                    return {"error": "등락률 계산을 위한 데이터가 부족합니다."}
            else:
                if len(only_need_col) > 0:
                    final_data = only_need_col.iloc[-1]
                    final_data = final_data.dropna()
                else:
                    print(f"DEBUG: answer_stock_screening: No data available for field calculation")
                    return {"error": "필드 계산을 위한 데이터가 부족합니다."}
        except (IndexError, KeyError) as e:
            print(f"DEBUG: answer_stock_screening: Error accessing data: {e}")
            return {"error": f"데이터 접근 중 오류가 발생했습니다: {e}"}
            
        try:
            result = apply_operator(final_data, q['conditions'][i]['operator'], q['conditions'][i]['value'], q['conditions'][i]['min_value'], q['conditions'][i]['max_value'])

            # 조건 만족해서 True인 행의 Ticker들
            true_tickers = result[result == True].index.tolist()

            # 조건별 결과 저장
            condition_results.append(true_tickers)
        except (IndexError, KeyError) as e:
            print(f"DEBUG: answer_stock_screening: Error applying operator for condition {i}: {e}")
            return {"error": f"조건 {i+1} 적용 중 오류가 발생했습니다: {e}"}

    # ---------- 교집합 계산 ----------
    print(f"DEBUG: answer_stock_screening: condition_results: {condition_results}")
    
    if not condition_results:        
        print(f"DEBUG: answer_stock_screening: No condition results found. Returning empty result.")
        return {}

    # 조건이 1개면 그대로, 2개 이상이면 set 교집합
    try:
        if len(condition_results) == 1:
            final_tickers = condition_results[0]
            print(f"DEBUG: answer_stock_screening: Single condition result: {final_tickers}")
        else:
            # map(set, …) 으로 각 리스트를 집합으로 변환 후 reduce 로 교차
            from functools import reduce
            # 빈 리스트가 있는지 확인
            valid_results = [result for result in condition_results if result and len(result) > 0]
            if not valid_results:
                print(f"DEBUG: answer_stock_screening: No valid results for intersection")
                final_tickers = []
            else:
                final_tickers = list(
                    reduce(set.intersection, map(set, valid_results)))
                print(f"DEBUG: answer_stock_screening: Intersection result: {final_tickers}")
    except (IndexError, TypeError) as e:
        print(f"DEBUG: answer_stock_screening: Error calculating intersection: {e}")
        print(f"DEBUG: answer_stock_screening: condition_results: {condition_results}")
        return {"error": f"교집합 계산 중 오류가 발생했습니다: {e}"}

    # 최종 결과를 딕셔너리로 변환
    try:
        stock_names = {}
        print(f"DEBUG: answer_stock_screening: final_tickers type: {type(final_tickers)}, value: {final_tickers}")
        
        if final_tickers and isinstance(final_tickers, list) and len(final_tickers) > 0:
            for ticker in final_tickers:
                try:
                    # clean_ticker = ticker.replace('.KS', '').replace('.KQ', '')
                    # stock_name = ticker_to_name(clean_ticker)
                    stock_name = ticker_to_name(ticker, target_date_str) # <-----------------하윤이 ticker_to_name 적용
                    stock_names[ticker] = stock_name
                except (IndexError, KeyError, AttributeError) as e:
                    print(f"DEBUG: answer_stock_screening: Error processing ticker '{ticker}': {e}")
                    continue
        else:
            print(f"DEBUG: answer_stock_screening: No valid final_tickers found. Returning empty result.")
            return {}

        return stock_names
    except (IndexError, KeyError, TypeError) as e:
        print(f"DEBUG: answer_stock_screening: Error converting final results: {e}")
        print(f"DEBUG: answer_stock_screening: final_tickers: {final_tickers}")
        return {"error": f"최종 결과 변환 중 오류가 발생했습니다: {e}"}
        
task2_tools = [answer_task2]
