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

    # target_date_str = q.get("date")
    # market_str = q.get("market", "ALL") # 기본값 ALL
    # conditions = q.get("conditions", [])

    # if not target_date_str or not conditions:
    #     print(f"DEBUG: Missing date or conditions in query.")
    #     return {"error": "날짜 또는 조건을 찾을 수 없습니다."}

    # # 조사할 시장의 모든 티커를 가져오기 (utils.get_tickers 사용)
    # # utils.get_tickers는 target_date를 인자로 받습니다.
    # tickers = get_tickers(market_str, target_date_str)
    # if not tickers:
    #     print(f"DEBUG: No tickers found for market '{market_str}' on '{target_date_str}'.")
    #     return {"result": f"[{target_date_str}] {market_str} 시장에서 종목을 찾을 수 없습니다."}

    # # 조건 수
    # num_conditions = len(conditions)
    # all_matched_tickers = set(tickers) # 초기에는 모든 종목이 조건에 맞다고 가정

    # try:
    #     # 각 조건별로 필터링
    #     for i, condition in enumerate(conditions):
    #         field = condition.get("field")
    #         operator = condition.get("operator")
    #         value = condition.get("value")
    #         min_value = condition.get("min_value")
    #         max_value = condition.get("max_value")
    #         unit = condition.get("unit")
            
    #         print(f"DEBUG: Processing condition {i+1}: Field='{field}', Operator='{operator}', Value='{value}', Range=[{min_value}-{max_value}]")

    #         if not field or not operator:
    #             print(f"DEBUG: Missing field or operator in condition {i+1}.")
    #             return {"error": f"조건 {i+1}에 필수 필드(field, operator)가 누락되었습니다."}

    #         # 계산에 필요한 일 수 가져오기
    #         required_days = DATE_RANGE.get(field, 1)

    #         # 질문에 있는 날짜
    #         tgt_date_dt = datetime.strptime(target_date_str, "%Y-%m-%d")

    #         # 데이터 조회 시작 날짜 (등락률 등을 위해 과거 데이터 필요)
    #         # 넉넉하게 7일 전부터 가져오지만, required_days에 맞춰 조정
    #         start_dt = (tgt_date_dt - timedelta(days=max(required_days + 1, 7))).strftime("%Y-%m-%d")
    #         # 데이터 조회 종료 날짜 (당일 포함)
    #         end_dt = (tgt_date_dt + timedelta(days=1)).strftime("%Y-%m-%d") # yfinance는 end_date 전날까지 포함

    #         # 배치 다운로드 (data_fetcher.get_historical_data 사용)
    #         # get_historical_data는 tickers 리스트를 받습니다.
    #         data = get_historical_data(tickers, start_dt, end_dt)
            
    #         if data.empty:
    #             print(f"DEBUG: No historical data downloaded for '{market_str}' from {start_dt} to {end_dt}.")
    #             return f"공휴일임으로 해당 날짜의 데이터가 존재하지 않습니다."

    #         # 필요한 컬럼만 추출
    #         need_col = FIELD_COLS.get(field)
    #         if not need_col or need_col not in data.columns.get_level_values(1):
    #             print(f"DEBUG: Required column '{need_col}' not found in data for field '{field}'. Data columns: {data.columns.tolist()}")
    #             return {"error": f"데이터에서 필요한 컬럼({field})을 찾을 수 없습니다."}

    #         # MultiIndex에서 해당 컬럼 데이터만 추출 (예: ('005930.KS', 'Close'))
    #         col_data = data.xs(need_col, level=1, axis=1)
    #         col_data.index = col_data.index.strftime("%Y-%m-%d")
            
    #         # 최종 계산에 사용할 시리즈 (해당 날짜 기준)
    #         final_series = pd.Series(dtype=float)

    #         if field == 'change_rate':
    #             # 등락률 계산
    #             # 현재 날짜 및 이전 날짜의 종가 필요
    #             if target_date_str not in col_data.index:
    #                 print(f"DEBUG: Target date {target_date_str} not in index for change_rate calculation.")
    #                 matched_tickers_for_condition = set() # 조건 만족하는 종목 없음
    #             else:
    #                 current_day_prices = col_data.loc[target_date_str]
                    
    #                 # target_date_str 직전 거래일의 가격을 찾아야 함
    #                 prev_day_date_idx = col_data.index.get_loc(target_date_str) -1
    #                 if prev_day_date_idx < 0: # 이전 데이터가 없는 경우
    #                     print(f"DEBUG: No previous day data for change_rate calculation for {target_date_str}.")
    #                     matched_tickers_for_condition = set() # 조건 만족하는 종목 없음
    #                 else:
    #                     prev_day_prices = col_data.iloc[prev_day_date_idx]
    #                     # 등락률 계산: (현재 - 이전) / 이전 * 100
    #                     change_rates = ((current_day_prices - prev_day_prices) / prev_day_prices) * 100
    #                     final_series = change_rates.dropna()
    #                     matched_tickers_for_condition = set(apply_operator(final_series, operator, value, min_value, max_value).index.tolist())

    #         elif field == 'volume_change_rate':
    #             # 거래량 변화율 계산
    #             if target_date_str not in col_data.index:
    #                 print(f"DEBUG: Target date {target_date_str} not in index for volume_change_rate calculation.")
    #                 matched_tickers_for_condition = set()
    #             else:
    #                 current_day_volumes = col_data.loc[target_date_str]
    #                 prev_day_date_idx = col_data.index.get_loc(target_date_str) -1
    #                 if prev_day_date_idx < 0:
    #                     print(f"DEBUG: No previous day data for volume_change_rate calculation for {target_date_str}.")
    #                     matched_tickers_for_condition = set()
    #                 else:
    #                     prev_day_volumes = col_data.iloc[prev_day_date_idx]
    #                     volume_change_rates = ((current_day_volumes - prev_day_volumes) / prev_day_volumes) * 100
    #                     final_series = volume_change_rates.dropna()
    #                     matched_tickers_for_condition = set(apply_operator(final_series, operator, value, min_value, max_value).index.tolist())
    #         else: # volume_abs, price (등 당일 데이터만 필요한 경우)
    #             if target_date_str not in col_data.index:
    #                 print(f"DEBUG: Target date {target_date_str} not in index for '{field}'.")
    #                 matched_tickers_for_condition = set()
    #             else:
    #                 final_series = col_data.loc[target_date_str].dropna()
    #                 matched_tickers_for_condition = set(apply_operator(final_series, operator, value, min_value, max_value).index.tolist())
            
    #         # 현재 조건에 맞는 종목들과 전체 종목의 교집합 계산
    #         all_matched_tickers.intersection_update(matched_tickers_for_condition)
    #         print(f"DEBUG: Condition {i+1} processed. Matched tickers: {len(matched_tickers_for_condition)}. Current intersection: {len(all_matched_tickers)}")

    #         if not all_matched_tickers: # 중간에 교집합이 없으면 더 이상 진행할 필요 없음
    #             print(f"DEBUG: No tickers satisfy all conditions after condition {i+1}. Breaking loop.")
    #             break

    #     # 최종 결과를 딕셔너리로 변환
    #     final_result_dict = {}
    #     if all_matched_tickers:
    #         for ticker in all_matched_tickers:
    #             # utils.ticker_to_name에 target_date 전달
    #             stock_name = ticker_to_name(ticker, target_date_str) 
    #             # 해당 종목의 최종 값도 가져오기 (결과 보고용)
    #             final_value = final_series.get(ticker) if ticker in final_series.index else None
                
    #             # 값과 단위를 포함하여 반환 문자열 구성
    #             unit = ""
    #             if unit == "percent": unit = "%"
    #             elif unit == "shares": unit = "주"
    #             elif unit == "won": unit = "원"

    #             if final_value is not None:
    #                 final_result_dict[ticker] = f"{stock_name}: {final_value:,.2f}{unit}" # 값 포매팅
    #             else:
    #                 final_result_dict[ticker] = stock_name

    #     print(f"DEBUG: Screening complete. Final result dict: {json.dumps(final_result_dict, ensure_ascii=False)}")
    #     return {"result": list(final_result_dict.values()) if final_result_dict else f"[{target_date_str}] 조건에 맞는 종목이 없습니다."}

    # except ValueError as e:
    #     print(f"DEBUG: ValueError in answer_stock_screening: {e}")
    #     return {"error": f"조건 검색 오류: {e}"}
    # except KeyError as e:
    #     print(f"DEBUG: KeyError in answer_stock_screening: {e}")
    #     return {"error": f"데이터 키 오류: {e}. 요청 필드나 데이터 구조 확인 필요."}
    # except Exception as e:
    #     print(f"DEBUG: Unexpected error in answer_stock_screening: {e}", exc_info=True)
    #     return {"error": f"조건 검색 중 예상치 못한 오류 발생: {e}"}

    ######---------------------------------기존이 위에 코드. 위 코드 하나도 안건드리고 주서처리함. 아래는 foden 코드. 데이터 다운로드랑 ticker_to_name만 변경
    target_date_str = q.get("date")
    market_str = q.get("market", "ALL") # 기본값 ALL
    conditions = q.get("conditions", [])

    if not target_date_str or not conditions:
        print(f"DEBUG: Missing date or conditions in query.")
        return {"error": "날짜 또는 조건을 찾을 수 없습니다."}

    # 조사할 시장의 모든 티커를 가져오기 (utils.get_tickers 사용)
    # utils.get_tickers는 target_date를 인자로 받습니다.
    tickers = get_tickers(market_str, target_date_str)
    
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
        # data = download_in_batches(tickers, start_dt, end_dt, batch_size=200)
        data = get_historical_data(tickers, start_dt, end_dt) # <---------------------------------Redis로 대체

        # 거래량 / 종가 계산 컬럼만 있는 데이터프레임
        only_need_col = data.xs(need_col, level=1, axis=1)

        data.index = only_need_col.index.strftime("%Y-%m-%d")  
        tgt_date = pd.to_datetime(tgt_date).strftime("%Y-%m-%d")
        if tgt_date not in data.index:
            return f"{tgt_date} : {kr_holidays.get(tgt_date)}임으로 해당 날짜의 데이터가 존재하지 않습니다."

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
        # stock_name = ticker_to_name(clean_ticker)
        stock_name = ticker_to_name(clean_ticker, target_date_str) # <-----------------하윤이 ticker_to_name 적용
        stock_names[ticker] = stock_name

    return stock_names
        
task2_tools = [answer_task2]
