import yfinance as yf
import pandas as pd
from typing import List, Dict, Literal, Callable
from datetime import datetime, timedelta

from utils import *
    
OPS: Dict[str, Callable] = {
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b
}

def apply_operator(df, operator, value):
    """
    데이터프레임에 operator 조건을 적용하는 함수
    """
    return OPS[operator](df, value)
    
##### 이동평균선 함수 #####
# def moving_average(df: pd.DataFrame, window: int) -> pd.DataFrame:
#     return df.rolling(window).mean()
def moving_average(df: pd.DataFrame, window: int, status : str = 'mean') -> pd.DataFrame:
    if status == 'mean':
        return df.rolling(window).mean()
    else:
        return df.rolling(window).std(ddof=1) 

# ────────────────────────RSI───────────────────────────────────────
def calc_rsi_df(data: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    def rsi_one(series: pd.Series) -> pd.Series:
        delta = series.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        # avg_gain = moving_average(gain.to_frame(), window=period, status='mean').iloc[:,0]
        # avg_loss = moving_average(loss.to_frame(), window=period, status='mean').iloc[:,0]

        # Wilder's Smoothing Method (표준 RSI 계산법)
        avg_gain = gain.ewm(alpha=1/period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1/period, adjust=False).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    return data.apply(rsi_one, axis=0)

def rsi(data: pd.DataFrame, target_date, threshold, operator) -> Dict[str, float]:
    # 모든 티커의 RSI 계산
    rsi_df = calc_rsi_df(data)

    if target_date not in rsi_df.index:
        raise ValueError(f"{target_date} is not in RSI DataFrame index")

    # 해당 날짜의 모든 종목 RSI Series
    rsi_on_date = rsi_df.loc[target_date]

    if operator == "<=":
        filtered = rsi_on_date[rsi_on_date <= threshold]
    else:
        filtered = rsi_on_date[rsi_on_date >= threshold]
    return filtered.to_dict()

# ────────────────────────크로스───────────────────────────────────────
def detect_cross(data: pd.DataFrame, stock_name, start_date, end_date, cross_type, short: int = 5, long: int = 20) -> Dict[str, float]:
    """
    stock_name이 있는 경우 : 횟수 반환
    없는 경우 : 종목명 반환
    """
    sma = moving_average(data, short)   # 5
    lma = moving_average(data, long)    # 20

    # 클린 크로스 공식
    # 전일에는 단기 < 장기, 당일에는 단기 >= 장기인 경우 골든크로스
    golden_cross = (sma >= lma) & (sma.shift(1) < lma.shift(1))
    dead_cross = (sma <= lma) & (sma.shift(1) > lma.shift(1))

    # 최소 30줄 이상 보기
    # print(data.head(30))
    # print(sma[stock_name].head(30))
    # print(lma[stock_name].head(30))
    # print(golden_cross[stock_name].head(30))
    
    # 날짜 필터링
    if start_date and end_date:
        idx = (data.index >= pd.to_datetime(start_date)) & (data.index <= pd.to_datetime(end_date))
    else:
        idx = slice(None)

    if stock_name:
        result = {}
        golden_dates = golden_cross[stock_name][idx][golden_cross[stock_name][idx]].index.tolist()
        dead_dates   = dead_cross[stock_name][idx][dead_cross[stock_name][idx]].index.tolist()

        print("=== 골든크로스 발생일 ===")
        print(golden_dates)
        print("=== 데드크로스 발생일 ===")
        print(dead_dates)

        if cross_type == "golden":
            if len(golden_dates) > 0:
                result["golden"] = len(golden_dates)
        elif cross_type == "dead":
            if len(dead_dates) > 0:
                result["dead"] = len(dead_dates)
        else:  # both or None
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
            else:  # both or None
                info = {}
                if len(golden_dates) > 0:
                    info['golden'] = len(golden_dates)
                if len(dead_dates) > 0:
                    info['dead'] = len(dead_dates)
                if info:
                    out[ticker] = info
        return out

# ────────────────────────MA───────────────────────────────────────
def price_vs_adj_ma(data: pd.DataFrame, target_date, ma_window: int, pct: float, price_column: str, operator: Literal[">=","<="] = ">=") -> Dict[str, float]:
    """
    조건을 만족하는 종목과 해당 종목의 이동평균 대비 퍼센트를 함께 반환
    """
    if not isinstance(data.columns, pd.MultiIndex):
        raise ValueError("DataFrame columns must be MultiIndex (PriceType, Ticker)")
    if target_date not in data.index:
        raise ValueError(f"{target_date} is not in index!")

    results = {}
    target_date = pd.to_datetime(target_date)

    data_close = data.xs(price_column, level="Price", axis=1)
    data_adj_close = data.xs("Adj Close", level="Price", axis=1)

    adj_ma_df = moving_average(data_adj_close, ma_window)
    
    for ticker in data_adj_close.columns:
        # 타겟 날짜 종가
        current_price = data_close[ticker].loc[target_date]

        # 타겟 날짜 이동평균값
        ma_val = adj_ma_df[ticker].loc[target_date]
        if pd.isna(ma_val) or ma_val == 0:
            continue
        
        # 이동평균 대비 퍼센트 계산
        diff_pct = ((current_price - ma_val) / ma_val) * 100

        # 조건 처리
        if operator == ">=" and diff_pct >= pct:
            results[ticker] = f"{round(diff_pct, 2)}%"
        elif operator == "<=" and diff_pct <= pct:
            results[ticker] = f"{round(diff_pct, 2)}%"
        
    return results

# ────────────────────────볼린저밴드───────────────────────────────────────
def bollinger_bands(data: pd.DataFrame, target_date, bollinger_side : str, window: int = 20, std_dev: float = 2.0) -> Dict[str, int]:
    """
    볼린저밴드는 'Adj Close'로 계산, 터치는 'Close'로 비교 (멀티인덱스)
    반환: {티커(또는 이름): Close}
    """
    if not isinstance(data.columns, pd.MultiIndex):
        raise ValueError("DataFrame columns must be MultiIndex (PriceType, Ticker)")
    if target_date not in data.index:
        raise ValueError(f"{target_date} is not in index!")

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

# ────────────────────────거래량 급증───────────────────────────────────────
def get_high_volume_stocks(df: pd.DataFrame, target_date, ma_window, volume_ratio) -> Dict[str, int]:
    """
    주어진 날짜에 거래량이 n일 이동평균 대비 ratio 배 이상 급증한 종목을 반환.
    - tickers: 종목 코드 리스트 (예: ['005930.KS', '035420.KS'])
    - date: 날짜 문자열 ('YYYY-MM-DD')
    - ma_window: 이동평균 산출 기간 (기본값: 20)
    - volume_ratio: 급증 기준 배수 (예: 5.0 = 500%)
    """

    results = {}
    # rolling mean 구하기 (각 티커별)
    ma_df = moving_average(df,ma_window)
    
    # target_date가 index에 있는지 체크
    if target_date not in df.index:
        raise ValueError(f"{target_date} is not in index!")
    
    # 각 티커별로 조건 검사
    for ticker in df.columns:
        today_vol = df.loc[target_date, ticker]
        ma_vol = ma_df.loc[target_date, ticker]

        if str(ticker).replace('.KS','').replace('.KQ','') == "315640":
            print(f"315640: today_vol={today_vol}, ma_vol={ma_vol}")

        if pd.isna(ma_vol) or ma_vol == 0:
            continue
        increase_pct = ((today_vol - ma_vol) / ma_vol) * 100
        
        if str(ticker).replace('.KS','').replace('.KQ','') == "315640":
            print(f"315640: increase_pct={increase_pct}")

        if increase_pct >= volume_ratio:
            results[ticker] = int(round(float(increase_pct)))
    return results

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

def res_task3(q: dict) -> List[str]:
    """
    q : LLM JSON 파싱 결과
    반환 : task3 질문에 대한 답
    """

    # 조사할 시장
    tickers  = get_tickers(q)
    if not tickers:
        return []
    
    # 사용할 함수
    func = FIELD_FUNC[q["type"]]
    print(f"사용할 함수 : {func}")

    # 질문 안에 있는 비교 값
    value = int(q['value'])
    print(f"비교할 값 : {value}")

    # 이동 평균선 구하기
    if q['moving_average_line'] != None:
        moving_value = int(q["moving_average_line"])
        print(f"ma 질문에서 비교할 이동 평균값 : {moving_value}")

    # 필요한 열
    need_col = q['OHLCV']
    print(f"필요한 열 : {need_col}")
    
    # 종목 정보 로드
    stock_name = q['stock_name']
    print(f"종목 이름 : {stock_name}")
    if stock_name != None:
        one_ticker = name_to_ticker[stock_name]
    else:
        one_ticker = None
    
    # 날짜
        # RSI 질문
    if q['target_date'] != None and q['moving_average_line'] == '14':
        print(f"RSI 질문 날짜")
        tgt_date  = datetime.strptime(q['target_date'], "%Y-%m-%d")
        print(f"target date : : {tgt_date}")
        start_dt  = tgt_date - timedelta(days=100)
        print(f"start_date : {start_dt}")
        end_dt    = tgt_date + timedelta(days=1) 
        print(f"end_date : {end_dt}")

        # MA 질문 / 거래량 급증
    elif q['target_date'] != None and q['moving_average_line'] in ("5","20","60"):
        print("MA 질문 날짜 / 거래량 급증")
        tgt_date  = datetime.strptime(q['target_date'], "%Y-%m-%d")
        print(f"target date : {tgt_date}")
        if moving_value == 5:
            extra_date = 20
        elif moving_value == 20:
            extra_date = 40  
        else:  # 60일
            extra_date = 110
        start_dt  = tgt_date - timedelta(days=extra_date)
        print(f"start_date : {start_dt}")
        end_dt    = tgt_date + timedelta(days=1) 
        print(f"end_date : {end_dt}")

       # 볼린저 질문
    elif q['target_date'] != None :
        print(f"볼린저 질문 날짜")
        tgt_date  = datetime.strptime(q['target_date'], "%Y-%m-%d")
        print(f"target date : {tgt_date}")
        start_dt  = tgt_date - timedelta(days=40)
        end_dt    = tgt_date + timedelta(days=1) 
    
        # 크로스 질문
    else:
        print(f"크로스 질문 날짜")
        start_date  = datetime.strptime(q['start_date'], "%Y-%m-%d")
        end_date = datetime.strptime(q['end_date'],"%Y-%m-%d")
        print(f"start_date : {start_date}")
        print(f"end_date : {end_date}")

        # 계산용
        start_dt = start_date - timedelta(days=40) 
        end_dt    = end_date + timedelta(days=1) 

    # 종목 다운로드
        # 볼린저 밴드는 data 사용
    if stock_name != None:
        data = yf.download(one_ticker, start_dt, end_dt, interval="1d", progress=False, threads=False, auto_adjust=False)
    else:
        data = download_in_batches(tickers, start_dt, end_dt, batch_size=200)
    print(f"다운로드된 데이터 기간: {data.index.min()} ~ {data.index.max()}")
    print(data.head(10))
    
    if need_col != None:
        # 거래량 질문
        data_need_col = data.xs(need_col, level="Price", axis=1)
        print(data_need_col.head(5))
    else:
        # 크로스 질문
        data_need_col = data.xs("Adj Close", level="Price", axis=1)
        print(data_need_col.head(5))
    
    ###### RSI 관련 질문에 대한 답 ######
    if q['type'] in ("시그널감지_RSI_oversold","시그널감지_RSI_overbought"):
        print(f"RSI 계산 중=====================")
        print(f"operator : {q['operator']}")
        rsi_results = func(data_need_col,q['target_date'], value, q['operator'])

        rsi_stock_name = {}
        for ticker,value in rsi_results.items():
            clean_ticker = ticker.replace('.KS', '').replace('.KQ', '')
            stock_name = ticker_to_name.get(clean_ticker, clean_ticker)
            rsi_stock_name[stock_name] = round(value,2)

        sorted_dict = dict(sorted(rsi_stock_name.items(), key=lambda x: x[1], reverse=True))
        return sorted_dict

    ###### 크로스 관련 질문에 대한 답 ######
    if q['type'] in ("시그널횟수_크로스_통합","시그널횟수_데드크로스","시그널횟수_골든크로스","시그널종목_데드크로스_기간","시그널종목_골든크로스_기간"):
        print(f"크로스 계산 중=====================")

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
            
    ###### n일 이동평균 관련 질문에 대한 답 ######
    if q['type'] in ("시그널감지_MA60돌파", "시그널감지_MA5돌파", "시그널감지_MA20돌파"):
        print(f"n일 이동평균 계산 중===================")

        ma_result = func(data,q['target_date'],moving_value,value,need_col,q['operator'])
        
        stock_name_dict = {}
        for ticker, percentage in ma_result.items():
            clean_ticker = ticker.replace('.KS', '').replace('.KQ', '')
            stock_name = ticker_to_name.get(clean_ticker, clean_ticker)
            stock_name_dict[stock_name] = percentage
        
        sorted_dict = dict(sorted(stock_name_dict.items(),key=lambda x: float(str(x[1]).replace('%','')),reverse=True))
        return sorted_dict
    
    ###### 볼리저밴드 ######
    if q['type'] in ("시그널감지_볼린저_upper", "시그널감지_볼린저_lower"):
        print(f"볼린저밴드 계산 중===================")

        bollinger = func(data,q['target_date'],q['bollinger_side'])

        stock_bollinger_dict = {}
        for ticker, close in bollinger.items():
            clean_ticker = ticker.replace('.KS', '').replace('.KQ', '')
            stock_name = ticker_to_name.get(clean_ticker, ticker)
            stock_bollinger_dict[stock_name] = close

        sorted_dict = dict(sorted(stock_bollinger_dict.items(), key=lambda x: x[1], reverse=True))
        return sorted_dict

    ###### 거래량 급증 ######
    if q['type'] in ("시그널감지_거래량급증"):
        print(f"거래량 급증 계산 중===================")
        
        volume_high = func(data_need_col, q['target_date'],moving_value,value)    

        stock_volume_dict = {}
        for ticker, volume in volume_high.items():
            clean_ticker = ticker.replace('.KS', '').replace('.KQ', '')
            stock_name = ticker_to_name.get(clean_ticker, ticker)
            stock_volume_dict[stock_name] = volume

        sorted_dict = dict(sorted(stock_volume_dict.items(), key=lambda x: x[1], reverse=True))
        return sorted_dict