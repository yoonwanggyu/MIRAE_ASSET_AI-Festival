import yfinance as yf
import pandas as pd
import json
from datetime import datetime, timedelta


# Redis 연결 및 유틸리티 함수 임포트
from redis_connector import get_redis_connection
redis_conn = get_redis_connection()

from utils import is_redis_target_date, get_all_stocks_for_date_from_redis


def fetch_single_stock_data_from_redis(stock_name: str, code: str, market: str, target_date: str) -> dict | None:
    """
    특정 종목(이름, 코드, 시장)의 특정 날짜 데이터를 Redis에서 직접 GET하여 반환합니다.
    """
    redis_conn = get_redis_connection()
    if not redis_conn or not is_redis_target_date(target_date):
        print(f"DEBUG: fetch_single_stock_data_from_redis: Skipping as Redis conn is {bool(redis_conn)} or date {target_date} is not target date.")
        return None

    # Redis 키 구성: {date_str}:{market}:{code6}:{name}
    # name_to_market()에서 반환되는 market은 이미 적절히 처리되어 있다고 가정
    # stock_name도 이미 utils.py에서 정규화되어 넘어온다고 가정
    redis_key = f"{target_date}:{market.upper()}:{code}:{stock_name}"
    print(f"DEBUG: fetch_single_stock_data_from_redis: Attempting direct Redis GET for key: '{redis_key}'")

    try:
        result_json = redis_conn.get(redis_key)
        if result_json:
            data = json.loads(result_json)
            print(f"DEBUG: fetch_single_stock_data_from_redis: Successfully fetched and parsed data for '{stock_name}' on '{target_date}'.")
            return data
        else:
            print(f"DEBUG: fetch_single_stock_data_from_redis: No data found for key: '{redis_key}' in Redis.")
            return None
    except (json.JSONDecodeError, ValueError) as e:
        print(f"DEBUG: fetch_single_stock_data_from_redis: Error parsing JSON or key for '{redis_key}': {e}. Raw JSON: {result_json}")
        return None
    except Exception as e:
        print(f"DEBUG: fetch_single_stock_data_from_redis: Unexpected error during Redis GET for '{redis_key}': {e}")
        return None


