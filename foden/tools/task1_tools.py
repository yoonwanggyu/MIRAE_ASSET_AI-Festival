import yfinance as yf, pandas as pd
from datetime import datetime, timedelta
import calendar
from langchain.tools import tool

from utils import *
from data_fetcher import *
    
field_kor_to_eng = {
    "시가": "Open",
    "고가": "High",
    "저가": "Low",
    "종가": "Close",
    "등락률": "change_rate",
    "거래량": "Volume"
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
            - "Volumne" : 거래량

    Returns:
        str: 해당 날짜와 필드에 대한 값. 예를 들어,
            - "[2025-03-12] 종가: 13,800원"
            - "[2025-03-12] 시가: 14,000원"
            - "[2025-03-12] 등락률: -1.65%"

    예시 질문:
    - "KOSPI에서 롯데지주의 2024-07-05 종가는?"
    - "삼영엠텍의 2025-05-15 등락률은?"
    - "한네트의 2024-11-20 시가는?"
    - "도화엔지니어링의 2025-06-25 고가는?"
    """

    field = field_kor_to_eng.get(field, field)
    ticker = name_to_ticker(stock)

    tgt_date = datetime.strptime(target_date, "%Y-%m-%d")
    start_dt = tgt_date - timedelta(days=7) if field == 'change_rate' else tgt_date
    end_dt = tgt_date + timedelta(days=1)
    
    data = get_stock_data(ticker, start_dt, end_dt, interval="1d")
    data.index = data.index.strftime("%Y-%m-%d")  
    
    if target_date not in data.index:
        return f"{target_date} : 해당 날짜의 데이터가 존재하지 않습니다."
    
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
    tgt_date = datetime.strptime(target_date, "%Y-%m-%d")
    end_dt = tgt_date + timedelta(days=1)

    ticker = "^KS11" if market == 'KOSPI' else "^KQ11"
    data = get_stock_data(ticker, tgt_date, end_dt, interval="1d")
    
    data.index = data.index.strftime("%Y-%m-%d")
    
    if target_date not in data.index or data.empty:
        return f"[{target_date}] {market} 지수 데이터가 없습니다."
    
    close = float(data.loc[target_date, 'Close'])
    return f"[{target_date}] {market} 지수: {close:.2f}"

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
    field = field_kor_to_eng.get(field, field)
    tickers = get_tickers(market)
    tgt_date = datetime.strptime(target_date, "%Y-%m-%d")
    start_dt = tgt_date - timedelta(days=7) if field == 'change_rate' else tgt_date
    end_dt = tgt_date + timedelta(days=1)

    need_col = 'Volume' if field == 'Volume' else 'Close'
    data = download_in_batches(tickers, start_dt, end_dt, batch_size=200)

    if isinstance(data.columns, pd.MultiIndex):
        try:
            data_need_col = data.xs(need_col, level="Price", axis=1)
        except KeyError:
            return f"[{target_date}] {need_col} 데이터 없음 (공휴일/비거래일 등)"
    else:
        if need_col not in data.columns:
            return f"[{target_date}] {need_col} 데이터 없음 (공휴일/비거래일 등)"
        data_need_col = data[need_col]
    data_need_col.index = data_need_col.index.strftime("%Y-%m-%d")  

    if field == 'change_rate':
        change_rates = {}
        for ticker in data_need_col.columns:
            if target_date not in data_need_col.index:
                continue
            idx_list = list(data_need_col.index)
            tgt_idx = idx_list.index(target_date)
            if tgt_idx == 0:
                continue
            prev_date = idx_list[tgt_idx - 1]
            now = data_need_col.loc[target_date, ticker]
            prev = data_need_col.loc[prev_date, ticker]
            if pd.notnull(now) and pd.notnull(prev) and prev != 0:
                rate = ((now - prev) / prev) * 100
                change_rates[ticker] = rate
        series = pd.Series(change_rates)
    else:
        if target_date not in data_need_col.index:
            return f"{target_date} 데이터 없음"
        series = data_need_col.loc[target_date]

    if operator in ("<", "asc", "min"):
        ascending = True
    elif operator in (">", "desc", "max"):
        ascending = False
    else:
        if reasoning and any(x in reasoning for x in ['하락', '하락률' '하위', '싼', '낮은']):
            ascending = True
        else:
            ascending = False

    ranked = series.sort_values(ascending=ascending).dropna()
    res = ranked.iloc[:top_n]
    result_list = []
    for t, v in res.items():
        key = t.split('.')[0] 
        stock_name = ticker_to_name.get(key, t)
        if field == 'change_rate':
            unit = "%"
        elif field == "Volume":
            unit = "주"
        else:
            unit = "원"
        result_list.append(f"{stock_name} ({t}): {round(v,2):,}{unit}")
    return result_list
    
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
    field = field_kor_to_eng.get(field, field)
    ticker1 = name_to_ticker(stock_name1)
    ticker2 = name_to_ticker(stock_name2)
    
    tgt_date = datetime.strptime(target_date, "%Y-%m-%d")
    start_dt = tgt_date - timedelta(days=7) if field == 'change_rate' else tgt_date
    end_dt = tgt_date + timedelta(days=1)

    data = get_stock_data([ticker1, ticker2], start_dt, end_dt,interval="1d")
    data.index = data.index.strftime("%Y-%m-%d")
    
    results = {}
    for name, ticker in zip([stock_name1, stock_name2], [ticker1, ticker2]):
        try:
            if field == "Close":
                if target_date in data.index:
                    val = data[("Close", ticker)].loc[target_date]
                    results[name] = (val, "원")
                else:
                    results[name] = (None, "원")
            elif field == "Volume":
                if target_date in data.index:
                    val = data[("Volume", ticker)].loc[target_date]
                    results[name] = (val, "주")
                else:
                    results[name] = (None, "주")
            elif field == "market_cap":
                if target_date in data.index:
                    mc = yf.Ticker(ticker).info.get("marketCap")
                    results[name] = (mc, "원") if mc is not None else (None, "원")
                else:
                    results[name] = (None, "원")
            elif field == "change_rate":
                idx_list = list(data.index)
                if target_date not in idx_list or idx_list.index(target_date) == 0:
                    results[name] = (None, "%")
                    continue
                tgt_idx = idx_list.index(target_date)
                prev_date = idx_list[tgt_idx - 1]
                now = data[("Close", ticker)].loc[target_date]
                prev = data[("Close", ticker)].loc[prev_date]
                if pd.notnull(now) and pd.notnull(prev) and prev != 0:
                    rate = ((now - prev) / prev) * 100
                    results[name] = (rate, "%")
                else:
                    results[name] = (None, "%")
            else:
                results[name] = (None, "")
        except Exception as e:
            results[name] = (None, "")
    
    # 결과 비교
    filtered = {k: v for k, v in results.items() if v[0] is not None}
    if not filtered:
        return f"{target_date} 데이터 없음"
    max_name = max(filtered, key=lambda k: filtered[k][0])
    val, unit = filtered[max_name]
    other_name = [k for k in filtered if k != max_name][0]
    other_val = filtered[other_name][0]
    
    return f"{target_date}에 {max_name}({val:,.2f}{unit}) > {other_name}({other_val:,.2f}{unit})"

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
    field = field_kor_to_eng.get(field, field)
    tgt_date = datetime.strptime(target_date, "%Y-%m-%d")
    end_dt = tgt_date + timedelta(days=1)
    
    target_ticker = name_to_ticker(stock_name)

    # 코스피와 코스닥 전체 종목 가져오기
    kospi_df = market_list[market_list['market'] == 'KOSPI']
    kosdaq_df = market_list[market_list['market'] == 'KOSDAQ']
    
    # 모든 티커 생성
    kospi_tickers = [f"{str(row['code']).zfill(6)}.KS" for _, row in kospi_df.iterrows()]
    kosdaq_tickers = [f"{str(row['code']).zfill(6)}.KQ" for _, row in kosdaq_df.iterrows()]
    
    # 전체 티커 합치기
    all_tickers = kospi_tickers + kosdaq_tickers

    data = download_in_batches(all_tickers, tgt_date, end_dt, batch_size=200)
    
    if isinstance(data.columns, pd.MultiIndex):
        volume_df = data.xs(field, level="Price", axis=1)
    else:
        volume_df = data[[field]]
    volume_df.index = volume_df.index.strftime("%Y-%m-%d")

    if target_date not in volume_df.index:
        return f"{target_date} 데이터가 없습니다."

    vols = volume_df.loc[target_date]
    # 거래량 내림차순 정렬
    sorted_vols = vols.sort_values(ascending=False)
    if target_ticker is None:
        return f"{stock_name}의 티커를 찾을 수 없습니다."
    try:
        rank = sorted_vols.index.get_loc(target_ticker) + 1
        val = sorted_vols.loc[target_ticker]
        total = len(sorted_vols)
        return f"{target_date} {stock_name}({target_ticker})의 거래량 순위: {rank}위 / {total}종목 (거래량 {val:,}주)"
    except KeyError:
        return f"{target_date} {stock_name}의 거래량 데이터가 없습니다."

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
    field = field_kor_to_eng.get(field, field)
    ticker = name_to_ticker(stock_name)
    market = name_to_market(stock_name)
    tgt_date = datetime.strptime(target_date, "%Y-%m-%d")
    start_dt = tgt_date - timedelta(days=7)
    end_dt = tgt_date + timedelta(days=1)

    market_df = market_list[market_list['market'] == market]
    if market == "KOSPI":
        tickers = [f"{str(row['code']).zfill(6)}.KS" for _, row in market_df.iterrows()]
    elif market == "KOSDAQ":
        tickers = [f"{str(row['code']).zfill(6)}.KQ" for _, row in market_df.iterrows()]
    else:
        return "지원하지 않는 시장입니다."

    try:
        data = download_in_batches(tickers, start_dt, end_dt, batch_size=200)
        price_df = data.xs('Close', level='Price', axis=1)
        price_df.index = price_df.index.strftime("%Y-%m-%d")
        idx_list = list(price_df.index)
        if target_date not in idx_list:
            day_name = calendar.day_name[tgt_date.weekday()]
            return f"{day_name} ({stock_name} 등락률 비교 데이터 없음(공휴일/비거래일 등))"
        tgt_idx = idx_list.index(target_date)
        if tgt_idx == 0:
            return f"{target_date} 전일 데이터 없음"
        prev_date = idx_list[tgt_idx - 1]
        now = price_df.loc[target_date, ticker]
        prev = price_df.loc[prev_date, ticker]
        if pd.isna(now) or pd.isna(prev) or prev == 0:
            return f"{target_date} {stock_name} 등락률 계산 불가"
        stock_chgrate = ((now - prev) / prev) * 100

        all_now = price_df.loc[target_date]
        all_prev = price_df.loc[prev_date]
        all_rate = ((all_now - all_prev) / all_prev * 100).dropna()
        market_avg = all_rate.mean()

        def fmt(num): return f"{num:+.2f}%"
        s_val = fmt(stock_chgrate)
        m_val = fmt(market_avg)

        if stock_chgrate > market_avg:
            return f"예 ({s_val} > 시장평균 {m_val})"
        else:
            return f"아니오 ({s_val} < 시장평균 {m_val})"
    except Exception as e:
        return f"에러: {e}"

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
    ticker = name_to_ticker(stock_name)
    tgt_date = datetime.strptime(target_date, "%Y-%m-%d")
    end_dt = tgt_date + timedelta(days=1)

    # 코스피와 코스닥 전체 종목 가져오기
    kospi_df = market_list[market_list['market'] == 'KOSPI']
    kosdaq_df = market_list[market_list['market'] == 'KOSDAQ']
    
    # 모든 티커 생성
    kospi_tickers = [f"{str(row['code']).zfill(6)}.KS" for _, row in kospi_df.iterrows()]
    kosdaq_tickers = [f"{str(row['code']).zfill(6)}.KQ" for _, row in kosdaq_df.iterrows()]
    
    # 전체 티커 합치기
    all_tickers = kospi_tickers + kosdaq_tickers

    try:
        data = download_in_batches(all_tickers, tgt_date, end_dt, batch_size=200)
        if isinstance(data.columns, pd.MultiIndex):
            volume_df = data.xs('Volume', level='Price', axis=1)
        else:
            volume_df = data[['Volume']]
        volume_df.index = volume_df.index.strftime("%Y-%m-%d")

        if target_date not in volume_df.index:
            day_name = calendar.day_name[tgt_date.weekday()]
            return f"{day_name} ({stock_name} 등락률 비교 데이터 없음(공휴일/비거래일 등))"

        vols = volume_df.loc[target_date]
        # 해당 종목 거래량
        stock_vol = vols.get(ticker)
        # 전체 합
        total_vol = vols.sum()

        if pd.isna(stock_vol) or total_vol == 0:
            return f"{target_date}에 {stock_name}의 거래량 비중 데이터가 없습니다."

        percent = stock_vol / total_vol * 100

        return f"{target_date} {stock_name} 거래량 비중: {percent:.2f}% (개별: {int(stock_vol):,} / 전체: {int(total_vol):,})"
    except Exception as e:
        return f"에러: {e}"
    
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
    tgt_date = datetime.strptime(target_date, "%Y-%m-%d")
    start_dt = tgt_date - timedelta(days=7) if field == 'change_rate' else tgt_date
    end_dt = tgt_date + timedelta(days=1)

    results = {}
    for market, ticker in [("KOSPI", "^KS11"), ("KOSDAQ", "^KQ11")]:
        data = get_stock_data(ticker, start_dt, end_dt, interval="1d")
        data.index = data.index.strftime("%Y-%m-%d")
        if target_date not in data.index:
            day_name = calendar.day_name[tgt_date.weekday()]
            return f"{day_name} : ({target_date} 날짜 데이터 없음(공휴일/비거래일 등))"

        if field == "change_rate":
            idx_list = list(data.index)
            tgt_idx = idx_list.index(target_date)
            if tgt_idx == 0:
                return f"{target_date} 전일 데이터 없음"
            
            prev_date = idx_list[tgt_idx - 1]
            now = data.loc[target_date, "Close"]
            prev = data.loc[prev_date, "Close"]
            if pd.notnull(now) and pd.notnull(prev) and prev != 0:
                rate = ((now - prev) / prev) * 100
                results[market] = rate
            else:
                results[market] = None
        else: 
            val = float(data.loc[target_date, 'Close'])
            results[market] = val

    valid = {k: v for k, v in results.items() if v is not None}
    if not valid:
        return f"{target_date} 데이터가 없습니다."

    # 둘 중 높은 값 선택 및 포맷
    max_market = max(valid, key=lambda k: valid[k])
    max_val = valid[max_market]
    if field == "change_rate":
        sign = "+" if max_val >= 0 else ""
        return f"{max_market} ({sign}{max_val:.2f}%)"
    else:
        return f"{max_market} ({max_val:,.2f})"
    
task1_tools = [answer_stock_query,
               answer_market_index,
               answer_market_ranking,
               answer_stock_compare,
               answer_market_stock_compare,
               answer_market_ratio,
               answer_market_compare]