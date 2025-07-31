import pandas as pd
import json, re, ast
from datetime import datetime
from functools import lru_cache
import unicodedata
# Redis 연결 객체를 임포트합니다.
from redis_connector import get_redis_connection

# --- 데이터 소스 라우팅 로직 ---
REDIS_START_DATE = datetime(2024, 1, 1)
REDIS_END_DATE = datetime(2025, 7, 31)

def is_redis_target_date(target_date_str: str) -> bool:
    """
    주어진 날짜 문자열이 Redis 조회 대상 기간(2024-01-01 ~ 2025-07-31)에 포함되는지 확인합니다.
    """
    if not target_date_str:
        print(f"DEBUG: is_redis_target_date received empty target_date_str.")
        return False
    try:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d")
        result = REDIS_START_DATE <= target_date <= REDIS_END_DATE
        print(f"DEBUG: is_redis_target_date('{target_date_str}') = {result}")
        return result
    except (ValueError, TypeError) as e:
        print(f"DEBUG: is_redis_target_date('{target_date_str}') failed to parse date: {e}")
        return False

# --- CSV 기반 유틸리티 함수 ---
CSV_PATH = "data/krx_tickers_with_market.csv"
try:
    market_list_df = pd.read_csv(CSV_PATH)
    print(f"DEBUG: CSV file loaded successfully from {CSV_PATH}. Rows: {len(market_list_df)}")
except FileNotFoundError:
    market_list_df = pd.DataFrame(columns=['code', 'name', 'market'])
    print(f"경고: CSV 파일을 찾을 수 없습니다. ({CSV_PATH}). Fallback 기능이 제한될 수 있습니다.")
except Exception as e:
    market_list_df = pd.DataFrame(columns=['code', 'name', 'market'])
    print(f"경고: CSV 파일을 로드하는 중 오류 발생 ({CSV_PATH}): {e}. Fallback 기능이 제한될 수 있습니다.")


def name_to_ticker_from_csv(stock: str) -> str:
    normalized_stock = unicodedata.normalize('NFC', stock).strip()
    row = market_list_df[market_list_df['name'].apply(lambda x: unicodedata.normalize('NFC', str(x)).strip()) == normalized_stock]
    if row.empty:
        print(f"DEBUG: name_to_ticker_from_csv: '{stock}' (normalized: '{normalized_stock}') not found in CSV.")
        raise ValueError(f"'{stock}' not found in CSV")
    row = row.iloc[0]
    ticker = f"{str(row['code']).zfill(6)}{'.KS' if row['market'] == 'KOSPI' else '.KQ'}"
    print(f"DEBUG: name_to_ticker_from_csv: Found '{stock}' as '{ticker}'.")
    return ticker

def ticker_to_name_from_csv(ticker: str) -> str:
    code = ticker.split('.')[0]
    row = market_list_df.loc[market_list_df['code'].astype(str).str.zfill(6) == code]
    if row.empty:
        print(f"DEBUG: ticker_to_name_from_csv: '{ticker}' not found in CSV.")
        raise ValueError(f"'{ticker}' not found in CSV")
    name = unicodedata.normalize('NFC', str(row.iloc[0]['name'])).strip()
    print(f"DEBUG: ticker_to_name_from_csv: Found '{ticker}' as '{name}'.")
    return name

def name_to_market_from_csv(stock: str) -> str:
    normalized_stock = unicodedata.normalize('NFC', stock).strip()
    row = market_list_df[market_list_df['name'].apply(lambda x: unicodedata.normalize('NFC', str(x)).strip()) == normalized_stock]
    if row.empty:
        print(f"DEBUG: name_to_market_from_csv: '{stock}' (normalized: '{normalized_stock}') not found in CSV.")
        raise ValueError(f"'{stock}' not found in CSV")
    market = row.iloc[0]['market']
    print(f"DEBUG: name_to_market_from_csv: Found market '{market}' for '{stock}'.")
    return market

def get_tickers_from_csv(market: str):
    tickers = []
    target_markets = [m.upper() for m in (["KOSPI", "KOSDAQ"] if market.upper() == "ALL" else [market])]
    print(f"DEBUG: get_tickers_from_csv: Target markets: {target_markets}")
    for m in target_markets:
        codes = market_list_df.loc[market_list_df["market"] == m, "code"].tolist()
        suffix = ".KS" if m == "KOSPI" else ".KQ"
        tickers.extend([f"{str(code).zfill(6)}{suffix}" for code in codes])
    print(f"DEBUG: get_tickers_from_csv: Found {len(tickers)} tickers for market '{market}'.")
    return tickers

# --- 통합 유틸리티 함수 (데이터 소스 자동 선택) ---

