import json, re, ast, time
import pandas as pd
import yfinance as yf
from typing import List
from datetime import datetime, timedelta
from typing import Dict, Callable, List

def parse_llm_json(text: str) -> dict:
    # 1)  {...} 블록만 추출
    m = re.search(r'\{.*\}', text, re.S)
    if not m:
        raise ValueError("JSON 블록을 찾을 수 없습니다.")
    j = m.group()

    # 2) JSON → dict
    try:
        return json.loads(j)
    except json.JSONDecodeError:
        return ast.literal_eval(j)   # fallback
    
market_list = pd.read_csv(r"C:\Users\rladl\Desktop\Mirae_Agent\MIRAE_ASSET_AI-Festival\sasha\test\krx_tickers_cleaned.csv")

def get_tickers(answer):
    if answer['market'] == "KOSPI":
        ticker_lists = market_list.loc[market_list["market"] == "KOSPI", "code"].tolist()
        # .KS 접미사 추가
        ticker_lists = [f"{ticker}.KS" for ticker in ticker_lists]
        print(f"조사할 종목 수 : {len(ticker_lists)}")
        return ticker_lists
    elif answer['market'] == "KOSDAQ":
        ticker_lists = market_list.loc[market_list["market"] == "KOSDAQ", "code"].tolist()
        # .KQ 접미사 추가
        ticker_lists = [f"{ticker}.KQ" for ticker in ticker_lists]
        print(f"조사할 종목 수 : {len(ticker_lists)}")
        return ticker_lists
    else:
        # 전체 시장인 경우 각각에 맞는 접미사 추가
        kospi_tickers = market_list.loc[market_list["market"] == "KOSPI", "code"].tolist()
        kosdaq_tickers = market_list.loc[market_list["market"] == "KOSDAQ", "code"].tolist()
        
        ticker_lists = [f"{ticker}.KS" for ticker in kospi_tickers] + \
                      [f"{ticker}.KQ" for ticker in kosdaq_tickers]
        print(f"조사할 종목 수 : {len(ticker_lists)}")
        return ticker_lists
    
# 1. 유틸: 연산자 함수 테이블
OPS: Dict[str, Callable] = {
    ">":  lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "<":  lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    "range": lambda a, min_val, max_val: min_val <= a <= max_val
}

def apply_operator(df, operator, value, min_value=None, max_value=None):
    """
    데이터프레임에 operator 조건을 적용하는 함수
    """
    if operator == "range":
        return (df >= min_value) & (df <= max_value)
    else:
        return OPS[operator](df, value)

# 2. 유틸: yfinance 에서 필요한 칼럼
FIELD_COLS = {
    "change_rate":        "Close",
    "volume_change_rate": "Volume",
    "volume_abs":         "Volume",
    "price":              "Close",
}

DATE_RANGE = {
    "change_rate":        2,
    "volume_change_rate": 2,
    "volume_abs":         1,
    "price":              1,
}

def download_in_batches(tickers, start_dt, end_dt, batch_size=100):
    """배치 단위로 다운로드 후 멀티인덱스 DataFrame으로 합치기"""
    all_ticker_data = {}
    total_batches = len(tickers) // batch_size + (1 if len(tickers) % batch_size > 0 else 0)
    
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i+batch_size]
        batch_num = i // batch_size + 1
        
        print(f"Processing batch {batch_num}/{total_batches} ({len(batch)} tickers)")
        
        try:
            # 배치 단위로 다운로드
            hist = yf.download(
                tickers=" ".join(batch),
                start=start_dt,
                end=end_dt,
                interval="1d",
                group_by="ticker",
                progress=False,
                threads=True,
                auto_adjust=False,
            )
            
            if not hist.empty:
                # 단일 종목인 경우 멀티인덱스로 변환
                if len(batch) == 1:
                    ticker = batch[0]
                    hist.columns = pd.MultiIndex.from_product([[ticker], hist.columns])
                
                # 각 ticker별로 데이터 저장
                for ticker in batch:
                    try:
                        if len(batch) == 1:
                            ticker_data = hist[ticker]
                        else:
                            ticker_data = hist[ticker]
                        
                        if not ticker_data.empty and not ticker_data.isna().all().all():
                            all_ticker_data[ticker] = ticker_data
                    except (KeyError, AttributeError):
                        print(f"No data for {ticker}")
                
                print(f"✓ Batch {batch_num} completed")
            else:
                print(f"✗ Batch {batch_num} returned empty data")
                
        except Exception as e:
            print(f"✗ Batch {batch_num} failed: {e}")
            # 실패한 배치는 개별 처리
            for ticker in batch:
                try:
                    single_hist = yf.download(ticker, start=start_dt, end=end_dt, progress=False)
                    if not single_hist.empty:
                        all_ticker_data[ticker] = single_hist
                        print(f"Individual download success: {ticker}")
                except:
                    print(f"Failed to download {ticker}")
        
        time.sleep(1)
    
    # 모든 ticker 데이터를 멀티인덱스 DataFrame으로 합치기
    if all_ticker_data:
        print(f"Combining data for {len(all_ticker_data)} tickers...")
        
        # 멀티인덱스 DataFrame 생성
        combined_data = pd.concat(all_ticker_data, axis=1)
        
        # 컬럼 순서 정리 (Price 기준으로)
        combined_data.columns.names = ['Ticker', 'Price']
        
        print(f"Final data shape: {combined_data.shape}")
        print(f"Columns: {combined_data.columns.get_level_values(1).unique().tolist()}")
        
        return combined_data
    else:
        print("No data downloaded")
        return pd.DataFrame()
    