def fetch_from_redis(target_date: str, end_date: str = None, target_tickers: list = None) -> pd.DataFrame:
    """
    특정 날짜(또는 날짜 구간)의 모든 종목 데이터를 Redis에서 가져와 yfinance와 유사한 MultiIndex DataFrame으로 만듭니다.
    이 함수는 '전체 시장 스캔'이 필요한 경우에만 호출됩니다.
    
    Args:
        target_date: 시작 날짜 (YYYY-MM-DD 형식)
        end_date: 종료 날짜 (YYYY-MM-DD 형식, None이면 target_date만 조회)
        target_tickers: 특정 티커만 필터링 (None이면 모든 종목)
    """
    redis_conn = get_redis_connection() # Redis 연결 가져오기
    
    # 날짜 구간 설정
    if end_date is None:
        date_range = [target_date]
    else:
        date_range = [d.strftime("%Y-%m-%d") for d in pd.date_range(start=target_date, end=end_date)]

    
    # 모든 날짜가 Redis 대상인지 확인
    all_dates_valid = all(is_redis_target_date(date) for date in date_range)
    if not redis_conn or not all_dates_valid:
        print(f"DEBUG: fetch_from_redis: Skipping as Redis conn is {bool(redis_conn)} or not all dates are target dates.")
        return pd.DataFrame()

    print(f"DEBUG: fetch_from_redis: Fetching data for date range: {date_range[0]} to {date_range[-1]} ({len(date_range)} days)")

    all_keys = []
    for date in date_range:
        stocks = get_all_stocks_for_date_from_redis(date)
        for stock in stocks:
            code = stock["code"]
            market = stock["market"]
            name = stock["name"]
            key = f"{date}:{market}:{code}:{name}"
            all_keys.append(key)

    print(f"DEBUG: fetch_from_redis: Total {len(all_keys)} keys constructed across all dates")

    
    if target_tickers:
        filtered_keys = []
        for key in all_keys:
            try:
                _, market, code, name = key.split(":", 3)
                suffix = ".KS" if market == "KOSPI" else ".KQ"
                ticker = f"{code}{suffix}"
                if ticker in target_tickers:
                    filtered_keys.append(key)
            except ValueError:
                continue
        all_keys = filtered_keys
        print(f"DEBUG: fetch_from_redis: Filtered to {len(all_keys)} keys for target tickers")
    
    if not all_keys:
        print(f"DEBUG: fetch_from_redis: No keys found after filtering. Returning empty DataFrame.")
        return pd.DataFrame()
    
    # 모든 키를 한 번의 파이프라인으로 가져오기
    print(f"DEBUG: fetch_from_redis: Attempting to fetch {len(all_keys)} keys using single pipeline.")
    pipe = redis_conn.pipeline()
    for key in all_keys:
        pipe.get(key)

    redis_results = pipe.execute()
    print(f"DEBUG: fetch_from_redis: Single pipeline executed. Got {len(redis_results)} results.")

    all_data = []
    print(f"DEBUG: fetch_from_redis: Processing {len(all_keys)} keys and {len(redis_results)} results")
    
    # 길이가 다를 경우 더 짧은 쪽에 맞춤
    min_length = min(len(all_keys), len(redis_results))
    print(f"DEBUG: fetch_from_redis: Using min_length: {min_length}")
    
    for i in range(min_length):
        try:
            key = all_keys[i]
            result_json = redis_results[i]
            
            if result_json:
                try:
                    data = json.loads(result_json)
                    parts = key.split(":", 3)
                    if len(parts) == 4:
                        current_date, market, code, name = parts
                        data['Date'] = pd.to_datetime(current_date)
                        suffix = ".KS" if market == "KOSPI" else ".KQ"
                        data['Ticker'] = f"{code}{suffix}"
                        all_data.append(data)
                    else:
                        print(f"DEBUG: fetch_from_redis: Key format mismatch (not 4 parts): '{key}'")
                        continue
                except (json.JSONDecodeError, ValueError) as e:
                    print(f"DEBUG: fetch_from_redis: Error parsing JSON or key for '{key}': {e}. Raw JSON: {result_json}")
                    continue
        except IndexError as e:
            print(f"DEBUG: fetch_from_redis: IndexError at position {i}: {e}")
            print(f"DEBUG: fetch_from_redis: all_keys length: {len(all_keys)}, redis_results length: {len(redis_results)}")
            break


    if not all_data:
        return pd.DataFrame()

    # DataFrame으로 변환하고 MultiIndex 컬럼으로 재구성 (yfinance 호환성)
    df = pd.DataFrame(all_data)
    df = df.set_index(['Date', 'Ticker'])
    df_pivoted = df.unstack(level='Ticker')

    # DataFrame이 비어있을 수 있으므로 컬럼이 있는지 확인 후 swaplevel 적용
    if not df_pivoted.empty and isinstance(df_pivoted.columns, pd.MultiIndex):
        df_pivoted.columns = df_pivoted.columns.swaplevel(0, 1)
        df_pivoted.sort_index(axis=1, level=0, inplace=True)


    return df_pivoted

def fetch_from_yfinance(tickers, start_dt, end_dt) -> pd.DataFrame:
    """yfinance API를 통해 데이터를 다운로드합니다."""
    print(f"INFO: yfinance에서 {len(tickers)}개 종목 데이터를 조회합니다. ({start_dt} ~ {end_dt})")
    return yf.download(
        tickers=tickers, start=start_dt, end=end_dt, interval="1d",
        group_by="ticker", progress=False, threads=True, auto_adjust=False,
    )