def name_to_ticker(stock_name: str, target_date: str) -> str:
    """날짜를 기준으로 종목명을 티커로 변환합니다."""
    normalized_stock_name = unicodedata.normalize('NFC', stock_name).strip()

    print(f"DEBUG: name_to_ticker called with stock_name='{stock_name}' (normalized='{normalized_stock_name}'), target_date='{target_date}'")
    
    code = None
    market = None
    
    try:
        # CSV 파일의 'name' 컬럼도 정규화하여 비교
        csv_row = market_list_df[market_list_df['name'].apply(lambda x: unicodedata.normalize('NFC', str(x)).strip()) == normalized_stock_name]
        
        if csv_row.empty:
            print(f"DEBUG: CSV lookup failed for '{stock_name}': Name '{normalized_stock_name}' not found in CSV.")
            raise ValueError(f"'{stock_name}' not found in CSV.") # 명확한 ValueError 발생

        csv_row = csv_row.iloc[0]
        code = str(csv_row['code']).zfill(6)
        market = csv_row['market']
        
        redis_market_name = market.upper() 
        print(f"DEBUG: Found in CSV: code='{code}', market='{market}' for '{stock_name}'.")
        
    except ValueError as e: # 위에서 발생시킨 ValueError를 잡음
        print(f"DEBUG: Error during CSV lookup (ValueError): {e}")
        raise # 다시 예외를 발생시켜 상위 호출자에게 전달
    except IndexError as e: # .iloc[0] 실패 시 (empty 아닐 시)
        print(f"DEBUG: IndexError during CSV lookup (likely empty row for '{stock_name}'): {e}")
        raise ValueError(f"'{stock_name}' not found in CSV. IndexError: {e}")
    except Exception as e:
        print(f"DEBUG: Unexpected error during CSV lookup for '{stock_name}': {e}")
        raise ValueError(f"Error processing CSV for '{stock_name}': {e}")
    
    if is_redis_target_date(target_date):
        redis_conn = get_redis_connection()
        if not redis_conn:
            print(f"DEBUG: Redis connection not available for direct GET. Falling back to CSV.")
            return name_to_ticker_from_csv(stock_name) 

        redis_key = f"{target_date}:{redis_market_name}:{code}:{normalized_stock_name}"
        print(f"DEBUG: Attempting direct Redis GET for key: '{redis_key}'")
        
        try:
            redis_value = redis_conn.get(redis_key) 
            
            if redis_value is not None:
                suffix = ".KS" if market.upper() == "KOSPI" else ".KQ"
                print(f"DEBUG: Found '{stock_name}' in Redis with key '{redis_key}'. Returning ticker: {code}{suffix}")
                return f"{code}{suffix}"
            else:
                print(f"DEBUG: Redis key '{redis_key}' returned None (not found).")
                raise ValueError(f"'{stock_name}' not found in Redis for date {target_date}. Redis key: {redis_key}")
        except Exception as e:
            print(f"DEBUG: Error during Redis GET for key '{redis_key}': {e}")
            raise ValueError(f"Error during Redis lookup for '{stock_name}': {e}")
    else:
        print(f"DEBUG: Target date '{target_date}' not within Redis range. Falling back to CSV.")
        return name_to_ticker_from_csv(stock_name)


def ticker_to_name(ticker: str, target_date: str) -> str:
    """날짜를 기준으로 티커를 종목명으로 변환합니다."""
    code = ticker.split('.')[0].strip()
    suffix = ticker.split('.')[1].strip().upper()

    print(f"DEBUG: ticker_to_name called with ticker='{ticker}', target_date='{target_date}'")

    name = None
    market = None

    if is_redis_target_date(target_date):
        redis_conn = get_redis_connection()
        if not redis_conn:
            print(f"DEBUG: Redis connection not available for direct GET. Falling back to CSV.")
            return ticker_to_name_from_csv(ticker)

        try:
            csv_row = market_list_df.loc[market_list_df['code'].astype(str).str.zfill(6) == code].iloc[0]
            name = unicodedata.normalize('NFC', str(csv_row['name'])).strip() # 이름 정규화
            market = csv_row['market']
            redis_market_name = market.upper()

            print(f"DEBUG: Found in CSV: name='{name}', market='{market}' for code='{code}'")

        except IndexError as e:
            print(f"DEBUG: CSV lookup failed for ticker '{ticker}': {e}")
            raise ValueError(f"'{ticker}' not found in CSV or Redis for date {target_date}. CSV Error: {e}")
        except Exception as e:
            print(f"DEBUG: Unexpected error during CSV lookup for ticker: {e}")
            raise ValueError(f"Error processing CSV for '{ticker}': {e}")

        redis_key = f"{target_date}:{redis_market_name}:{code}:{name}" # name 부분 정규화된 이름 사용
        print(f"DEBUG: Attempting direct Redis GET for key: '{redis_key}'")
        try:
            redis_value = redis_conn.get(redis_key)
            
            if redis_value is not None:
                print(f"DEBUG: Found '{ticker}' in Redis with key '{redis_key}'. Returning name: {name}")
                return name
            else:
                print(f"DEBUG: Redis key '{redis_key}' returned None (not found).")
                raise ValueError(f"'{ticker}' not found in Redis for date {target_date}. Redis key: {redis_key}")
        except Exception as e:
            print(f"DEBUG: Error during Redis GET for key '{redis_key}': {e}")
            raise ValueError(f"Error during Redis lookup for '{ticker}': {e}")
    else:
        print(f"DEBUG: Target date '{target_date}' not within Redis range. Falling back to CSV.")
        return ticker_to_name_from_csv(ticker)
        

