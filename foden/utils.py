from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf
import json, re, ast, time

"""
Task1 / Task2 / Task3 공통으로 사용되는 함수 정리 
"""

# 티커 / 종목명 / 시장 정리한 파일
market_list = pd.read_csv("krx_tickers_cleaned.csv 경로")

# 종목명을 티커로 변경
name_to_ticker = {row['name']: f"{str(row['code']).zfill(6)}{'.KS' if row['market']=='KOSPI' else '.KQ'}"for _, row in market_list.iterrows()}

# 티커를 종목명으로 변경
ticker_to_name = dict(zip(market_list['code'], market_list['name']))

# 특정 종목이 속한 시장 반환
name_to_market = dict(zip(market_list['name'], market_list['market']))

def parse_llm_json(text: str) -> dict:
    """
    LLM이 질문을 각 Task에 맞게 분석한 JSON을 정리하는 함수
    """
    # 1)  {...} 블록만 추출
    m = re.search(r'\{.*\}', text, re.S)
    if not m:
        raise ValueError("JSON 블록을 찾을 수 없습니다.")
    j = m.group()

    # 2) JSON → dict
    try:
        return json.loads(j)
    except json.JSONDecodeError:
        return ast.literal_eval(j)  
    
def get_tickers(answer):
    """
    특정 시장에 있는 모든 티커들을 불러오는 함수
    """
    if answer['market'] == "KOSPI":
        ticker_lists = market_list.loc[market_list["market"] == "KOSPI", "code"].tolist()
        ticker_lists = [f"{ticker}.KS" for ticker in ticker_lists]
        return ticker_lists
    elif answer['market'] == "KOSDAQ":
        ticker_lists = market_list.loc[market_list["market"] == "KOSDAQ", "code"].tolist()
        ticker_lists = [f"{ticker}.KQ" for ticker in ticker_lists]
        return ticker_lists
    else:
        kospi_tickers = market_list.loc[market_list["market"] == "KOSPI", "code"].tolist()
        kosdaq_tickers = market_list.loc[market_list["market"] == "KOSDAQ", "code"].tolist()
        ticker_lists = [f"{ticker}.KS" for ticker in kospi_tickers] + \
                      [f"{ticker}.KQ" for ticker in kosdaq_tickers]
        return ticker_lists

def download_in_batches(tickers, start_dt, end_dt, batch_size=100):
    """
    배치 단위로 다운로드 후 멀티인덱스 DataFrame으로 합치는 함수
    """
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