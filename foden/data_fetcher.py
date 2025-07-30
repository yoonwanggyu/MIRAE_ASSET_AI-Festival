import yfinance as yf
import pandas as pd
import time

"""
yfiance에서 데이터를 다운로드 하는 함수 -> Redis에서 가져오는 함수로 변경 필요
"""

def download_in_batches(tickers, start_dt, end_dt, batch_size=100) -> pd.DataFrame:
    """
    여러 종목들을 배치 단위로 다운로드 후 멀티인덱스 DataFrame으로 합치는 함수
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
    

def get_stock_data(ticker: str, start: str, end: str, interval: str = "1d") -> pd.DataFrame:
    """
    한 종목만 다운로드 하는 함수
    """
    return yf.download(
        tickers=ticker,
        start=start,
        end=end,
        interval=interval,
        progress=False,
        threads=False,
        auto_adjust=False
    )