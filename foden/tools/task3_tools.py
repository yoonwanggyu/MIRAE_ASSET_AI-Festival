import yfinance as yf
import pandas as pd
from typing import List, Dict, Literal
from datetime import datetime, timedelta
from langchain.tools import tool
import numpy as np

from utils import *
from data_fetcher import *
    
def moving_average(df: pd.DataFrame, window: int, status : str = 'mean') -> pd.DataFrame:
    """
    이동평균선 구하는 함수
    """
    if status == 'mean':
        return df.rolling(window).mean()
    else:
        return df.rolling(window).std(ddof=1) 

def calc_rsi_df(data: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    RSI Helper 함수 : 한 종목씩 RSI 구하고 합치는 함수
    """
    def rsi_one(series: pd.Series) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
        # 0으로 나누기 방지
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi
        # rs = avg_gain / avg_loss
        # rsi = 100 - (100 / (1 + rs))
        # return rsi
    return data.apply(rsi_one, axis=0)

@tool("rsi", description="특정 날짜에 여러 종목의 RSI 값을 계산해, 과매수/과매도 조건에 맞는 종목을 필터링합니다. operator는 반드시 '>='와 '<=' 중 하나만 입력하세요!")
def rsi(target_date:str, threshold:int, operator:str) -> Dict[str, float]:
    """
    [RSI 기준 종목 필터링 함수]
    여러 종목의 주가 데이터에서 특정 날짜의 RSI(상대강도지수)를 계산한 뒤, 
    threshold(임계값)과 operator 조건(>=, <= 등)에 따라 조건을 만족하는 종목만 반환합니다.
    
    Args:
        target_date (str): 
            - 조회할 날짜 (YYYY-MM-DD 형식)
        threshold (float): 
            - RSI 임계값 (예: 80, 30 등)
            - 과매수(>=80), 과매도(<=30) 탐지에 사용
        operator (str): 
            - 조건 부등호 ('>=' 또는 '<=')
            - '>='이면 threshold 이상(과매수 등), '<='이면 이하(과매도 등)
        
    Returns:
        Dict[str, float]: 
            - 조건을 만족하는 {티커: RSI값} 딕셔너리
            - 예: {'005930.KS': 83.2, '035720.KQ': 81.1}
            - 해당 날짜 index가 없으면 "날짜 없음" 문자열 반환
    
    Note:
        - RSI는 0~100 구간으로, 70 이상(과매수), 30 이하(과매도)로 주로 활용됩니다.
        - DataFrame에 해당 날짜 index가 없는 경우 안내 메시지를 반환합니다.

    예시 사용:
    - "2024-11-21에 RSI가 25 이하인 과매도 종목을 알려줘"
    >>> rsi(target_date="2024-11-21", threshold=25, operator="<=")
    - "2024-08-30에 RSI가 80 이상인 과매수 종목을 알려줘"
    >>> rsi(target_date="2024-08-30", threshold=80, operator="<=")
    """
    print(threshold)
    print(operator)
    tickers  = get_tickers("ALL")
    tgt_date  = datetime.strptime(target_date, "%Y-%m-%d")
    start_dt  = tgt_date - timedelta(days=200)
    end_dt    = tgt_date + timedelta(days=1) 

    data = download_in_batches(tickers, start_dt, end_dt, batch_size=200)
    data_need_col = data.xs("Adj Close", level="Price", axis=1)

    rsi_df = calc_rsi_df(data_need_col)
    rsi_df.index = rsi_df.index.strftime("%Y-%m-%d")  
    
    if target_date not in rsi_df.index:
        return f"{target_date} : 해당 날짜의 데이터가 존재하지 않습니다."

    rsi_on_date = rsi_df.loc[target_date]

    # NaN 값 제거
    rsi_on_date = rsi_on_date.dropna()

    if operator == "<=":
        filtered = rsi_on_date[rsi_on_date <= threshold]
        sort_asc = True
    else:
        filtered = rsi_on_date[rsi_on_date >= threshold]
        sort_asc = False
    result = filtered.to_dict()
    rsi_stock_name = {}
    for ticker,value in result.items():
        clean_ticker = ticker.replace('.KS', '').replace('.KQ', '')
        stock_name = ticker_to_name(clean_ticker)
        rsi_stock_name[stock_name] = round(value,2)

    sorted_dict = dict(sorted(rsi_stock_name.items(), key=lambda x: x[1], reverse=not sort_asc))
    return sorted_dict

@tool ("detect_cross", description="여러 종목 또는 단일 종목의 골든/데드크로스 발생 횟수 또는 종목명을 반환합니다. cross_type은 반드시 'golden','dead','all' 세 개 중 하나만 입력하세요!")
def detect_cross(stock_name:str, start_date:str, end_date:str, cross_type:str, short: int = 5, long: int = 20) -> Dict[str, float]:
    """
    [이동평균선(MA) 교차 신호(골든/데드크로스) 탐지 함수]

    여러 종목 또는 단일 종목의 지정된 기간(start_date ~ end_date) 내에 골든크로스(단기선이 장기선 위로 돌파) / 데드크로스(반대) 발생 횟수 또는 종목명을 반환합니다.

    Args:
        stock_name (str, optional): 
            - 분석할 특정 종목명(예: "삼성전자")  
            - None 
        start_date (str): 
            - 분석 시작 날짜(YYYY-MM-DD)
        end_date (str): 
            - 분석 종료 날짜(YYYY-MM-DD)
        cross_type (str): 
            - "golden": 골든크로스만
            - "dead": 데드크로스만
            - "all": 둘 다
    Returns:
        dict:  
            - stock_name이 지정된 경우: {'golden': N, 'dead': M} (N/M은 각 신호 횟수)
            - stock_name이 없으면: {티커: 신호횟수/딕셔너리, ...}
                예: {'005930.KS': {'golden': 2, 'dead': 1}, ...}
            - 신호가 없는 경우 빈 dict

    Note:
        - 골든크로스: 단기 MA가 장기 MA를 아래→위로 돌파
        - 데드크로스: 단기 MA가 장기 MA를 위→아래로 돌파
        - cross_type = "all"이면 두 신호 모두 카운트
        - stock_name이 None/""이면 전체 종목 대상으로 계산 후, 
          신호가 발생한 종목만 반환
    예시 사용:
    - "2025-02-24부터 2025-03-26까지 데드크로스가 발생한 종목을 알려줘"
    >>> detect_cross(stock_name=None,start_date="2025-02-24",end_date="2025-03-26",cross_type="dead")
    - "웨이비스는 2024-06-01부터 2025-06-30까지 데드크로스 또는 골든크로스가 몇번 발생했어?"
    >>> detect_cross(stock_name="웨이비스",start_date="2024-06-01",end_date="2025-06-30",cross_type="all")
    - "TP는 2024-06-01부터 2025-06-30까지 골든크로스가 몇번 발생했어?"
    >>> detect_cross(stock_name="TP",start_date="2024-06-01",end_date="2025-06-30",cross_type="golden")
    """
    print(stock_name)
    print(cross_type)
    tickers  = get_tickers("ALL")
    start_date  = datetime.strptime(start_date, "%Y-%m-%d")
    end_date = datetime.strptime(end_date, "%Y-%m-%d")

    start_dt = start_date - timedelta(days=40) 
    end_dt    = end_date + timedelta(days=1) 

    if stock_name:
        ticker = name_to_ticker(stock_name)
        data = get_stock_data(ticker, start_dt, end_dt)
        data_need_col = data.xs("Adj Close", level="Price", axis=1)

        sma = moving_average(data_need_col, short)   
        lma = moving_average(data_need_col, long)    

        golden_cross = (sma >= lma) & (sma.shift(1) < lma.shift(1))
        dead_cross = (sma <= lma) & (sma.shift(1) > lma.shift(1))

        if start_date and end_date:
            idx = (data.index >= pd.to_datetime(start_date)) & (data.index <= pd.to_datetime(end_date))
        else:
            idx = slice(None)

        out = {}
        golden_dates = golden_cross[ticker][idx][golden_cross[ticker][idx]].index.tolist()
        dead_dates   = dead_cross[ticker][idx][dead_cross[ticker][idx]].index.tolist()

        if cross_type == "golden":
            if len(golden_dates) > 0:
                out["golden"] = len(golden_dates)
        elif cross_type == "dead":
            if len(dead_dates) > 0:
                out["dead"] = len(dead_dates)
        else:  
            if len(golden_dates) > 0:
                out["golden"] = len(golden_dates)
            if len(dead_dates) > 0:
                out["dead"] = len(dead_dates)
        return out
    else:
        data = download_in_batches(tickers, start_dt, end_dt, batch_size=200)
        data_need_col = data.xs("Adj Close", level="Price", axis=1)

        sma = moving_average(data_need_col, short)   
        lma = moving_average(data_need_col, long)    

        golden_cross = (sma >= lma) & (sma.shift(1) < lma.shift(1))
        dead_cross = (sma <= lma) & (sma.shift(1) > lma.shift(1))

        if start_date and end_date:
            idx = (data.index >= pd.to_datetime(start_date)) & (data.index <= pd.to_datetime(end_date))
        else:
            idx = slice(None)
        out = {}
        for ticker in data_need_col.columns:
            golden_dates = golden_cross[ticker][idx][golden_cross[ticker][idx]].index
            dead_dates   = dead_cross[ticker][idx][dead_cross[ticker][idx]].index

            if cross_type == "golden":
                if len(golden_dates) > 0:
                    out[ticker] = len(golden_dates)
            elif cross_type == "dead":
                if len(dead_dates) > 0:
                    out[ticker] = len(dead_dates)
            else:  
                info = {}
                if len(golden_dates) > 0:
                    info['golden'] = len(golden_dates)
                if len(dead_dates) > 0:
                    info['dead'] = len(dead_dates)
                if info:
                    out[ticker] = info
        stock_name_dict = {}
        for ticker, value in out.items():
            clean_ticker = ticker.replace('.KS', '').replace('.KQ', '')
            stock_name = ticker_to_name(clean_ticker)
            stock_name_dict[stock_name] = value
        return stock_name_dict
        

@tool("price_vs_adj_ma",description="특정 날짜에 여러 종목의 종가가 N일 이동평균선(MA) 대비 X% 이상 돌파 또는 이하인 종목을 필터링합니다.")
def price_vs_adj_ma(target_date:str, ma_window: int, pct: float,operator: Literal[">=","<="] = ">=") -> Dict[str, float]:
    """
    [이동평균선(MA) 대비 돌파/이탈 종목 탐지 함수]

    모든 종목의 종가 데이터를 기준으로,
    지정한 날짜(target_date)에 N일 이동평균선(MA) 대비 가격 변화율이 
    X%(pct) 이상(혹은 이하)인 종목만 필터링하여 반환합니다.

    Args:
        target_date (str): 
            - 조회 날짜 (YYYY-MM-DD)
        ma_window (int): 
            - 이동평균 기간(일). (5, 20, 60)
        pct (float): 
            - 이동평균 대비 변동률 임계값(%, 예: 3.0)
        operator (str, optional): 
            - 비교 연산자(">=": 이상, "<=": 이하) (기본값: ">=")

    Returns:
        dict: 
            - {티커: 변화율(%)}, 예: {"005930.KS": "3.21%", ...}
            - 조건에 맞는 종목이 없으면 빈 dict

    Note:
        - operator가 ">="이면 MA 대비 pct% 이상 돌파, "<="이면 pct% 이하 이탈 탐지

    예시 사용:
    - "2024-10-07에 종가가 60일 이동평균보다 3% 이상 높은 종목을 알려줘"
    >>> price_vs_adj_ma(target_date="2024-10-07", ma_window=60, pct=3.0, operator=">=")
    - "2025-03-06에 종가가 20일 이동평균보다 5% 이상 높은 종목을 알려줘"
    >>> price_vs_adj_ma(target_date="2025-03-06", ma_window=20, pct=5.0, operator=">=")
    - "2024-08-05에 종가가 5일 이동평균보다 1% 이상 높은 종목을 알려줘"
    >>> price_vs_adj_ma(target_date="2024-08-05", ma_window=5, pct=1.0, operator=">=")
    """
    tickers  = get_tickers("ALL")
    tgt_date  = datetime.strptime(target_date, "%Y-%m-%d")
    if ma_window == 5:
        extra_date = 20
    elif ma_window == 20:
        extra_date = 40  
    else:  
        extra_date = 110
    start_dt  = tgt_date - timedelta(days=extra_date)
    end_dt    = tgt_date + timedelta(days=1) 

    data = download_in_batches(tickers, start_dt, end_dt, batch_size=200)
    data.index = data.index.strftime("%Y-%m-%d")  
    
    if not isinstance(data.columns, pd.MultiIndex):
        return "DataFrame columns must be MultiIndex (PriceType, Ticker)"
    if target_date not in data.index:
        return f"{target_date} is not in index!"

    results = {}
    # target_date = pd.to_datetime(target_date)

    data_close = data.xs("Close", level="Price", axis=1)
    data_adj_close = data.xs("Adj Close", level="Price", axis=1)

    adj_ma_df = moving_average(data_adj_close, ma_window)
    
    for ticker in data_adj_close.columns:
        current_price = data_close[ticker].loc[target_date]

        ma_val = adj_ma_df[ticker].loc[target_date]
        if pd.isna(ma_val) or ma_val == 0:
            continue
        
        diff_pct = ((current_price - ma_val) / ma_val) * 100

        if operator == ">=" and diff_pct >= pct:
            results[ticker] = f"{round(diff_pct, 2)}%"
        elif operator == "<=" and diff_pct <= pct:
            results[ticker] = f"{round(diff_pct, 2)}%"
        
    stock_name_dict = {}
    for ticker, percentage in results.items():
        clean_ticker = ticker.replace('.KS', '').replace('.KQ', '')
        stock_name = ticker_to_name(clean_ticker)
        stock_name_dict[stock_name] = percentage
    
    sorted_dict = dict(sorted(stock_name_dict.items(),key=lambda x: float(str(x[1]).replace('%','')),reverse=True))
    return sorted_dict

@tool("bollinger_bands",description="특정 날짜에 여러 종목의 종가가 볼린저밴드 상단(upper) 또는 하단(lower)을 돌파한 종목만 필터링합니다. bollinger_side는 반드시 'upper' 또는 'lower'만 입력하세요!")
def bollinger_bands(target_date:str, bollinger_side : str = 'upper', window: int = 20, std_dev: float = 2.0) -> Dict[str, int]:
    """
    [볼린저밴드 상/하단 돌파 종목 탐지 함수]

    여러 종목의 종가 데이터를 기준으로,
    지정한 날짜(target_date)에 볼린저밴드 상단(upper) 또는 하단(lower)을 돌파한(혹은 이탈한) 종목만 반환합니다.

    Args:
        target_date (str): 
            - 조회 날짜(YYYY-MM-DD)
        bollinger_side (str / 반드시 다음 두 가지만 입력하세요: 
            - "upper"
            - "lower"

    Returns:
        dict: 
            - {티커: 종가}, 예: {"005930.KS": 84200, ...}
            - 조건을 만족하는 종목이 없으면 빈 dict
            - DataFrame 구조 또는 날짜 미일치시 에러 메시지(str) 반환

    Note:
        - 상단 돌파: 종가가 upper band 이상, 하단 돌파: 종가가 lower band 이하
        - DataFrame 멀티인덱스 또는 날짜 누락 등 예외 상황 안내 포함

    예시 사용:
    - "2024-11-21에 볼린저밴드 상단을 돌파한 종목을 알려줘"
    >>> bollinger_bands(target_date="2024-11-21", bollinger_side="upper")
    - "2024-11-18에 볼린저 밴드 하단에 터치한 종목을 알려줘"
    >>> bollinger_bands(target_date="2024-11-18", bollinger_side="lower")
    """
    print(target_date)
    print(bollinger_side)

    # side_map = {
    #     "상단": "upper", "상": "upper", "top": "upper", "upper": "upper",
    #     "하단": "lower", "하": "lower", "bottom": "lower", "lower": "lower"
    # }
    # bollinger_side = side_map.get(bollinger_side.lower(), bollinger_side.lower())
    
    tickers  = get_tickers("ALL")
    tgt_date  = datetime.strptime(target_date, "%Y-%m-%d")
    start_dt  = tgt_date - timedelta(days=40)
    end_dt    = tgt_date + timedelta(days=1) 

    data = download_in_batches(tickers, start_dt, end_dt, batch_size=200)
    data.index = data.index.strftime("%Y-%m-%d")  
    if not isinstance(data.columns, pd.MultiIndex):
        return "DataFrame columns must be MultiIndex (PriceType, Ticker)"
    if target_date not in data.index:
        return f"{target_date} is not in index!"
    # target_date = pd.to_datetime(target_date)

    data_adj_close = data.xs("Adj Close", level="Price", axis=1)
    data_close = data.xs("Adj Close", level="Price", axis=1)

    results = {}
    for ticker in data_adj_close.columns:
        adj_close = data_adj_close[ticker]
        close = data_close[ticker]

        ma = moving_average(adj_close,window)
        std = moving_average(adj_close,window,status='std')
        upper = ma + std_dev * std
        lower = ma - std_dev * std

        close_val = close.loc[target_date]
        upper_val = upper.loc[target_date]
        lower_val = lower.loc[target_date]

        if bollinger_side == "upper" and close_val >= upper_val:
            results[ticker] = int(round(float(close_val)))
        elif bollinger_side == "lower" and close_val <= lower_val:
            results[ticker] = int(round(float(close_val)))
    
    stock_bollinger_dict = {}
    for ticker, close in results.items():
        clean_ticker = ticker.replace('.KS', '').replace('.KQ', '')
        stock_name = ticker_to_name(clean_ticker)
        stock_bollinger_dict[stock_name] = close

    sorted_dict = dict(sorted(stock_bollinger_dict.items(), key=lambda x: x[1], reverse=True))
    return sorted_dict

@tool("get_high_volume_stocks",description="특정 날짜에 여러 종목의 거래량이 N일 평균 대비 X% 이상 급증한 종목을 필터링합니다.")
def get_high_volume_stocks(target_date, ma_window, volume_ratio) -> Dict[str, int]:
    """
    [거래량 급증 종목 필터링 함수]

    여러 종목의 거래량 데이터를 기반으로,
    지정한 날짜(target_date)에 N일 이동평균(ma_window) 대비
    거래량이 volume_ratio(%) 이상 증가한 종목만 필터링하여 반환합니다.

    Args:
        target_date (str): 
            - 조회할 날짜(YYYY-MM-DD)
        ma_window (int): 
            - 이동평균 기간(일, 예: 5, 20)
        volume_ratio (float): 
            - 이동평균 대비 거래량 증가 임계값(%, 예: 100, 300)

    Returns:
        dict: 
            - {티커: 증가율(%)}, 예: {"005930.KS": 155, ...}
            - 조건을 만족하는 종목이 없으면 빈 dict 반환
            - 날짜 미포함 등 예외 상황은 str 메시지 반환

    Note:
        - DataFrame에 날짜가 없으면 에러 메시지 반환

    예시 사용:
    - "2024-11-06에 거래량이 20일 평균 대비 100% 이상 급증한 종목을 알려줘"
    >>> get_high_volume_stocks(target_date="2024-11-06", ma_window=20, volume_ratio=100)
    - "2025-02-17에 거래량이 20일 평균 대비 300% 이상 급증한 종목을 알려줘"
    >>> get_high_volume_stocks(target_date="2025-02-17", ma_window=20, volume_ratio=300)
    """
    tickers  = get_tickers("ALL")
    tgt_date  = datetime.strptime(target_date, "%Y-%m-%d")
    if ma_window == 5:
        extra_date = 20
    elif ma_window == 20:
        extra_date = 40  
    else:  
        extra_date = 110
    start_dt  = tgt_date - timedelta(days=extra_date)
    end_dt    = tgt_date + timedelta(days=1) 
    data = download_in_batches(tickers, start_dt, end_dt, batch_size=200)
    data_need_col = data.xs("Volume", level="Price", axis=1)
    data_need_col.index = data_need_col.index.strftime("%Y-%m-%d")  
    if target_date not in data_need_col.index:
        return f"{target_date} is not in index!"

    results = {}
    ma_df = moving_average(data_need_col,ma_window)

    for ticker in data_need_col.columns:
        today_vol = data_need_col.loc[target_date, ticker]
        ma_vol = ma_df.loc[target_date, ticker]

        if pd.isna(ma_vol) or ma_vol == 0:
            continue
        increase_pct = ((today_vol - ma_vol) / ma_vol) * 100

        if increase_pct >= volume_ratio:
            results[ticker] = int(round(float(increase_pct)))

    stock_volume_dict = {}
    for ticker, volume in results.items():
        clean_ticker = ticker.replace('.KS', '').replace('.KQ', '')
        stock_name = ticker_to_name(clean_ticker)
        stock_volume_dict[stock_name] = volume

    sorted_dict = dict(sorted(stock_volume_dict.items(), key=lambda x: x[1], reverse=True))
    return sorted_dict

task3_tools = [rsi, detect_cross, price_vs_adj_ma, bollinger_bands, get_high_volume_stocks]