def get_historical_data(tickers: list, start_date: str, end_date: str) -> pd.DataFrame:
    """
    데이터 소스를 결정하여 특정 '기간'의 시계열 데이터를 가져오는 통합 함수.
    기간이 Redis와 yfinance에 걸쳐 있는 경우는 현재 미지원 (yfinance로 통일).

    end_date는 두 데이터 소스 모두에서 '포함(inclusive)'으로 동작합니다.
    fetch_from_redis는 pd.date_range로 end_date를 포함하지만 yfinance의 end는
    제외(exclusive)이므로, yfinance 경로에서만 하루를 더해 의미를 맞춥니다.
    """
    is_start_redis = is_redis_target_date(start_date)
    is_end_redis = is_redis_target_date(end_date)

    if is_start_redis and is_end_redis:
        print(f"INFO: Redis에서 기간 데이터를 조회합니다. ({start_date} ~ {end_date})")
        # 수정된 fetch_from_redis 함수를 사용하여 한 번에 구간 데이터를 가져옴 (티커 필터링 포함)
        combined_df = fetch_from_redis(start_date, end_date, tickers)

        if combined_df.empty:
            return pd.DataFrame()

        return combined_df
    else:
        # 기간이 걸쳐있거나, 모두 yfinance 대상인 경우 yfinance 사용
        yf_end_date = (pd.to_datetime(end_date) + timedelta(days=1)).strftime("%Y-%m-%d")
        return fetch_from_yfinance(tickers, start_date, yf_end_date)

def get_single_day_data(stock_name: str, code: str, market: str, target_date: str) -> pd.DataFrame:
    """
    데이터 소스를 결정하여 특정 '하루'의 '특정 종목' 데이터를 가져오는 통합 함수.
    등락률 계산 등을 위해 실제 조회는 며칠 더 이전부터 할 수 있습니다.
    """
    if is_redis_target_date(target_date):
        print(f"INFO: Redis에서 단일 날짜의 특정 종목 데이터를 조회합니다. ({target_date}, {stock_name})")
        # 특정 종목 데이터만 Redis에서 가져옴
        single_stock_data = fetch_single_stock_data_from_redis(stock_name, code, market, target_date)
        
        if single_stock_data:
            df = pd.DataFrame([single_stock_data])
            df['Date'] = pd.to_datetime(target_date)
            ticker_suffix = ".KS" if market.upper() == "KOSPI" else ".KQ"
            df['Ticker'] = f"{code}{ticker_suffix}"
            df = df.set_index(['Date', 'Ticker'])
            df_pivoted = df.unstack(level='Ticker')
            
            # DataFrame이 비어있지 않고 MultiIndex인지 확인 후 swaplevel 적용
            if not df_pivoted.empty and isinstance(df_pivoted.columns, pd.MultiIndex):
                df_pivoted.columns = df_pivoted.columns.swaplevel(0, 1)
                df_pivoted.sort_index(axis=1, level=0, inplace=True)
            
            print(f"DEBUG: get_single_day_data: Redis data processed for '{stock_name}'. DF shape: {df_pivoted.shape}")
            return df_pivoted
        else:
            print(f"DEBUG: get_single_day_data: No data found for '{stock_name}' from Redis on {target_date}. Falling back to yfinance (historical).")
            # Redis에 없으면 yfinance로 폴백 (기존의 yfinance 호출 방식 유지)
            tgt_date_dt = datetime.strptime(target_date, "%Y-%m-%d")
            start_dt = (tgt_date_dt - timedelta(days=7)).strftime("%Y-%m-%d") # 등락률 위해 7일치
            end_dt = (tgt_date_dt + timedelta(days=1)).strftime("%Y-%m-%d") # end 날짜는 다음날까지
            ticker_suffix = ".KS" if market.upper() == "KOSPI" else ".KQ"
            return fetch_from_yfinance([f"{code}{ticker_suffix}"], start_dt, end_dt)

    else:
        print(f"INFO: yfinance에서 단일 날짜 데이터를 조회합니다. ({target_date}, {stock_name})")
        tgt_date_dt = datetime.strptime(target_date, "%Y-%m-%d")
        start_dt = (tgt_date_dt - timedelta(days=7)).strftime("%Y-%m-%d") # 등락률 위해 7일치
        end_dt = (tgt_date_dt + timedelta(days=1)).strftime("%Y-%m-%d") # end 날짜는 다음날까지
        ticker_suffix = ".KS" if market.upper() == "KOSPI" else ".KQ"
        return fetch_from_yfinance([f"{code}{ticker_suffix}"], start_dt, end_dt)