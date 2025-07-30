import pandas as pd
import json, re, ast

"""
Task1 / Task2 / Task3 공통으로 사용되는 함수 정리 
"""

# 티커 / 종목명 / 시장 정리한 파일
market_list = pd.read_csv("/Users/yoon/MIRAE_ASSET_AI-Festival/foden/data/krx_tickers_cleaned.csv")

def name_to_ticker(stock: str) -> str:
    """
    종목명(stock)과 market_list DataFrame을 받아 티커(str)를 반환하는 함수

    Args:
        stock (str): 종목명
        market_list (pd.DataFrame): ['name', 'code', 'market'] 컬럼 포함

    Returns:
        str: 티커 ('005930.KS' 또는 '035720.KQ' 등)
    """
    market_list = pd.read_csv("/Users/yoon/MIRAE_ASSET_AI-Festival/foden/data/krx_tickers_cleaned.csv")
    row = market_list.loc[market_list['name'] == stock]
    if row.empty:
        raise ValueError(f"'{stock}' not found in market_list")
    row = row.iloc[0]
    ticker = f"{str(row['code']).zfill(6)}{'.KS' if row['market'] == 'KOSPI' else '.KQ'}"
    return ticker

def ticker_to_name(ticker: str) -> str:
    """
    티커(예: '005930.KS' 또는 '005930')를 종목명으로 반환하는 함수
    """
    market_list = pd.read_csv("/Users/yoon/MIRAE_ASSET_AI-Festival/foden/data/krx_tickers_cleaned.csv")
    # 숫자 6자리 추출
    code = ticker.split('.')[0]
    # code 컬럼은 str로 변환 후 zfill(6) 보정
    row = market_list.loc[market_list['code'].astype(str).str.zfill(6) == code]
    if row.empty:
        raise ValueError(f"'{ticker}' not found in market_list")
    return row.iloc[0]['name']

def name_to_market(stock: str) -> str:
    """
    종목명(stock)에 해당하는 시장(KOSPI, KOSDAQ 등)을 반환하는 함수

    Args:
        stock (str): 종목명
        market_list (pd.DataFrame): ['name', 'market'] 컬럼 포함

    Returns:
        str: 시장명 ('KOSPI' 또는 'KOSDAQ' 등)
    """
    market_list = pd.read_csv("/Users/yoon/MIRAE_ASSET_AI-Festival/foden/data/krx_tickers_cleaned.csv")
    row = market_list.loc[market_list['name'] == stock]
    if row.empty:
        raise ValueError(f"'{stock}' not found in market_list")
    row = row.iloc[0]
    return row['market']
    
def get_tickers(market):
    """
    특정 시장에 있는 모든 티커들을 불러오는 함수
    """
    if market == "KOSPI":
        ticker_lists = market_list.loc[market_list["market"] == "KOSPI", "code"].tolist()
        ticker_lists = [f"{ticker}.KS" for ticker in ticker_lists]
        return ticker_lists
    elif market == "KOSDAQ":
        ticker_lists = market_list.loc[market_list["market"] == "KOSDAQ", "code"].tolist()
        ticker_lists = [f"{ticker}.KQ" for ticker in ticker_lists]
        return ticker_lists
    else:
        kospi_tickers = market_list.loc[market_list["market"] == "KOSPI", "code"].tolist()
        kosdaq_tickers = market_list.loc[market_list["market"] == "KOSDAQ", "code"].tolist()
        ticker_lists = [f"{ticker}.KS" for ticker in kospi_tickers] + \
                      [f"{ticker}.KQ" for ticker in kosdaq_tickers]
        return ticker_lists
    
def parse_llm_json(text: str) -> dict:
    """
    LLM이 질문을 각 Task에 맞게 분석한 JSON을 정리하는 함수
    """
    m = re.search(r'\{.*\}', text, re.S)
    if not m:
        raise ValueError("JSON 블록을 찾을 수 없습니다.")
    j = m.group()

    try:
        return json.loads(j)
    except json.JSONDecodeError:
        return ast.literal_eval(j)  