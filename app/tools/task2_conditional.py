# app/tools/task2_search.py

import pandas as pd
from typing import Dict
from langchain.tools import tool
from datetime import datetime, timedelta

from app.utils import parse_llm_json, get_latest_trading_day, ticker_to_name, name_to_ticker
from app.data_fetcher import fetch_batch_history


"""
주요 변경사항
parse_llm_json -> utils.py 파일로 이동
download_in_batches -> data_fetcher.py 파일로 이동
get_tickers -> 내부 로직으로 통합
screen_stocks -> @tool 데코레이터 적용
"""

@tool
def screen_stocks_by_conditions(llm_analyzed_json_string: str) -> Dict[str, str]:
    """
    LLM이 사용자의 복잡한 질문을 분석하여 생성한 JSON 형식의 조건을 입력받아,
    해당 조건들을 모두 만족하는 주식 목록을 필터링하여 반환합니다.
    """
    try:
        q = parse_llm_json(llm_analyzed_json_string)
        print(f"조건 검색 실행: {q}")

        # --- 1. 티커 목록 준비 ---
        # utils.py의 캐시된 KRX 목록을 활용하여 티커를 가져옵니다.
        from app.utils import _load_krx_tickers
        tickers_df = _load_krx_tickers()
        
        market = q.get("market", "ALL").upper()
        if market == "ALL":
            tickers_df["suffix"] = tickers_df["market"].apply(lambda x: ".KS" if x.upper() == "KOSPI" else ".KQ")
            tickers = (tickers_df["code"] + tickers_df["suffix"]).tolist()
        else:
            mdf = tickers_df[tickers_df["market"].str.upper() == market]
            suffix = ".KS" if market == "KOSPI" else ".KQ"
            tickers = (mdf["code"] + suffix).tolist()

        if not tickers:
            return {"message": "지정한 시장에 해당하는 종목이 없습니다."}

        # --- 2. 데이터 조회 ---
        # 필요한 모든 데이터를 한 번에 가져오기 위해 날짜 범위를 계산
        date_str = get_latest_trading_day(q.get("date", "오늘"))
        end_dt = pd.to_datetime(date_str) + timedelta(days=1)
        # 등락률 계산 등을 위해 넉넉하게 5일치 데이터를 가져옵니다.
        start_dt = end_dt - timedelta(days=6)

        data = fetch_batch_history(tickers, start_date=start_dt, end_date=end_dt)
        if data is None or data.empty:
            return {"message": "조건 검색에 필요한 데이터를 가져올 수 없습니다."}

        # --- 3. 조건별 필터링 ---
        final_mask = pd.Series(True, index=data.columns.get_level_values(0).unique())

        ops = {">": pd.Series.gt, ">=": pd.Series.ge, "<": pd.Series.lt, "<=": pd.Series.le}

        for cond in q.get("conditions", []):
            field = cond.get("field")
            operator = cond.get("operator")
            
            # 필드에 따라 데이터 가공
            if field in ["change_rate", "volume_change_rate"]:
                col = "Close" if field == "change_rate" else "Volume"
                series = data.xs(col, level=1, axis=1).pct_change().iloc[-1] * 100
            elif field in ["volume_abs", "price"]:
                col = "Volume" if field == "volume_abs" else "Close"
                series = data.xs(col, level=1, axis=1).iloc[-1]
            else:
                continue # 알 수 없는 필드는 건너뛰기

            series = series.dropna()
            
            # 조건에 맞는 mask 생성
            if operator == "range":
                mask = series.between(cond.get('min_value'), cond.get('max_value'))
            else:
                mask = ops[operator](series, cond.get('value'))
            
            # 최종 mask에 AND 연산으로 누적
            final_mask = final_mask & mask.reindex(final_mask.index, fill_value=False)

        # --- 4. 최종 결과 반환 ---
        final_tickers = final_mask[final_mask].index.tolist()
        
        if not final_tickers:
            return {"message": "지정한 모든 조건을 만족하는 주식을 찾지 못했습니다."}

        return {ticker: ticker_to_name(ticker) for ticker in final_tickers}

    except Exception as e:
        return {"error": f"조건 검색 중 오류 발생: {str(e)}"}