import yfinance as yf, pandas as pd
from datetime import datetime, timedelta
import calendar
from langchain.tools import tool

from utils import *
from data_fetcher import *
import holidays
    
kr_holidays = holidays.SouthKorea()


field_kor_to_eng = {
    "시가": "Open",
    "고가": "High",
    "저가": "Low",
    "종가": "Close",
    "등락률": "change_rate",
    "거래량": "Volume",
    "시가총액": "marketCap"
}

@tool("answer_stock_query", description="특정 날짜에 특정 종목의 종가, 시가, 고가, 저가, 등락률 계산")
def answer_stock_query(stock: str, target_date: str, field: str):
    """
    특정 종목(stock)의 특정 날짜(target_date)의 Open/Close/Low/High/change_rate(field)를 반환합니다.

    Args:
        stock (str): 종목명, 예시 '한양증권'
        target_date (str): 날짜, 예시 '2025-03-12' (YYYY-MM-DD 형식)
        field (str): 조회할 항목. 아래 값 중 하나여야 합니다.
            - "Open"  : 시가
            - "High"  : 고가
            - "Low"   : 저가
            - "Close" : 종가
            - "change_rate" : 등락률(전일 종가 대비 등락률, %)
            - "Volume" : 거래량
            - "marketCap" : 시가총액

    Returns:
        str: 해당 날짜와 필드에 대한 값. 예를 들어,
            - "[2025-03-12] 종가: 13,800원"
            - "[2025-03-12] 시가: 14,000원"
            - "[2025-03-12] 등락률: -1.65%"
            - "[2025-03-12] 시가총액: 100,000,000,000원"

    예시 질문:
    - "KOSPI에서 롯데지주의 2024-07-05 종가는?"
    - "삼영엠텍의 2025-05-15 등락률은?"
    - "한네트의 2024-11-20 시가는?"
    - "도화엔지니어링의 2025-06-25 고가는?"
    - "삼성전자의 2025-06-25 시가총액은?"
    """

    # field_eng = field_kor_to_eng.get(field, field)
    
    # # name_to_ticker와 name_to_market을 사용하여 코드와 시장을 얻습니다.
    # # 이 과정에서 utils.py의 개선된 로직(CSV 먼저, 다음 Redis GET)이 사용됩니다.
    # try:
    #     ticker = name_to_ticker(stock, target_date) # 티커 (예: 005930.KS)
    #     # ticker에서 코드만 추출
    #     code = ticker.split('.')[0]
    #     # name_to_market을 사용하여 시장 정보를 얻습니다.
    #     market = name_to_market(stock, target_date) # 시장 (예: KOSPI)
    # except ValueError as e:
    #     print(f"DEBUG: answer_stock_query: Failed to get ticker/market for '{stock}' on '{target_date}': {e}")
    #     return f"[{target_date}] {stock} 데이터를 조회할 수 없습니다. (종목명/날짜 오류: {e})"


    # # 데이터 조회 함수를 get_single_day_data로 교체하고 필요한 정보 전달
    # # 등락률 계산을 위해 최소 2일의 데이터가 필요하므로 get_single_day_data는 7일치 가져옴
    # data = get_single_day_data(stock, code, market, target_date)

    # if data.empty or target_date not in data.index.strftime('%Y-%m-%d'):
    #     print(f"DEBUG: answer_stock_query: Data is empty or target date '{target_date}' not in index for '{stock}'.")
    #     return f"[{target_date}] {stock} 데이터를 조회할 수 없습니다."

    # # MultiIndex에서 해당 티커 데이터만 선택
    # if isinstance(data.columns, pd.MultiIndex):
    #     # target_date에 대한 데이터만 선택
    #     if target_date not in data.index.strftime('%Y-%m-%d'):
    #         return f"{target_date} : {kr_holidays.get(target_date)}임으로 해당 날짜의 데이터가 존재하지 않습니다."
        
    #     stock_data = data.loc[data.index.strftime('%Y-%m-%d') == target_date].xs(ticker, level=0, axis=1)
    #     stock_data.index = stock_data.index.strftime("%Y-%m-%d") # 인덱스 날짜 문자열로 변환
        
    #     # 등락률 계산을 위해 이전 날짜의 데이터가 필요하다면,
    #     # get_single_day_data에서 가져온 데이터 전체를 사용해야 합니다.
    #     # 따라서 stock_data = data.xs(ticker, level=0, axis=1) 형태로 가져온 후
    #     # 특정 날짜를 .loc으로 접근하는 방식이 더 안전합니다.
        
    #     # 다시 변경하여 get_single_day_data가 반환하는 전체 기간 DataFrame에서 티커 선택
    #     full_stock_data_df = data.xs(ticker, level=0, axis=1)
    #     full_stock_data_df.index = full_stock_data_df.index.strftime("%Y-%m-%d")

    # else: # 단일 티커 데이터일 경우 (이 경우는 거의 없음, MultiIndex 예상)
    #     full_stock_data_df = data
    #     full_stock_data_df.index = full_stock_data_df.index.strftime("%Y-%m-%d")

    # # 등락률 계산
    # if field_eng == 'change_rate':
    #     # 등락률 계산을 위한 데이터 준비
    #     # target_date 이전의 가장 가까운 거래일 종가를 찾아야 합니다.
    #     target_date_dt = datetime.strptime(target_date, "%Y-%m-%d").date()
        
    #     # full_stock_data_df에서 target_date와 그 이전 날짜 데이터만 필터링
    #     relevant_data = full_stock_data_df.loc[full_stock_data_df.index.to_series().apply(lambda x: datetime.strptime(x, "%Y-%m-%d").date() <= target_date_dt)]
    #     relevant_data = relevant_data.sort_index()

    #     if len(relevant_data) < 2:
    #         print(f"DEBUG: answer_stock_query: Not enough data for change_rate calculation. Rows: {len(relevant_data)}")
    #         return f"[{target_date}] 등락률을 계산할 전일 데이터가 없습니다."
        
    #     # target_date의 종가
    #     now_close = relevant_data.loc[target_date, 'Close']
        
    #     # target_date 직전 거래일의 종가
    #     prev_close = relevant_data.iloc[-2]['Close'] # 가장 마지막에서 두 번째 행
        
    #     if pd.isna(now_close) or pd.isna(prev_close) or prev_close == 0:
    #         return f"[{target_date}] 등락률을 계산할 데이터가 유효하지 않습니다."

    #     change_rate = ((now_close - prev_close) / prev_close) * 100
    #     print(f"DEBUG: answer_stock_query: Calculated change_rate for '{stock}' on '{target_date}': {change_rate:.2f}%")
    #     return f"[{target_date}] {stock} 등락률: {round(change_rate, 2)}%"
    
    # # 기타 필드 조회 (시가, 고가, 저가, 종가, 거래량, 시가총액)
    # field_map = {"Close": "종가", "Open": "시가", "High": "고가", "Low": "저가", "Volume": "거래량", "marketCap": "시가총액"}
    # label = field_map.get(field_eng, field_eng)
    
    # # 특정 날짜의 데이터만 선택
    # if target_date not in full_stock_data_df.index:
    #     print(f"DEBUG: answer_stock_query: Target date '{target_date}' not found in stock_data index for '{stock}'.")
    #     return f"[{target_date}] {stock} {label} 데이터를 찾을 수 없습니다."

    # result = full_stock_data_df.loc[target_date, field_eng]
    
    # if pd.isna(result):
    #     return f"[{target_date}] {stock} {label} 데이터가 유효하지 않습니다."

    # unit = "주" if field_eng == "Volume" else "원"
    # if field_eng == "Volume" or field_eng == "marketCap":
    #     print(f"DEBUG: answer_stock_query: Retrieved '{field_eng}' for '{stock}' on '{target_date}': {result:,}{unit}")
    #     return f"[{target_date}] {stock} {label}: {int(result):,}{unit}"
    # else:
    #     print(f"DEBUG: answer_stock_query: Retrieved '{field_eng}' for '{stock}' on '{target_date}': {result:,.0f}{unit}")
    #     return f"[{target_date}] {stock} {label}: {int(result):,}{unit}"

    ###-----------------------테스트 후 위 코드 주석 풀든 지우면 됨-------------------------------------
    field = field_kor_to_eng.get(field, field)
    ticker = name_to_ticker(stock, target_date)
    code = ticker.split('.')[0]

    tgt_date = datetime.strptime(target_date, "%Y-%m-%d")
    start_dt = tgt_date - timedelta(days=7) if field == 'change_rate' else tgt_date
    end_dt = tgt_date + timedelta(days=1)
    
    # data = get_stock_data(ticker, start_dt, end_dt, interval="1d")
    data = get_single_day_data(stock, code, market, target_date)
    data.index = data.index.strftime("%Y-%m-%d")  
    target_date = pd.to_datetime(target_date).strftime("%Y-%m-%d")
    if target_date not in data.index:
        return f"{target_date} : {kr_holidays.get(target_date)}임으로 해당 날짜의 데이터가 존재하지 않습니다."
    
    if field == 'change_rate':
        idx_list = list(data.index)
        tgt_idx = idx_list.index(target_date)
        prev_date = idx_list[tgt_idx - 1]
        
        now_close = data.loc[target_date, 'Close']
        prev_close = data.loc[prev_date, 'Close']
        
        change_rate = ((now_close - prev_close) / prev_close) * 100
        return f"[{target_date}] 등락률: {round(change_rate, 2)}%"
    
    field_map = {
        "Close": "종가",
        "Open": "시가",
        "High": "고가",
        "Low": "저가",
        "Volume": "거래량"
    }
    label = field_map.get(field, field)
    result = data.loc[target_date, field]
    return f"[{target_date}] {label}: {int(result):,}원"
    #######------------------------------------------------
    
