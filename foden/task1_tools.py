import yfinance as yf, pandas as pd
from datetime import datetime, timedelta
import calendar
from langchain.tools import tool

from utils import *
from data_fetcher import *
    
def answer_stock_query(ticker, target_date, field):
    """
    특정 날짜/종목의
    종가,시가,고가,등락률 계산
    """
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

def answer_market_index(market, target_date):
    """
    코스피/코스닥 지수 계산
    """
    tgt_date = datetime.strptime(target_date, "%Y-%m-%d")
    end_dt = tgt_date + timedelta(days=1)

    ticker = "^KS11" if market == 'KOSPI' else "^KQ11"
    data = get_stock_data(ticker, tgt_date, end_dt, interval="1d")
    print(data)
    
    data.index = data.index.strftime("%Y-%m-%d")
    
    if target_date not in data.index or data.empty:
        return f"[{target_date}] {market} 지수 데이터가 없습니다."
    
    close = float(data.loc[target_date, 'Close'])
    return f"[{target_date}] {market} 지수: {close:.2f}"

def answer_market_ranking(tickers, target_date, field, top_n, reasoning, operator):
    """
    코스피/코스닥에서 가장 비싼(종가) 종목 3개?
    코스피/코스닥에서 거래량이 가장 많은 종목 3개?
    코스피/코스닥에서 하락률(종가)이 가장 높은 종목 3개?
    """
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
    
def answer_stock_compare(stock_name1, stock_name2, target_date, field):
    """
    2024-11-06에 현대차과 NAVER 중 시가총액/종가/거래량/등락률이 더 큰 종목은?
    """
    ticker1 = name_to_ticker[stock_name1]
    ticker2 = name_to_ticker[stock_name2]
    
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

def answer_stock_ranking(stock_name, target_date, field):
    """
    2024-12-19에 셀트리온의 거래량 순위는?
    """
    tgt_date = datetime.strptime(target_date, "%Y-%m-%d")
    end_dt = tgt_date + timedelta(days=1)
    
    target_ticker = name_to_ticker[stock_name]

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

def answer_market_stock_compare(stock_name, target_date):
    """
    2024-09-08에 삼성바이오로직스의 등락률이 시장 평균보다 높은가?
    """
    ticker = name_to_ticker[stock_name]
    market = name_to_market[stock_name]
    tgt_date = datetime.strptime(target_date, "%Y-%m-%d")
    start_dt = tgt_date - timedelta(days=7)
    end_dt = tgt_date + timedelta(days=1)

    # 1. 시장 전체 티커 추출
    market_df = market_list[market_list['market'] == market]
    if market == "KOSPI":
        tickers = [f"{str(row['code']).zfill(6)}.KS" for _, row in market_df.iterrows()]
    elif market == "KOSDAQ":
        tickers = [f"{str(row['code']).zfill(6)}.KQ" for _, row in market_df.iterrows()]
    else:
        return "지원하지 않는 시장입니다."

    # 2. 데이터 다운로드
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

        # 시장 전체 평균 등락률
        all_now = price_df.loc[target_date]
        all_prev = price_df.loc[prev_date]
        all_rate = ((all_now - all_prev) / all_prev * 100).dropna()
        market_avg = all_rate.mean()

        # 소수점 두 자리 반올림 및 부호 표기
        def fmt(num): return f"{num:+.2f}%"
        s_val = fmt(stock_chgrate)
        m_val = fmt(market_avg)

        # 예/아니오 판정
        if stock_chgrate > market_avg:
            return f"예 ({s_val} > 시장평균 {m_val})"
        else:
            return f"아니오 ({s_val} < 시장평균 {m_val})"
    except Exception as e:
        return f"에러: {e}"
    
def answer_market_ratio(stock_name, target_date):
    """
    ex) 2025-05-23에 셀트리온의 거래량이 전체 시장 거래량의 몇 %인가?
    """
    ticker = name_to_ticker[stock_name]
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
    
def answer_market_compare(target_date,field):
    """
    2025-06-19에 KOSPI와 KOSDAQ 중 더 높은 지수는?
    2025-05-06에 KOSPI와 KOSDAQ 중 전일 대비 상승률이 더 높은 지수는?
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
    
FIELD_FUNC = {
    "종목조회": answer_stock_query,
    "시장지수": answer_market_index,
    "시장랭킹": answer_market_ranking,
    "종목비교": answer_stock_compare,
    "종목랭킹": answer_stock_ranking,
    "시장비교": answer_market_stock_compare,
    "시장비중": answer_market_ratio,
}

def asnwer_task1(q:dict):
    """
    q : LLM JSON 파싱 결과
    반환 : task1 질문에 대한 답
    """
    
    tickers  = get_tickers(q) 
    
    ques_type = q['type']

    stock = q['stock_name1']

    target_date = q['target_date']

    func = FIELD_FUNC[ques_type]

    field = q['field']

    if ques_type == "종목조회":
        ticker = name_to_ticker[stock]
        result = func(ticker, target_date, field)
        return result
    
    if ques_type == "시장지수":
        market = q['market']
        result = func(market,target_date)
        return result

    if ques_type == '시장랭킹':
        result = func(tickers, target_date, field, q['top_n'], q['reasoning'], q['operator'])
        return result
    
    if ques_type == '종목비교':
        result = func(stock, q['stock_name2'], target_date, field)
        return result
    
    if ques_type == '종목랭킹':
        result = func(stock, target_date, field)
        return result
    
    if ques_type == '시장비교':
        if q['stock_name1'] == None and q['stock_name2'] == None:
            result = answer_market_compare(target_date,field)
        else:
            result = func(stock,target_date)
        return result
    
    if ques_type == '시장비중':
        result = func(stock, target_date)
        return result