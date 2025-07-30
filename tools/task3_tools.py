import yfinance as yf
import pandas as pd
from typing import List, Dict, Literal
from datetime import datetime, timedelta
from langchain.tools import tool

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
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    return data.apply(rsi_one, axis=0)

@tool("rsi", description="특정 날짜에 여러 종목의 RSI 값을 계산해, 과매수/과매도 조건에 맞는 종목을 필터링합니다.")
def rsi(data: pd.DataFrame, target_date, threshold, operator) -> Dict[str, float]:
    """
    [RSI 기준 종목 필터링 함수]
    여러 종목의 주가 데이터(DataFrame)에서 특정 날짜의 RSI(상대강도지수)를 계산한 뒤, 
    threshold(임계값)과 operator 조건(>=, <= 등)에 따라 조건을 만족하는 종목만 반환합니다.
    
    Args:
        data (pd.DataFrame): 
            - index: 일자 (str 또는 Timestamp)
            - columns: 종목(티커 또는 종목명)
            - 각 셀: 종가 또는 원하는 가격 시계열
            - 예시:
                index        005930.KS   035720.KQ
                2025-01-01   65200       93400
                ...
        target_date (str): 
            - 조회할 날짜 (YYYY-MM-DD 형식, DataFrame index와 일치해야 함)
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
        >>> result = rsi(df, target_date="2025-01-10", threshold=80, operator=">=")
        >>> print(result)  # {'005930.KS': 82.6, ...}
    """
    rsi_df = calc_rsi_df(data)

    if target_date not in rsi_df.index:
        return f"{target_date} is not in RSI DataFrame index"

    rsi_on_date = rsi_df.loc[target_date]

    if operator == "<=":
        filtered = rsi_on_date[rsi_on_date <= threshold]
    else:
        filtered = rsi_on_date[rsi_on_date >= threshold]
    return filtered.to_dict()

def detect_cross(data: pd.DataFrame, stock_name, start_date, end_date, cross_type, short: int = 5, long: int = 20) -> Dict[str, float]:
    """
    골든/데드크로스 구해서 질문에 대한 정답 내뱉는 함수
    """
    sma = moving_average(data, short)   
    lma = moving_average(data, long)    

    golden_cross = (sma >= lma) & (sma.shift(1) < lma.shift(1))
    dead_cross = (sma <= lma) & (sma.shift(1) > lma.shift(1))

    if start_date and end_date:
        idx = (data.index >= pd.to_datetime(start_date)) & (data.index <= pd.to_datetime(end_date))
    else:
        idx = slice(None)

    if stock_name:
        result = {}
        golden_dates = golden_cross[stock_name][idx][golden_cross[stock_name][idx]].index.tolist()
        dead_dates   = dead_cross[stock_name][idx][dead_cross[stock_name][idx]].index.tolist()

        if cross_type == "golden":
            if len(golden_dates) > 0:
                result["golden"] = len(golden_dates)
        elif cross_type == "dead":
            if len(dead_dates) > 0:
                result["dead"] = len(dead_dates)
        else:  
            if len(golden_dates) > 0:
                result["golden"] = len(golden_dates)
            if len(dead_dates) > 0:
                result["dead"] = len(dead_dates)
        return result
    else:
        out = {}
        for ticker in data.columns:
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
        return out

def price_vs_adj_ma(data: pd.DataFrame, target_date, ma_window: int, pct: float, price_column: str, operator: Literal[">=","<="] = ">=") -> Dict[str, float]:
    """
    이동평균 대비 퍼센트 구해 질문에 대한 정답 내뱉는 함수
    """
    if not isinstance(data.columns, pd.MultiIndex):
        return "DataFrame columns must be MultiIndex (PriceType, Ticker)"
    if target_date not in data.index:
        return f"{target_date} is not in index!"

    results = {}
    target_date = pd.to_datetime(target_date)

    data_close = data.xs(price_column, level="Price", axis=1)
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
        
    return results

def bollinger_bands(data: pd.DataFrame, target_date, bollinger_side : str, window: int = 20, std_dev: float = 2.0) -> Dict[str, int]:
    """
    볼린저밴드 구해 질문에 대한 정답 내뱉는 함수
    """
    if not isinstance(data.columns, pd.MultiIndex):
        return "DataFrame columns must be MultiIndex (PriceType, Ticker)"
    if target_date not in data.index:
        return f"{target_date} is not in index!"

    results = {}
    target_date = pd.to_datetime(target_date)

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

    return results

def get_high_volume_stocks(df: pd.DataFrame, target_date, ma_window, volume_ratio) -> Dict[str, int]:
    """
    거래량 급증 종목 구해 질문에 대한 정답 내뱉는 함수
    """

    results = {}
    ma_df = moving_average(df,ma_window)
    
    if target_date not in df.index:
        return f"{target_date} is not in index!"

    for ticker in df.columns:
        today_vol = df.loc[target_date, ticker]
        ma_vol = ma_df.loc[target_date, ticker]

        if pd.isna(ma_vol) or ma_vol == 0:
            continue
        increase_pct = ((today_vol - ma_vol) / ma_vol) * 100

        if increase_pct >= volume_ratio:
            results[ticker] = int(round(float(increase_pct)))
    return results

# Type에 따른 함수 호출
FIELD_FUNC = {
    "시그널감지_RSI_oversold": rsi,
    "시그널감지_RSI_overbought": rsi,
    "시그널횟수_크로스_통합": detect_cross,
    "시그널횟수_데드크로스": detect_cross,
    "시그널횟수_골든크로스": detect_cross,
    "시그널종목_데드크로스_기간": detect_cross,
    "시그널종목_골든크로스_기간": detect_cross,
    "시그널감지_MA60돌파" : price_vs_adj_ma,
    "시그널감지_MA5돌파" : price_vs_adj_ma,
    "시그널감지_MA20돌파" : price_vs_adj_ma,
    "시그널감지_볼린저_upper" : bollinger_bands,
    "시그널감지_볼린저_lower" : bollinger_bands,
    "시그널감지_거래량급증" : get_high_volume_stocks
}