@tool("answer_market_index", description="특정 날짜의 KOSPI 또는 KOSDAQ 지수(종가) 조회")
def answer_market_index(target_date:str, market:str):
    """
    특정 날짜(target_date)의 KOSPI 또는 KOSDAQ 지수(종가)를 반환합니다.

    Args:
        market (str): 시장 이름. 'KOSPI' 또는 'KOSDAQ'만 입력 가능합니다.
        target_date (str): 날짜, 예시 '2025-03-12' (YYYY-MM-DD 형식)

    Returns:
        str: 해당 날짜와 시장의 지수 종가. 예를 들어,
            - "[2025-03-12] KOSPI 지수: 3,025.45"
            - "[2025-03-12] KOSDAQ 지수: 1,012.18"
        데이터가 없으면 오류 메시지를 반환합니다.

    예시 질문:
    - "2025-06-26 KOSPI 지수는?"
    - "2025-06-11 KOSDAQ 지수는?"
    """
    # 지수 데이터는 Redis에 없으므로 항상 yfinance를 사용합니다.
    # ticker = "^KS11" if market.upper() == 'KOSPI' else "^KQ11"
    # data = fetch_from_yfinance([ticker], target_date, (datetime.strptime(target_date, "%Y-%m-%d") + timedelta(days=1)).strftime('%Y-%m-%d'))
    
    # if data.empty or target_date not in data.index.strftime('%Y-%m-%d'):
    #     return f"[{target_date}] {kr_holidays.get(target_date)}임으로 해당 날짜의 {market} 지수 데이터가 없습니다."
    
    # close = float(data.loc[data.index.strftime('%Y-%m-%d') == target_date, 'Close'].iloc[0])
    # return f"[{target_date}] {market} 지수: {close:.2f}"

    #######------------------------------------------------
    tgt_date = datetime.strptime(target_date, "%Y-%m-%d")
    end_dt = tgt_date + timedelta(days=1)

    ticker = "^KS11" if market == 'KOSPI' else "^KQ11"
    # data = get_stock_data(ticker, tgt_date, end_dt, interval="1d")
    data = fetch_from_yfinance([ticker], target_date, (datetime.strptime(target_date, "%Y-%m-%d") + timedelta(days=1)).strftime('%Y-%m-%d'))
    
    data.index = data.index.strftime("%Y-%m-%d")
    target_date = pd.to_datetime(target_date).strftime("%Y-%m-%d")
    if target_date not in data.index or data.empty:
        return f"[{target_date}] {kr_holidays.get(target_date)}임으로 해당 날짜의 {market} 지수 데이터가 없습니다."
    
    close = float(data.loc[target_date, 'Close'])
    return f"[{target_date}] {market} 지수: {close:.2f}"
    #######------------------------------------------------

