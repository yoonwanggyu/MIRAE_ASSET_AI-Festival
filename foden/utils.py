import pandas as pd
import json, re, ast

"""
Task1 / Task2 / Task3 공통으로 사용되는 함수 정리 
"""

# 티커 / 종목명 / 시장 정리한 파일
market_list = pd.read_csv("/Users/yoon/MIRAE_ASSET_AI-Festival/krx_tickers_cleaned.csv")

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