def screen_stocks(q: dict) -> List[str]:
    """
    q : LLM JSON 파싱 결과.
    반환 : 모든 조건을 동시에 만족하는 종목 코드 리스트(중복 제거·정렬).
    """

    print(f"LLM의 질문 분석 결과 : {q}")

    # 조사할 시장
    tickers  = get_tickers(q)
    if not tickers:
        return []
    
    # 종목 정보 로드
    stock_info = pd.read_csv(r'C:\Users\rladl\Desktop\Mirae_Agent\MIRAE_ASSET_AI-Festival\sasha\test\krx_tickers_cleaned.csv')  
    ticker_to_name = dict(zip(stock_info['code'], stock_info['name']))

    # 조건 수
    num_conditions = len(q['conditions'])
    print(f"조건 수 = 반복문 횟수 : {num_conditions}")

    condition_results: List[List[str]] = []

    stock_names = {}
    # 조건 수 만큼 개별적으로 돌기
    for i in range(num_conditions):

        print(f"{i+1}번째 반복문 돌아가는 중----------------------")

        date_range = DATE_RANGE[q['conditions'][i]['field']]
        print(f"date_range : {date_range}")

        # 거래량 / 종가 계산 컬럼 가져오기
        need_col = FIELD_COLS[q['conditions'][i]['field']]
        print(f"필요한 컬럼 : {need_col}")

        # 질문에 있는 날짜
        tgt_date  = datetime.strptime(q["date"], "%Y-%m-%d")
        print(f"타킷 날짜 : {tgt_date}")

        # 주말·휴일 여유
        start_dt  = tgt_date - timedelta(days=5)            
        print(f"조회 시작 날짜 : {start_dt}")

        # 끝 날짜
        end_dt    = tgt_date + timedelta(days=1)          
        print(f"조희 끝 날짜 : {end_dt}")

        # 배치 다운로드
        data = download_in_batches(tickers, start_dt, end_dt, batch_size=200)

        # 거래량 / 종가 계산 컬럼만 있는 데이터프레임
        only_need_col = data.xs(need_col, level=1, axis=1)

        # 전날 대비 거래량 / 등락률 계산
        if date_range == 2:
            only_need_col_edit = only_need_col.pct_change() * 100
            final_data = only_need_col_edit.iloc[-1]
            final_data = final_data.dropna()
            print("date_range = 2일 때 계산---------------------------")
            print(final_data.head(10))
        else:
            final_data = only_need_col.iloc[-1]
            final_data = final_data.dropna()
            print("date_range = 1일 때 계산---------------------------")
            print(final_data.head(10))

        # 연산자에 따른 계산 다르게
        def apply_operator(df, operator, value, min_value=None, max_value=None):
            """
            데이터프레임에 operator 조건을 적용하는 함수
            """
            if operator == "range":
                return (df >= min_value) & (df <= max_value)
            else:
                return OPS[operator](df, value)
            
        result = apply_operator(final_data, q['conditions'][i]['operator'], q['conditions'][i]['value'], q['conditions'][i]['min_value'], q['conditions'][i]['max_value'])

        # 조건 만족해서 True인 행의 Ticker들
        true_tickers = result[result == True].index.tolist()
        print("조건을 만족하는 ticker들 수:", len(true_tickers))
        # 조건별 결과 저장
        condition_results.append(true_tickers)

    # ---------- 교집합 계산 ----------
    if not condition_results:          # 보호 코드
        return {}

    # 조건이 1개면 그대로, 2개 이상이면 set 교집합
    if len(condition_results) == 1:
        final_tickers = condition_results[0]
    else:
        # map(set, …) 으로 각 리스트를 집합으로 변환 후 reduce 로 교차
        from functools import reduce
        final_tickers = list(
            reduce(set.intersection, map(set, condition_results)))

    print(f"최종 선별된 종목 수: {len(final_tickers)}")

    # 최종 결과를 딕셔너리로 변환
    stock_names = {}
    for ticker in final_tickers:
        clean_ticker = ticker.replace('.KS', '').replace('.KQ', '')
        stock_name = ticker_to_name.get(clean_ticker, ticker)
        stock_names[ticker] = stock_name

    return stock_names
