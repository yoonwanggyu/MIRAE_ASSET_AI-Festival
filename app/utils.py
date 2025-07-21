import pandas as pd
import yaml
import json
import ast
import re
from datetime import datetime, timedelta
from functools import lru_cache

import pandas_market_calendars as mcal


# 티커 정보 캐싱
@lru_cache(maxsize=1)
def _load_krx_tickers() -> pd.DataFrame:
    """
    KRX 종목 정보 CSV 파일을 읽어 DataFrame으로 반환합니다.
    @lru_cache 데코레이터에 의해 이 함수는 최초 호출 시 단 한 번만 실행됩니다.
    """
    try:
        # 설정 파일에서 경로를 읽어옵니다.
        with open("config.yaml", 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        csv_path = config['file_paths']['krx_tickers']
        print(f"KRX ticker list loaded from: {csv_path}")
        return pd.read_csv(csv_path, dtype={'code': str})
    except Exception as e:
        raise ValueError(f"KRX 종목 목록 파일을 로드할 수 없습니다. config.yaml을 확인하세요. 오류: {e}")

def name_to_ticker(stock_name: str) -> str | None:
    """한글 종목명을 티커 코드로 변환합니다. (캐시된 데이터 사용)"""
    df = _load_krx_tickers()
    name_std = stock_name.strip()
    row = df.loc[df["name"] == name_std]
    if row.empty:
        return None
    
    code = row["code"].iloc[0]
    suffix = ".KS" if row["market"].iloc[0] == "KOSPI" else ".KQ"
    return f"{code}{suffix}"

def ticker_to_name(ticker: str) -> str | None:
    """티커 코드를 한글 종목명으로 변환합니다. (캐시된 데이터 사용)"""
    df = _load_krx_tickers()
    code = ticker.split(".")[0]
    row = df.loc[df["code"] == code]
    return row["name"].iloc[0] if not row.empty else None


# 날짜 처리 함수
def parse_date_string(date_str: str | None) -> str:
    """
    다양한 형식의 날짜 문자열을 'YYYY-MM-DD' 표준 형식으로 변환합니다.
    요일 등 추가 정보는 붙이지 않고, 순수한 날짜 문자열만 반환합니다.
    """
    if not date_str or str(date_str).strip() == "":
        return datetime.today().strftime("%Y-%m-%d")

    s = str(date_str).strip()
    today = datetime.today()

    # 상대 표현 처리 ('오늘', '어제' 등)
    rel_map = {"오늘": 0, "어제": -1, "그제": -2, "지난주": -7}
    for word, days in rel_map.items():
        if word in s:
            return (today + timedelta(days=days)).strftime("%Y-%m-%d")
    
    m = re.fullmatch(r"(\d+)일\s?전", s)
    if m:
        return (today - timedelta(days=int(m.group(1)))).strftime("%Y-%m-%d")

    # 절대 날짜 처리 (YYYYMMDD, YYYY-MM-DD, M/D 등)
    try:
        # pandas.to_datetime이 대부분의 형식을 똑똑하게 처리해 줌
        return pd.to_datetime(s).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        raise ValueError(f"지원하지 않는 날짜 형식입니다: {date_str}")

@lru_cache(maxsize=128)
def get_latest_trading_day(date_str: str = "오늘") -> str:
    """
    입력된 날짜를 기준으로, 같거나 그 이전의 가장 가까운 실제 '거래일'을 반환합니다.
    주말이나 공휴일에 '오늘'을 입력하면 직전 거래일(예: 금요일)을 반환합니다.
    """
    try:
        base_date = pd.to_datetime(parse_date_string(date_str))
        krx_calendar = mcal.get_calendar('KRX')
        
        # 기준일로부터 과거 10일간의 스케줄 조회
        schedule = krx_calendar.schedule(start_date=base_date - timedelta(days=10), end_date=base_date)
        
        if schedule.empty:
            raise ValueError("최근 거래일을 찾을 수 없습니다.")
            
        # 스케줄의 마지막 날짜가 가장 최근 거래일
        return schedule.index[-1].strftime('%Y-%m-%d')
    except Exception as e:
        # lru_cache를 사용하므로, 오류 발생 시 캐싱되지 않도록 예외를 발생시키는 것이 좋음
        raise ValueError(f"거래일 변환 중 오류: {e}")


# task2에서 활용
def parse_llm_json(text: str) -> dict:
    """
    LLM이 응답한 텍스트에서 JSON 블록({...})을 안전하게 추출하여 dict로 변환합니다.
    """
    # re.DOTALL 플래그를 사용하여 여러 줄에 걸친 JSON도 처리
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if not match:
        raise ValueError("텍스트에서 JSON 블록을 찾을 수 없습니다.")
    
    json_str = match.group()
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        # JSON 파싱 실패 시, 파이썬 리터럴 구문으로 평가하는 fallback
        try:
            return ast.literal_eval(json_str)
        except (ValueError, SyntaxError):
            raise ValueError("JSON 또는 Python dict 형식으로 변환할 수 없습니다.")