def answer_task3(q: dict) -> List[str]:
    """
    q : LLM JSON 파싱 결과
    반환 : task3 질문에 대한 답
    """

    tickers  = get_tickers(q)
    if not tickers:
        return []
    
    func = FIELD_FUNC[q["type"]]

    if q['value'] != None:
        value = int(q['value'])

    if q['moving_average_line'] != None:
        moving_value = int(q["moving_average_line"])

    need_col = q['OHLCV']
    
    stock_name = q['stock_name']
    if stock_name != None:
        one_ticker = name_to_ticker[stock_name]
    else:
        one_ticker = None
    
    if q['target_date'] != None and q['moving_average_line'] == '14':
        tgt_date  = datetime.strptime(q['target_date'], "%Y-%m-%d")
        start_dt  = tgt_date - timedelta(days=100)
        end_dt    = tgt_date + timedelta(days=1) 

    elif q['target_date'] != None and q['moving_average_line'] in ("5","20","60"):
        tgt_date  = datetime.strptime(q['target_date'], "%Y-%m-%d")
        if moving_value == 5:
            extra_date = 20
        elif moving_value == 20:
            extra_date = 40  
        else:  
            extra_date = 110
        start_dt  = tgt_date - timedelta(days=extra_date)
        end_dt    = tgt_date + timedelta(days=1) 

    elif q['target_date'] != None :
        tgt_date  = datetime.strptime(q['target_date'], "%Y-%m-%d")
        start_dt  = tgt_date - timedelta(days=40)
        end_dt    = tgt_date + timedelta(days=1) 
    
    else:
        start_date  = datetime.strptime(q['start_date'], "%Y-%m-%d")
        end_date = datetime.strptime(q['end_date'],"%Y-%m-%d")

        start_dt = start_date - timedelta(days=40) 
        end_dt    = end_date + timedelta(days=1) 

    if stock_name != None:
        data = yf.download(one_ticker, start_dt, end_dt, interval="1d", progress=False, threads=False, auto_adjust=False)
    else:
        data = download_in_batches(tickers, start_dt, end_dt, batch_size=200)
    
    if need_col != None:
        data_need_col = data.xs(need_col, level="Price", axis=1)
    else:
        data_need_col = data.xs("Adj Close", level="Price", axis=1)

    if q['type'] in ("시그널감지_RSI_oversold","시그널감지_RSI_overbought"):
        rsi_results = func(data_need_col,q['target_date'], value, q['operator'])

        rsi_stock_name = {}
        for ticker,value in rsi_results.items():
            clean_ticker = ticker.replace('.KS', '').replace('.KQ', '')
            stock_name = ticker_to_name.get(clean_ticker, clean_ticker)
            rsi_stock_name[stock_name] = round(value,2)

        sorted_dict = dict(sorted(rsi_stock_name.items(), key=lambda x: x[1], reverse=True))
        return sorted_dict

    if q['type'] in ("시그널횟수_크로스_통합","시그널횟수_데드크로스","시그널횟수_골든크로스","시그널종목_데드크로스_기간","시그널종목_골든크로스_기간"):
        cross_df = func(data_need_col,one_ticker,start_date,end_date,q['type_of_cross'])
        if q.get('stock_name', None):
            return cross_df
        else:
            stock_name_dict = {}
            for ticker, value in cross_df.items():
                clean_ticker = ticker.replace('.KS', '').replace('.KQ', '')
                stock_name = ticker_to_name.get(clean_ticker, clean_ticker)
                stock_name_dict[stock_name] = value
            return stock_name_dict
            
    if q['type'] in ("시그널감지_MA60돌파", "시그널감지_MA5돌파", "시그널감지_MA20돌파"):
        ma_result = func(data,q['target_date'],moving_value,value,need_col,q['operator'])
        
        stock_name_dict = {}
        for ticker, percentage in ma_result.items():
            clean_ticker = ticker.replace('.KS', '').replace('.KQ', '')
            stock_name = ticker_to_name.get(clean_ticker, clean_ticker)
            stock_name_dict[stock_name] = percentage
        
        sorted_dict = dict(sorted(stock_name_dict.items(),key=lambda x: float(str(x[1]).replace('%','')),reverse=True))
        return sorted_dict
    
    if q['type'] in ("시그널감지_볼린저_upper", "시그널감지_볼린저_lower"):
        bollinger = func(data,q['target_date'],q['bollinger_side'])

        stock_bollinger_dict = {}
        for ticker, close in bollinger.items():
            clean_ticker = ticker.replace('.KS', '').replace('.KQ', '')
            stock_name = ticker_to_name.get(clean_ticker, ticker)
            stock_bollinger_dict[stock_name] = close

        sorted_dict = dict(sorted(stock_bollinger_dict.items(), key=lambda x: x[1], reverse=True))
        return sorted_dict

    if q['type'] in ("시그널감지_거래량급증"):
        volume_high = func(data_need_col, q['target_date'],moving_value,value)    

        stock_volume_dict = {}
        for ticker, volume in volume_high.items():
            clean_ticker = ticker.replace('.KS', '').replace('.KQ', '')
            stock_name = ticker_to_name.get(clean_ticker, ticker)
            stock_volume_dict[stock_name] = volume

        sorted_dict = dict(sorted(stock_volume_dict.items(), key=lambda x: x[1], reverse=True))
        return sorted_dict