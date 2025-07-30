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

        
def fetch_from_redis(target_date: str) -> pd.DataFrame:
    """
    특정 날짜의 모든 종목 데이터를 Redis에서 가져와 yfinance와 유사한 MultiIndex DataFrame으로 만듭니다.
    이 함수는 '전체 시장 스캔'이 필요한 경우에만 호출됩니다.
    """
    redis_conn = get_redis_connection() # Redis 연결 가져오기
    if not redis_conn or not is_redis_target_date(target_date):
        print(f"DEBUG: fetch_from_redis: Skipping as Redis conn is {bool(redis_conn)} or date {target_date} is not target date.")
        return pd.DataFrame()

    print(f"DEBUG: fetch_from_redis: Calling get_all_stocks_for_date_from_redis for date: {target_date}")
    all_stocks_meta = get_all_stocks_for_date_from_redis(target_date)

    if not all_stocks_meta:
        print(f"DEBUG: fetch_from_redis: No stock metadata found for {target_date}. Returning empty DataFrame.")
        return pd.DataFrame()

    # Redis 파이프라인을 사용하여 한 번에 모든 데이터를 효율적으로 가져옵니다.
    pipe = redis_conn.pipeline()
    keys_to_fetch = [f"{target_date}:{s['market']}:{s['code']}:{s['name']}" for s in all_stocks_meta]
    print(f"DEBUG: fetch_from_redis: Attempting to fetch {len(keys_to_fetch)} keys using pipeline.")
    for key in keys_to_fetch:
        pipe.get(key)

    redis_results = pipe.execute()
    print(f"DEBUG: fetch_from_redis: Pipeline executed. Got {len(redis_results)} results.")

    all_data = []
    for i, (key, result_json) in enumerate(zip(keys_to_fetch, redis_results)):
        if result_json:
            try:
                data = json.loads(result_json)
                _, market, code, name = key.split(":", 3) # 키는 이미 디코딩된 문자열 (decode_responses=True)
                data['Date'] = pd.to_datetime(target_date)
                suffix = ".KS" if market == "KOSPI" else ".KQ"
                data['Ticker'] = f"{code}{suffix}"
                all_data.append(data)
            except (json.JSONDecodeError, ValueError) as e:
                print(f"DEBUG: fetch_from_redis: Error parsing JSON or key for '{key}': {e}. Raw JSON: {result_json}")
                continue
        else:
            # print(f"DEBUG: fetch_from_redis: No data found for key: {key} (result_json was None/empty)")
            pass


    if not all_data:
        print(f"DEBUG: fetch_from_redis: 'all_data' list is empty after processing results. Returning empty DataFrame.")
        return pd.DataFrame()

    # DataFrame으로 변환하고 MultiIndex 컬럼으로 재구성 (yfinance 호환성)
    df = pd.DataFrame(all_data)
    print(f"DEBUG: fetch_from_redis: DataFrame created with {len(df)} rows. Columns: {df.columns.tolist()}")
    df = df.set_index(['Date', 'Ticker'])
    print(f"DEBUG: fetch_from_redis: Index set to 'Date', 'Ticker'.")
    df_pivoted = df.unstack(level='Ticker')
    print(f"DEBUG: fetch_from_redis: DataFrame unstacked.")

    # DataFrame이 비어있을 수 있으므로 컬럼이 있는지 확인 후 swaplevel 적용
    if not df_pivoted.empty and isinstance(df_pivoted.columns, pd.MultiIndex):
        df_pivoted.columns = df_pivoted.columns.swaplevel(0, 1)
        df_pivoted.sort_index(axis=1, level=0, inplace=True)
        print(f"DEBUG: fetch_from_redis: Columns swapped and sorted. Final DF shape: {df_pivoted.shape}")
    elif df_pivoted.empty:
        print(f"DEBUG: fetch_from_redis: Pivoted DataFrame is empty.")
    else:
        print(f"DEBUG: fetch_from_redis: Pivoted DataFrame is not MultiIndex, or is empty.")

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
    """
    is_start_redis = is_redis_target_date(start_date)
    is_end_redis = is_redis_target_date(end_date)

    if is_start_redis and is_end_redis:
        print(f"INFO: Redis에서 기간 데이터를 조회합니다. ({start_date} ~ {end_date})")
        date_range = pd.date_range(start=start_date, end=end_date)
        all_dfs = [fetch_from_redis(date.strftime("%Y-%m-%d")) for date in date_range]
        
        valid_dfs = [df for df in all_dfs if not df.empty]
        if not valid_dfs: return pd.DataFrame()
            
        combined_df = pd.concat(valid_dfs)
        # 요청된 티커만 필터링
        existing_tickers = [t for t in tickers if t in combined_df.columns.get_level_values(0)]
        return combined_df[existing_tickers] if existing_tickers else pd.DataFrame()
    else:
        # 기간이 걸쳐있거나, 모두 yfinance 대상인 경우 yfinance 사용
        return fetch_from_yfinance(tickers, start_date, end_date)

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