@tool("answer_market_ranking", description="특정 날짜의 시장 내 종가/거래량/등락률 상위 또는 하위 종목 순위 조회")
def answer_market_ranking(market:str, target_date:str, field:str, top_n:int, reasoning:str, operator:str):
    """
    특정 날짜의 KOSPI/KOSDAQ 내에서 종가, 거래량, 등락률 등 기준으로 상위/하위 N개 종목을 순위별로 반환합니다.

    Args:
        market (str): 시장, 예시 'KOSPI', 'KOSDA'
        target_date (str): 날짜, 예시 '2025-03-12'
        field (str): 순위 기준 필드. 아래 값 중 하나여야 합니다.
            - "Open"  : 시가
            - "High"  : 고가
            - "Low"   : 저가
            - "Close" : 종가
            - "change_rate" : 등락률(전일 종가 대비 등락률, %)
            - "Volumne" : 거래량
        top_n (int): 상위/하위 종목 개수 (예: 3)
        reasoning (str, optional): 오름차순/내림차순 여부 추론용 질의 설명(예: "하략률 높은", "가장 비싼","많은" 등)
        operator (str, optional): 정렬방향, '>', '>=', '<', '<=', 'rank', 'max', 'min', 'compare', 'percent', null 등

    Returns:
        list: [순위별 종목명(티커): 값+단위] 형태의 문자열 리스트  
        예: ["삼성전자 (005930.KS): 71,800원", "카카오 (035720.KQ): 38,500원", ...]
        데이터 없거나 비거래일 등 예외는 오류 메시지(str)로 반환

    예시 질문:
    - "KOSPI/KOSDAQ에서 가장 비싼(종가) 종목 3개?"
    - "KOSPI/KOSDAQ에서 거래량이 가장 많은 종목 3개?"
    - "KOSPI/KOSDAQ에서 하락률(종가)이 가장 높은 종목 3개?"
    """
    field_eng = field_kor_to_eng.get(field, field)
    tickers = get_tickers(market, target_date)
    
    start_dt = (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
    data = get_historical_data(tickers, start_dt, target_date)
    
    if data.empty:
        return f"[{target_date}] {market} 시장 데이터를 조회할 수 없습니다."

    # MultiIndex에서 필요한 데이터 필드만 추출
    need_col = 'Volume' if field_eng == 'Volume' else 'Close'
    if isinstance(data.columns, pd.MultiIndex):
        data_need_col = data.xs(need_col, level=1, axis=1)
    else:
        data_need_col = data[[need_col]]
    
    data_need_col.index = data_need_col.index.strftime("%Y-%m-%d")

    if field_eng == 'change_rate':
        if len(data_need_col) < 2:
            return f"[{target_date}] 등락률을 계산할 전일 데이터가 없습니다."
        now_prices = data_need_col.loc[target_date]
        prev_prices = data_need_col.iloc[-2]
        series = ((now_prices - prev_prices) / prev_prices * 100).dropna()
    else:
        if target_date not in data_need_col.index:
            return f"[{target_date}] {kr_holidays.get(target_date)}임으로 해당 날짜의 데이터 없음"
        series = data_need_col.loc[target_date].dropna()

    ascending = '하락' in reasoning or '하위' in reasoning or '낮은' in reasoning
    ranked = series.sort_values(ascending=ascending)
    res = ranked.head(top_n)

    result_list = []
    for t, v in res.items():
        # target_date를 사용하여 종목명을 가져옵니다.
        stock_name = ticker_to_name(t, target_date)
        unit = "%" if field_eng == 'change_rate' else "주" if field_eng == "Volume" else "원"
        result_list.append(f"{stock_name} ({t}): {round(v, 2):,}{unit}")
        
    return result_list if result_list else "조건에 맞는 종목이 없습니다."

    
@tool("answer_stock_compare", description="특정 날짜에 두 종목의 종가, 거래량, 시가총액, 등락률을 비교해 더 큰 종목을 반환")
def answer_stock_compare(stock_name1:str, stock_name2:str, target_date:str, field:str):
    """
    특정 날짜(target_date)에 두 종목(stock_name1, stock_name2)의 종가/거래량/시가총액/등락률을 비교하여 더 큰 값을 가진 종목을 반환합니다.

    Args:
        stock_name1 (str): 첫 번째 종목명 (예: '현대차')
        stock_name2 (str): 두 번째 종목명 (예: 'NAVER')
        target_date (str): 날짜, 예시 '2024-11-06' (YYYY-MM-DD 형식)
        field (str): 비교 항목. 아래 값 중 하나여야 합니다.
            - "Open"  : 시가
            - "High"  : 고가
            - "Low"   : 저가
            - "Close" : 종가
            - "market_cap" : 시가총액
            - "change_rate" : 등락률(전일 종가 대비 등락률, %)
            - "Volumne" : 거래량

    Returns:
        str: "[날짜]에 [더 큰 종목명](값) > [작은 종목명](값)" 형식의 비교 결과 문자열  
        예: "2024-11-06에 현대차(199,000원) > NAVER(179,500원)"
        - 데이터가 없으면 "데이터 없음" 메시지 반환

    예시 질문:
    - "2025-04-07에 카카오과 현대차 중 종가이 더 높은 종목은?"
    - "2025-02-28에 현대차과 삼성SDI 중 등락률이 더 높은 종목은?"
    - "2024-11-06에 현대차과 NAVER 중 시가총액이 더 큰 종목은?"
    """
    field_eng = field_kor_to_eng.get(field, field)
    ticker1 = name_to_ticker(stock_name1, target_date)
    ticker2 = name_to_ticker(stock_name2, target_date)
    
    start_dt = (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
    data = get_historical_data([ticker1, ticker2], start_dt, target_date)

    if data.empty or target_date not in data.index.strftime('%Y-%m-%d'):
        return f"{kr_holidays.get(target_date)}임으로 해당 날짜의 데이터가 없습니다."
    
    results = {}
    for name, ticker in zip([stock_name1, stock_name2], [ticker1, ticker2]):
        stock_data = data.xs(ticker, level=0, axis=1)
        stock_data.index = stock_data.index.strftime("%Y-%m-%d")
        
        val, unit = None, ""
        if field_eng == "change_rate":
            if len(stock_data) >= 2:
                now = stock_data.loc[target_date, 'Close']
                prev = stock_data.iloc[-2]['Close']
                if pd.notna(now) and pd.notna(prev) and prev != 0:
                    val = ((now - prev) / prev) * 100
            unit = "%"
        else: # Close, Open, High, Low, Volume
            if target_date in stock_data.index:
                val = stock_data.loc[target_date, field_eng]
            unit = "주" if field_eng == "Volume" else "원"
        results[name] = (val, unit)

    filtered = {k: v for k, v in results.items() if v[0] is not None}
    if len(filtered) < 2: return f"[{target_date}] 두 종목의 데이터를 모두 조회할 수 없어 비교가 불가능합니다."

    max_name = max(filtered, key=lambda k: filtered[k][0])
    min_name = min(filtered, key=lambda k: filtered[k][0])
    
    max_val, unit = filtered[max_name]
    min_val, _ = filtered[min_name]

    return f"{target_date}에 {max_name}({max_val:,.2f}{unit}) > {min_name}({min_val:,.2f}{unit})"


@tool("answer_stock_ranking", description="특정 날짜에 특정 종목의 거래량(또는 종가 등) 시장 내 순위를 반환")
def answer_stock_ranking(stock_name:str, target_date:str, field:str):
    """
    특정 날짜(target_date)에 특정 종목(stock_name)의 거래량, 종가 등 기준으로 코스피/코스닥 전체 시장 내 순위를 반환합니다.

    Args:
        stock_name (str): 종목명, (예: '현대차')
        target_date (str): 날짜, 예시 '2024-11-06' (YYYY-MM-DD 형식)
        field (str): 순위 기준. 아래 값 중 하나여야 합니다.
            - "Open"  : 시가
            - "High"  : 고가
            - "Low"   : 저가
            - "Close" : 종가
            - "market_cap" : 시가총액
            - "change_rate" : 등락률(전일 종가 대비 등락률, %)
            - "Volumne" : 거래량
    Returns:
        str: "[날짜] [종목명](티커)의 [field] 순위: N위 / 전체 (값)" 형식의 문자열
        예: "2024-12-19 셀트리온(068270.KS)의 거래량 순위: 15위 / 1,850종목 (거래량 105,000주)"
        데이터 없으면 오류 메시지(str)로 반환
    
    예시 질문:
    - "2024-07-04에 카카오의 거래량 순위는?"
    """
    field_eng = field_kor_to_eng.get(field, field)
    target_ticker = name_to_ticker(stock_name, target_date)
    
    # 전체 시장의 티커를 가져옵니다.
    all_tickers = get_tickers("ALL", target_date)

    start_dt = (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
    data = get_historical_data(all_tickers, start_dt, target_date)

    if data.empty: return f"[{target_date}] 시장 데이터를 조회할 수 없습니다."

    need_col = 'Volume' if field_eng == 'Volume' else 'Close'
    series = data.xs(need_col, level=1, axis=1).loc[target_date].dropna()
    
    sorted_series = series.sort_values(ascending=False)
    
    try:
        rank = sorted_series.index.get_loc(target_ticker) + 1
        val = sorted_series.loc[target_ticker]
        total = len(sorted_series)
        unit = "주" if need_col == "Volume" else "원"
        return f"{target_date} {stock_name}({target_ticker})의 {field} 순위: {rank}위 / {total}종목 ({val:,.0f}{unit})"
    except KeyError:
        return f"[{target_date}] {stock_name}의 순위를 계산할 수 없습니다."


@tool("answer_market_stock_compare", description="특정 날짜에 특정 종목의 등락률이 시장(코스피/코스닥) 평균 등락률보다 높은지 비교")
def answer_market_stock_compare(stock_name:str, target_date:str):
    """
    특정 날짜(target_date)에 특정 종목(stock_name)의 등락률이 해당 종목이 속한 시장(KOSPI/KOSDAQ) 평균 등락률보다 높은지 여부를 판정하여 반환합니다.

    Args:
        stock_name (str): 종목명 (예: '삼성바이오로직스')
        target_date (str): 날짜 (예: '2024-09-08', YYYY-MM-DD 형식)

    Returns:
        str: "예 (+등락률% > 시장평균 +등락률%)" 또는  
             "아니오 (+등락률% < 시장평균 +등락률%)"  
             (소수점 두 자리, 부호 표기, 값 포함)
        - 데이터가 없으면 오류 메시지 반환  
          (예: "월요일 (삼성바이오로직스 등락률 비교 데이터 없음(공휴일/비거래일 등))")

    예시 질문:
    - "2024-09-08에 삼성바이오로직스의 등락률이 시장 평균보다 높은가?"
    """
    ticker = name_to_ticker(stock_name, target_date)
    market = name_to_market(stock_name, target_date)
    
    market_tickers = get_tickers(market, target_date)
    start_dt = (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
    data = get_historical_data(market_tickers, start_dt, target_date)

    if data.empty or len(data) < 2: 
        return f"{kr_holidays.get(target_date)}임으로 해당 날짜의 데이터가 없습니다."
    
    price_df = data.xs('Close', level=1, axis=1)
    price_df.index = price_df.index.strftime("%Y-%m-%d")
    
    now_prices = price_df.loc[target_date]
    prev_prices = price_df.iloc[-2]
    
    all_rates = ((now_prices - prev_prices) / prev_prices * 100).dropna()
    market_avg = all_rates.mean()
    stock_chgrate = all_rates.get(ticker)

    if stock_chgrate is None: 
        return f"[{target_date}] {stock_name}의 등락률을 계산할 수 없습니다."

    s_val = f"{stock_chgrate:+.2f}%"
    m_val = f"{market_avg:+.2f}%"
    
    return f"예 ({s_val} > 시장평균 {m_val})" if stock_chgrate > market_avg else f"아니오 ({s_val} <= 시장평균 {m_val})"


@tool("answer_market_ratio", description="특정 종목의 거래량이 전체 시장 거래량에서 차지하는 비중(%) 계산")
def answer_market_ratio(stock_name:str, target_date:str):
    """
    특정 날짜(target_date)에 특정 종목(stock_name)의 거래량이 전체 시장(코스피+코스닥) 거래량에서 몇 %인지 반환합니다.

    Args:
        stock_name (str): 종목명 (예: '셀트리온')
        target_date (str): 날짜 (예: '2024-09-08', YYYY-MM-DD 형식)

    Returns:
        str: "[날짜] [종목명] 거래량 비중: X.XX% (개별: N / 전체: M)" 형식의 문자열  
        예: "2025-05-23 셀트리온 거래량 비중: 2.14% (개별: 120,000 / 전체: 5,600,000)"
        - 데이터가 없거나 휴일 등 예외는 오류 메시지 반환
    
    예시 질문:
    - "2025-05-23에 셀트리온의 거래량이 전체 시장 거래량의 몇 %인가?"
    """
    ticker = name_to_ticker(stock_name, target_date)
    all_tickers = get_tickers("ALL", target_date)
    
    data = get_historical_data(all_tickers, target_date, target_date)
    if data.empty: return f"[{target_date}] 시장 데이터를 조회할 수 없습니다."

    volume_df = data.xs('Volume', level=1, axis=1)
    if target_date not in volume_df.index.strftime('%Y-%m-%d'): 
        return f"[{target_date}] {kr_holidays.get(target_date)}임으로 해당 날짜의 거래량 데이터가 없습니다."
    
    vols = volume_df.loc[target_date]
    stock_vol = vols.get(ticker)
    total_vol = vols.sum()

    if pd.isna(stock_vol) or total_vol == 0:
        return f"[{target_date}] {stock_name}의 거래량 비중을 계산할 수 없습니다."

    percent = (stock_vol / total_vol) * 100
    return f"{target_date} {stock_name} 거래량 비중: {percent:.2f}% (개별: {int(stock_vol):,} / 전체: {int(total_vol):,})"

    
@tool("answer_market_compare", description="특정 날짜에 KOSPI와 KOSDAQ 지수(또는 상승률)를 비교해 더 높은 시장을 반환")
def answer_market_compare(target_date:str,field:str):
    """
    특정 날짜(target_date)에 KOSPI와 KOSDAQ의 지수(종가) 또는 상승률(change_rate)을 비교해 더 높은 시장명을 반환합니다.

    Args:
        target_date (str): 날짜 (예: '2025-06-19', 'YYYY-MM-DD' 형식)
        field (str): 비교 항목. 아래 값 중 하나여야 합니다.
            - "Close": 종가(지수)
            - "change_rate" : 등락률(전일 종가 대비 등락률, %)

    Returns:
        str: "[시장명] ([값])" 형식의 비교 결과
            - field='Close' 예시: "KOSPI (2,860.31)"
            - field='change_rate' 예시: "KOSDAQ (+1.23%)"
        데이터 없으면 오류 메시지 반환

    예시 질문:
    - "2025-06-19에 KOSPI와 KOSDAQ 중 더 높은 지수는?"
    - "2025-05-06에 KOSPI와 KOSDAQ 중 전일 대비 상승률이 더 높은 지수는?"
    """
    field_eng = field_kor_to_eng.get(field, field)
    start_dt = (datetime.strptime(target_date, "%Y-%m-%d") - timedelta(days=7)).strftime("%Y-%m-%d")
    end_dt = (datetime.strptime(target_date, "%Y-%m-%d") + timedelta(days=1)).strftime('%Y-%m-%d')

    results = {}
    for market, ticker in [("KOSPI", "^KS11"), ("KOSDAQ", "^KQ11")]:
        data = fetch_from_yfinance([ticker], start_dt, end_dt)
        if data.empty or target_date not in data.index.strftime('%Y-%m-%d'): 
            return f"{kr_holidays.get(target_date)}임으로 해당 날짜의 데이터가 없습니다."

        if field_eng == "change_rate":
            if len(data) < 2: continue
            rate = data['Close'].pct_change().iloc[-1] * 100
            results[market] = rate
        else: 
            val = float(data.loc[data.index.strftime('%Y-%m-%d') == target_date, 'Close'].iloc[0])
            results[market] = val

    if not results: return f"[{target_date}] 지수 데이터를 조회할 수 없습니다."
    
    max_market = max(results, key=results.get)
    max_val = results[max_market]
    
    return f"{max_market} ({max_val:+.2f}%)" if field_eng == "change_rate" else f"{max_market} ({max_val:,.2f})"

    
task1_tools = [answer_stock_query,
               answer_market_index,
               answer_market_ranking,
               answer_stock_compare,
               answer_stock_ranking,
               answer_market_stock_compare,
               answer_market_ratio,
               answer_market_compare]