def name_to_market(stock_name: str, target_date: str) -> str:
    """날짜를 기준으로 종목명의 소속 시장을 반환합니다."""
    normalized_stock_name = unicodedata.normalize('NFC', stock_name).strip()

    print(f"DEBUG: name_to_market called with stock_name='{stock_name}' (normalized='{normalized_stock_name}'), target_date='{target_date}'")

    code = None
    market = None

    if is_redis_target_date(target_date):
        try:
            csv_row = market_list_df[market_list_df['name'].apply(lambda x: unicodedata.normalize('NFC', str(x)).strip()) == normalized_stock_name]
            
            if csv_row.empty:
                print(f"DEBUG: CSV lookup failed for '{stock_name}': Name not found in CSV.")
                raise ValueError(f"'{stock_name}' not found in CSV.")

            csv_row = csv_row.iloc[0]
            code = str(csv_row['code']).zfill(6)
            market = csv_row['market']
            redis_market_name = market.upper()

            print(f"DEBUG: Found in CSV: code='{code}', market='{market}' for '{stock_name}'.")

        except ValueError as e:
            print(f"DEBUG: Error during CSV lookup: {e}")
            raise
        except IndexError as e:
            print(f"DEBUG: IndexError during CSV lookup (likely empty row): {e}")
            raise ValueError(f"'{stock_name}' not found in CSV. IndexError: {e}")
        except Exception as e:
            print(f"DEBUG: Unexpected error during CSV lookup: {e}")
            raise ValueError(f"Error processing CSV for '{stock_name}': {e}")

        redis_conn = get_redis_connection()
        if not redis_conn:
            print(f"DEBUG: Redis connection not available for direct GET. Falling back to CSV.")
            return name_to_market_from_csv(stock_name)

        redis_key = f"{target_date}:{redis_market_name}:{code}:{normalized_stock_name}"
        print(f"DEBUG: Attempting direct Redis GET for key: '{redis_key}'")
        try:
            redis_value = redis_conn.get(redis_key)

            if redis_value is not None:
                print(f"DEBUG: Found '{stock_name}' in Redis with key '{redis_key}'. Returning market: {market}")
                return market
            else:
                print(f"DEBUG: Redis key '{redis_key}' returned None (not found).")
                raise ValueError(f"'{stock_name}' not found in Redis for date {target_date}. Redis key: {redis_key}")
        except Exception as e:
            print(f"DEBUG: Error during Redis GET for key '{redis_key}': {e}")
            raise ValueError(f"Error during Redis lookup for '{stock_name}': {e}")
    else:
        print(f"DEBUG: Target date '{target_date}' not within Redis range. Falling back to CSV.")
        return name_to_market_from_csv(stock_name)


# --- Redis 기반 유틸리티 함수 ---
@lru_cache(maxsize=128)
def get_all_stocks_for_date_from_redis(target_date: str):
    """
    특정 날짜의 모든 주식 메타데이터(코드, 이름, 시장)를 Redis에서 스캔하여 가져옵니다.
    결과는 후속 조회를 위해 캐싱됩니다.
    """
    redis_conn = get_redis_connection()
    if not redis_conn:
        print(f"DEBUG: get_all_stocks_for_date_from_redis: Redis connection not available.")
        return []
    if not is_redis_target_date(target_date):
        print(f"DEBUG: get_all_stocks_for_date_from_redis: Skipping Redis scan. Target date '{target_date}' not in Redis range.")
        return []
    
    index_key = f"date:{{{target_date}}}"
    print(f"DEBUG: get_all_stocks_for_date_from_redis: Using index key: '{index_key}'")

    try:
        keys = redis_conn.smembers(index_key)
    except Exception as e:
        print(f"ERROR: get_all_stocks_for_date_from_redis: Failed to retrieve keys from index: {e}")
        return []
    stock_list = []
    for key_str in keys:
        # print(f"DEBUG: get_all_stocks_for_date_from_redis: Found raw key: '{key_str}'") # 너무 많은 로그로 인해 주석 처리 유지
        try:
            parts = key_str.split(":", 3)
            if len(parts) == 4:
                _, market, code, name_from_key_raw = parts
                normalized_name_from_key = unicodedata.normalize('NFC', name_from_key_raw).strip()
                stock_list.append({"code": code, "name": normalized_name_from_key, "market": market})
            else:
                print(f"DEBUG: get_all_stocks_for_date_from_redis: Key format mismatch (not 4 parts): '{key_str}'")
        except Exception as e:
            print(f"DEBUG: get_all_stocks_for_date_from_redis: Error processing key '{key_str}': {e}")
            continue
    print(f"DEBUG: get_all_stocks_for_date_from_redis: Found {len(stock_list)} stocks for date {target_date}.")
    return stock_list

# --- 통합 유틸리티 함수 (get_tickers는 그대로 유지) ---
def get_tickers(market: str, target_date: str, end_date: str = None):
    """
    날짜를 기준으로 데이터 소스를 선택하여 특정 시장의 모든 티커를 반환합니다.
    
    Args:
        market (str): 시장 구분 ("KOSPI", "KOSDAQ", "ALL")
        target_date (str): 시작 날짜 (YYYY-MM-DD)
        end_date (str, optional): 종료 날짜 (YYYY-MM-DD). None이면 target_date만 사용
    """
    print(f"DEBUG: get_tickers called with market='{market}', target_date='{target_date}', end_date='{end_date}'.")
    
    # 기간이 지정된 경우 (end_date가 제공된 경우)
    if end_date:
        print(f"DEBUG: get_tickers: Period mode - from {target_date} to {end_date}")
        
        # 기간 내 모든 날짜에 대해 티커를 수집
        all_tickers = set()
        current_date = datetime.strptime(target_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        
        while current_date <= end_dt:
            current_date_str = current_date.strftime("%Y-%m-%d")
            
            if is_redis_target_date(current_date_str):
                # Redis에서 해당 날짜의 티커 가져오기
                all_stocks = get_all_stocks_for_date_from_redis(current_date_str)
                target_markets = [m.upper() for m in (["KOSPI", "KOSDAQ"] if market.upper() == "ALL" else [market])]
                
                for stock in all_stocks:
                    if stock['market'].upper() in target_markets:
                        suffix = ".KS" if stock['market'].upper() == "KOSPI" else ".KQ"
                        all_tickers.add(f"{stock['code']}{suffix}")
            else:
                # CSV에서 티커 가져오기 (한 번만)
                if not all_tickers:  # 아직 티커가 없으면 CSV에서 가져오기
                    csv_tickers = get_tickers_from_csv(market)
                    all_tickers.update(csv_tickers)
            
            current_date += timedelta(days=1)
        
        tickers = list(all_tickers)
        print(f"DEBUG: get_tickers: Period mode - Returning {len(tickers)} unique tickers for period {target_date} to {end_date}")
        return tickers
    
    # 단일 날짜 모드 (기존 로직)
    else:
        if is_redis_target_date(target_date):
            all_stocks = get_all_stocks_for_date_from_redis(target_date)
            tickers = []
            target_markets = [m.upper() for m in (["KOSPI", "KOSDAQ"] if market.upper() == "ALL" else [market])]
            print(f"DEBUG: get_tickers: Filtering {len(all_stocks)} stocks for target markets: {target_markets}.")
            for stock in all_stocks:
                if stock['market'].upper() in target_markets:
                    suffix = ".KS" if stock['market'].upper() == "KOSPI" else ".KQ"
                    tickers.append(f"{stock['code']}{suffix}")
            print(f"DEBUG: get_tickers: Returning {len(tickers)} tickers from Redis for market '{market}'.")
            return tickers
        else:
            print(f"DEBUG: get_tickers: Target date '{target_date}' not within Redis range. Falling back to CSV.")
            return get_tickers_from_csv(market)

# --- JSON 파싱 함수 ---
def parse_llm_json(text: str) -> dict:
    m = re.search(r'\{.*\}', text, re.S)
    if not m: raise ValueError("JSON 블록을 찾을 수 없습니다.")
    j = m.group()
    try:
        return json.loads(j)
    except json.JSONDecodeError:
        try:
            return ast.literal_eval(j)
        except (ValueError, SyntaxError):
            raise ValueError("LLM 응답에서 유효한 JSON을 파싱할 수 없습니다.")