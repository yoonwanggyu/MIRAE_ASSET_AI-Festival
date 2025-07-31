# task5_tools.py - 투자 판단 분석 도구
from utils import *
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf
import requests
from typing import Dict, Any, List, Tuple, Optional
import concurrent.futures
import numpy as np
import time
import random
import json
import asyncio
import dart_fss


# =============================================================================
# Task5 Function Definitions for Function Calling
# =============================================================================

task5_functions = [
    {
        "name": "get_info_stock",
        "description": "자연어 질문에서 종목명을 추출하고 종목 코드 및 티커 정보를 반환합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_query": {
                    "type": "string",
                    "description": "사용자가 입력한 자연어 질문 (예: 삼성전자 지금 사도 될까?)"
                }
            },
            "required": ["user_query"] 
        }
    },
    {
        "name": "get_yfinance_data",
        "description": "Yahoo Finance API를 통해 기업의 시세, 재무제표, 애널리스트 의견, 뉴스 등을 수집합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Yahoo Finance 티커 코드 (예: '005930.KS', 'AAPL')"
                },
                "data_types": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["price_data", "financial_statements", "analyst_info", "news"]
                    },
                    "default": ["price_data", "financial_statements", "analyst_info", "news"],
                    "description": "수집할 데이터 유형 선택"
                },
                "period": {
                    "type": "string",
                    "enum": ["1mo", "3mo", "6mo", "1y", "2y"],
                    "default": "1y",
                    "description": "주가 데이터 수집 기간"
                }
            },
            "required": ["ticker"]
        }
    },
    {
        "name": "get_dart_disclosure_data",
        "description": "DART 전자공시시스템에서 기업의 재무제표, 감사보고서, 공시 정보 등을 수집합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "corp_name": {
                    "type": "string",  
                    "description": "기업명 (예: 삼성전자, 카카오)"
                },
                "corp_code": {
                    "type": "string",
                    "description": "DART 기업 코드 (8자리)"
                },
                "data_types": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["company_info", "financial_summary", "audit_report", "major_shareholders", "dividends", "employees", "shareholders"]
                    },
                    "default": ["financial_summary"],
                    "description": "수집할 공시 데이터 유형"
                },
                "bsns_year": {
                    "type": "string",
                    "default": "2023",
                    "description": "사업연도 (YYYY 형식)"
                },
                "reprt_code": {
                    "type": "string",
                    "enum": ["11013", "11012", "11014", "11011"],
                    "default": "11011",
                    "description": "보고서 코드: 11011(사업보고서), 11012(반기보고서), 11013(1분기보고서), 11014(3분기보고서)"
                }
            },
            "required": ["corp_name", "corp_code"]
        }
    },
    {
        "name": "calculate_roe_peg",
        "description": "Yahoo Finance 데이터를 기반으로 ROE(자기자본이익률)와 PEG(Price/Earnings to Growth) 비율을 계산합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "fin_data": {
                    "type": "object",
                    "description": "Yahoo Finance에서 수집한 재무 데이터"
                }
            },
            "required": ["fin_data"]
        }
    },
    {
        "name": "format_growth_prompt",
        "description": "성장성 분석 데이터를 바탕으로 HCX-005 모델을 통해 투자 성장성을 분석하고 결과를 반환합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "fin_data": {
                    "type": "object",
                    "description": "시가총액, PER, PBR, EPS, 배당률 등 주요지표 dict"
                },
                "income_stmt": {
                    "type": "object",
                    "description": "손익계산서 등 재무 데이터 (선택사항)"
                },
                "news_list": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "관련 뉴스 요약문 리스트 (선택사항)"
                },
                "roe": {
                    "type": "number",
                    "description": "자기자본이익률 (선택사항)"
                },
                "peg": {
                    "type": "number", 
                    "description": "PEG 비율 (선택사항)"
                }
            },
            "required": ["fin_data"]
        }
    },
    {
        "name": "format_financial_safety_prompt",
        "description": "DART 공시 데이터를 바탕으로 HCX-005 모델을 통해 재무건전성을 분석하고 결과를 반환합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "dart_data": {
                    "type": "object",
                    "description": "DART에서 수집한 공시 데이터 (get_dart_disclosure_data 결과의 data 부분)"
                }
            },
            "required": ["dart_data"]
        }
    },
    {
        "name": "generate_investment_prompt_summary",
        "description": "재무건전성과 성장성 분석 결과를 종합하여 HCX-005 모델을 통해 최종 투자 판단을 수행하고 결과를 반환합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "safety_summary": {
                    "type": "string",
                    "description": "format_financial_safety_prompt() 결과 (선택사항)"
                },
                "growth_summary": {
                    "type": "string",
                    "description": "format_growth_prompt() 결과 (선택사항)"
                },
                "ticker": {
                    "type": "string",
                    "description": "티커 심볼 (선택사항)"
                },
                "stock_name": {
                    "type": "string",
                    "description": "종목명 (선택사항)"
                },
                "base_date": {
                    "type": "string",
                    "description": "기준일 (선택사항)"
                }
            },
            "required": []
        }
    },
    {
        "name": "analyze_investment_comprehensive",
        "description": "사용자 질문을 받아 종목 추출부터 최종 투자 판단까지 전체 분석 과정을 자동으로 실행하는 통합 함수입니다. 가장 효율적인 분석 방법입니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "user_query": {
                    "type": "string",
                    "description": "사용자가 입력한 투자 관련 질문 (예: 삼성전자 지금 사도 될까?)"
                }
            },
            "required": ["user_query"]
        }
    }
]

# =============================================================================
# 1. 종목 정보 추출 모듈
# =============================================================================


def get_info_stock(user_query: str, csv_path=r"data\krx_tickers_with_market.csv"):
    """
    사용자 질문에서 종목명을 추출하고 티커 및 기업코드 반환
    """
    df = pd.read_csv(csv_path)
    query = user_query.strip()

    # 종목명 후보 리스트
    known_names = df["name"].tolist()

    # 종목명 추출
    stock_name = None
    for name in known_names:
        if name in query:
            stock_name = name
            break

    if stock_name is None:
        return {"error": "질문에서 종목명을 추출할 수 없습니다."}

    # 티커/기업코드 조회
    row = df.loc[df["name"] == stock_name].iloc[0]
    ticker_raw = row["code"]
    ticker = name_to_ticker(ticker_raw)
    corp_code = row["corp_code"]

    return {
        "stock_name": stock_name,
        "ticker": ticker,
        "corp_code": corp_code,
        "original_query": user_query
    }

# =============================================================================
# 2. 성장성 데이터 수집 & 처리 모듈 (Yahoo Finance)
# =============================================================================

def get_yfinance_data(ticker: str, data_types: List[str] = None, period: str = "1y") -> Dict[str, Any]:
    """
    Yahoo Finance에서 종합 데이터 수집
    """
    if data_types is None:
        data_types = ["price_data", "financial_statements", "analyst_info", "news"]
    
    try:
        stock = yf.Ticker(ticker)
        result = {"ticker": ticker, "data": {}}
        
        # 기본 정보
        result["data"]["info"] = stock.info
        
        # 가격 데이터
        if "price_data" in data_types:
            result["data"]["price_data"] = {
                "current_price": stock.info.get("currentPrice"),
                "previous_close": stock.info.get("previousClose"),
                "day_high": stock.info.get("dayHigh"),
                "day_low": stock.info.get("dayLow"),
                "52_week_high": stock.info.get("fiftyTwoWeekHigh"),
                "52_week_low": stock.info.get("fiftyTwoWeekLow"),
                "market_cap": stock.info.get("marketCap"),
                "volume": stock.info.get("volume"),
                "avg_volume": stock.info.get("averageVolume")
            }
            
            # 주가 히스토리
            hist = stock.history(period=period)
            result["data"]["price_history"] = hist.to_dict()
        
        # 재무제표
        if "financial_statements" in data_types:
            result["data"]["financials"] = {
                "income_statement": stock.financials.to_dict() if not stock.financials.empty else {},
                "balance_sheet": stock.balance_sheet.to_dict() if not stock.balance_sheet.empty else {},
                "cash_flow": stock.cashflow.to_dict() if not stock.cashflow.empty else {}
            }
        
        # 애널리스트 정보
        if "analyst_info" in data_types:
            result["data"]["analyst_info"] = {
                "recommendations": stock.recommendations.to_dict() if stock.recommendations is not None else {},
                "target_price": stock.info.get("targetMeanPrice"),
                "recommendation_key": stock.info.get("recommendationKey"),
                "number_of_analysts": stock.info.get("numberOfAnalystOpinions")
            }
        
        # 뉴스
        if "news" in data_types:
            news = stock.news[:5]  # 최근 5개 뉴스만
            result["data"]["news"] = [
                {
                    "title": item.get("title"),
                    "publisher": item.get("publisher"),
                    "published_at": datetime.fromtimestamp(item.get("providerPublishTime", 0)).strftime("%Y-%m-%d %H:%M"),
                    "url": item.get("link")
                } for item in news
            ]
        
        return {"status": "success", "data": result}
        
    except Exception as e:
        return {
            "status": "error", 
            "message": f"Yahoo Finance 데이터 수집 오류: {str(e)}"
        }

def calculate_roe_peg(fin_data: Dict[str, Any]) -> Dict[str, str]:
    """
    ROE 및 PEG 계산 (Yahoo Finance 기반 재무제표 및 애널리스트 데이터 사용)
    """
    summary = {}

    try:
        # 1. ROE 계산: ROE = Net Income / Total Equity * 100
        income_stmt = fin_data.get("financials", {}).get("income_statement", {})
        balance_sheet = fin_data.get("financials", {}).get("balance_sheet", {})
        
        net_income_val = None
        total_equity_val = None

        if income_stmt.get("Net Income"):
            # 가장 최근 날짜 값 사용
            net_income_val = list(income_stmt["Net Income"].values())[0]  # dict[str, float]
        if balance_sheet.get("Total Stockholder Equity"):
            total_equity_val = list(balance_sheet["Total Stockholder Equity"].values())[0]

        if isinstance(net_income_val, (int, float)) and isinstance(total_equity_val, (int, float)) and total_equity_val != 0:
            roe = (net_income_val / total_equity_val) * 100
            summary["ROE"] = f"{roe:.2f}%"
        else:
            summary["ROE"] = "N/A"

        # 2. PEG 계산: PEG = PER / EPS Growth Rate
        per = fin_data.get("info", {}).get("trailingPE")  # 또는 forwardPE
        eps_growth = fin_data.get("info", {}).get("earningsGrowth")  # ex: 0.15 (15%)

        if isinstance(per, (int, float)) and isinstance(eps_growth, (int, float)) and eps_growth != 0:
            peg = per / (eps_growth * 100)  # % 기준으로 나누기
            summary["PEG"] = f"{peg:.2f}"
        else:
            summary["PEG"] = "N/A"

    except Exception as e:
        summary["ROE"] = "N/A"
        summary["PEG"] = "N/A"

    return summary

def format_growth_prompt(fin_data: Dict[str, Any], 
                        income_stmt: Optional[Dict[str, Any]]=None, 
                        news_list: Optional[List[str]]=None,
                        roe=None, 
                        peg=None) -> Dict[str, Any]:
    """
    성장성 분석에 필요한 주요 데이터를 바탕으로 LLM 분석을 실행하고 결과를 반환
    """
    try:
        roe_peg_summary = calculate_roe_peg(fin_data)
        roe = roe_peg_summary.get("ROE", "N/A")
        peg = roe_peg_summary.get("PEG", "N/A")

        # 데이터 섹션 구성
        data_section = []
        data_section.append("■ 성장성 주요 지표 요약")
        
        info = fin_data.get("info", {})
        if info.get("currentPrice"): 
            data_section.append(f"- 현재가: {info['currentPrice']:,.0f}")
        if info.get("marketCap"): 
            data_section.append(f"- 시가총액: {info['marketCap']/1e12:.2f}조")
        if info.get("trailingPE"): 
            data_section.append(f"- PER: {info['trailingPE']:.2f}")
        if info.get("priceToBook"): 
            data_section.append(f"- PBR: {info['priceToBook']:.2f}")
        if info.get("trailingEps"): 
            data_section.append(f"- EPS: {info['trailingEps']:,.0f}")
        if info.get("dividendYield"): 
            data_section.append(f"- 배당수익률: {info['dividendYield']*100:.2f}%")
        if info.get("recommendationKey"): 
            data_section.append(f"- 애널리스트 평균 등급: {info['recommendationKey']}")
        if info.get("targetMeanPrice"): 
            data_section.append(f"- 애널리스트 목표가: {info['targetMeanPrice']:,.0f}")
        
        data_section.append(f"- ROE(자기자본이익률): {roe}")
        data_section.append(f"- PEG(성장반영 PER): {peg}")

        # 재무 성과 추가
        if income_stmt:
            rev = income_stmt.get("매출액") or income_stmt.get("Revenue")
            op_profit = income_stmt.get("영업이익") or income_stmt.get("Operating Income")
            net_profit = income_stmt.get("당기순이익") or income_stmt.get("Net Income")
            year = income_stmt.get("연도", "")
            if rev or op_profit or net_profit:
                data_section.append("\n■ 최근 재무 성과")
                if year: data_section.append(f"- 연도: {year}")
                if rev: data_section.append(f"- 매출액: {rev}")
                if op_profit: data_section.append(f"- 영업이익: {op_profit}")
                if net_profit: data_section.append(f"- 순이익: {net_profit}")

        # 뉴스 추가
        if news_list:
            data_section.append("\n■ 최근 시장 뉴스 요약")
            for news in news_list[:3]:
                data_section.append(f"- {news}")

        # LLM 프롬프트 구성
        analysis_prompt = f"""
당신은 전문 투자 분석가입니다. 아래 데이터를 바탕으로 해당 기업의 성장성을 분석하고 투자 매력도를 평가해주세요.

{chr(10).join(data_section)}

■ 분석 요청사항:
1. 밸류에이션 분석: PER, PBR이 업계 대비 저평가/적정/고평가인지 판단
2. 수익성 분석: ROE, 애널리스트 등급 등을 통한 수익성 평가
3. 성장성 평가: EPS 성장률, PEG 등을 통한 성장 가능성 분석
4. 시장 전망: 뉴스와 애널리스트 목표가를 바탕으로 한 시장 기대감 분석

■ 답변 형식:
- 각 분석 항목별로 구체적인 수치를 제시하며 설명
- 투자 매력도를 5점 만점으로 평가
- 투자 시 주의사항이나 리스크 요인 언급
- 결론적으로 현 시점 투자 추천 여부 명시

위 요구사항에 따라 객관적이고 전문적인 분석 결과를 한국어로 제공해주세요.
"""

        # HCX API 호출
        data = {
            "model": "HCX-005",
            "messages": [
                {"role": "system", "content": "당신은 전문 금융 투자 분석가입니다. 주어진 데이터를 바탕으로 정확하고 객관적인 투자 분석을 제공합니다."},
                {"role": "user", "content": analysis_prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 2000
        }

        response = requests.post(url, headers=headers, json=data)
        result = response.json()
        
        analysis_result = result.get('result', {}).get('message', {}).get('content', '')
        
        return {
            "status": "success",
            "analysis_type": "growth_analysis",
            "analysis_result": analysis_result,
            "raw_data": data_section,
            "prompt_used": analysis_prompt
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"성장성 분석 중 오류 발생: {str(e)}"
        }




# =============================================================================
# 3. 재무건전성 평가 (DART API) 데이터 수집 & 처리 모듈
# =============================================================================

from typing import List, Dict, Any
import pandas as pd
import dart_fss

def get_dart_disclosure_data(corp_name: str, corp_code: str,
                              data_types: List[str] = None,
                              bsns_year: str = "2023",
                              reprt_code: str = "11011") -> Dict[str, Any]:
    """
    DART 전자공시 Open API를 활용해 기업 정보, 재무제표, 감사보고서 등 수집
    """
    if data_types is None:
        data_types = ["company_info", "financial_summary", "audit_report"]

    try:
        # API 키 설정
        api_key = '0778fdc977a04c6bc0516326fe22cea0224b233b'
        dart_fss.set_api_key(api_key)
        
        result = {"corp_name": corp_name, "corp_code": corp_code, "data": {}}

        # 1. 기업 개요
        if "company_info" in data_types:
            info = dart_fss.api.filings.get_corp_info(corp_code)
            result["data"]["company_info"] = info

        # 2. 재무제표 요약
        if "financial_summary" in data_types:
            fin = dart_fss.api.finance.fnltt_singl_acnt(corp_code, bsns_year, reprt_code)
            result["data"]["financial_summary"] = pd.DataFrame(fin['list']) if 'list' in fin else {}
    
        # 3. 상세 재무정보
        # Dart API를 사용해보기(상장기업 재무정보)

            all = dart_fss.api.filings.get_corp_code()
            all[0]

            df = pd.DataFrame(all)

            df_listed = df[df['stock_code'].notnull()]
            df_non_listed = df[df['stock_code'].isnull()]

            corp_code = df_listed[df_listed['corp_name'] == '카카오'].iloc[0,0]
            data = dart_fss.api.finance.fnltt_singl_acnt(corp_code, '2021', '11011')

            pd.DataFrame(data['list'])

        return {"status": "success", "data": result}

    except Exception as e:
        return {
            "status": "error",
            "message": f"DART 데이터 수집 오류: {str(e)}"
        }


def format_financial_safety_prompt(dart_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    DART 재무 데이터를 바탕으로 LLM 재무건전성 분석을 실행하고 결과를 반환
    """
    try:
        data_section = ["■ 재무 건전성 분석 요약"]
        
        fin_df = dart_data.get("financial_summary", pd.DataFrame())
        if not isinstance(fin_df, pd.DataFrame) or fin_df.empty:
            data_section.append("- 재무제표 요약 데이터가 없습니다.")
        else:
            df = fin_df.copy()
            # 금액을 숫자 타입으로 변환
            for col in ["thstrm_amount", "frmtrm_amount"]:
                df[col] = (
                    df[col]
                    .astype(str)
                    .str.replace(",", "")
                    .replace("", "0")
                    .astype(float)
                )

            def get_amt(name):
                sub = df.loc[df["account_nm"] == name, "thstrm_amount"]
                return sub.iloc[0] if len(sub) > 0 else None

            asset = get_amt("자산총계")
            debt = get_amt("부채총계")
            equity = get_amt("자본총계")
            op_profit = get_amt("영업이익")
            interest = get_amt("이자비용")
            net_income = get_amt("당기순이익")

            # 주요 계정 추가
            for name, val in [
                ("자산총계", asset),
                ("부채총계", debt),
                ("자본총계", equity),
                ("영업이익", op_profit),
                ("이자비용", interest),
                ("당기순이익", net_income),
            ]:
                if val is not None:
                    data_section.append(f"- {name}: {int(val):,} 원")

            # 비율 계산 및 추가
            if asset and debt:
                cur_asset = get_amt("유동자산")
                cur_debt = get_amt("유동부채")
                if cur_asset and cur_debt:
                    data_section.append(f"- 유동비율: {cur_asset/cur_debt*100:.1f}%")
            if equity and debt:
                data_section.append(f"- 부채비율: {debt/equity*100:.1f}%")
                data_section.append(f"- 차입금의존도: {debt/asset*100:.1f}%")
            if op_profit and interest and interest != 0:
                data_section.append(f"- 이자보상배율: {op_profit/interest:.1f}")

        # LLM 프롬프트 구성
        analysis_prompt = f"""
당신은 전문 재무 분석가입니다. 아래 DART 공시 데이터를 바탕으로 해당 기업의 재무건전성을 종합 평가해주세요.

{chr(10).join(data_section)}

■ 분석 기준 및 요청사항:
1. 유동성 분석: 유동비율(100% 이상 양호)을 통한 단기 지급능력 평가
2. 안정성 분석: 부채비율(200% 이하 양호), 차입금의존도(30% 이하 양호) 평가
3. 수익성 분석: 영업이익, 당기순이익의 흑자/적자 지속성 평가
4. 이자보상능력: 이자보상배율(1배 이상 양호)을 통한 이자 지급능력 평가

■ 답변 형식:
- 각 재무비율별로 우수/보통/미흡 등급 제시
- 재무건전성을 5점 만점으로 종합 평가
- 투자 시 주의해야 할 재무 리스크 요인 구체적 언급
- 결론적으로 재무적 관점에서의 투자 안전성 평가

위 요구사항에 따라 객관적이고 전문적인 재무건전성 분석 결과를 한국어로 제공해주세요.
"""

        # HCX API 호출
        data = {
            "model": "HCX-005",
            "messages": [
                {"role": "system", "content": "당신은 전문 재무 분석가입니다. DART 공시 데이터를 바탕으로 정확한 재무건전성 분석을 제공합니다."},
                {"role": "user", "content": analysis_prompt}
            ],
            "temperature": 0.3,
            "max_tokens": 2000
        }

        response = requests.post(url, headers=headers, json=data)
        result = response.json()
        
        analysis_result = result.get('result', {}).get('message', {}).get('content', '')
        
        return {
            "status": "success",
            "analysis_type": "safety_analysis",
            "analysis_result": analysis_result,
            "raw_data": data_section,
            "prompt_used": analysis_prompt
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"재무건전성 분석 중 오류 발생: {str(e)}"
        }


def generate_investment_prompt_summary(
    safety_summary: Optional[str] = None,
    growth_summary: Optional[str] = None,
    ticker: Optional[str] = None,
    stock_name: Optional[str] = None,
    base_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    재무건전성과 성장성 분석 결과를 종합하여 최종 투자 판단을 LLM으로 수행
    """
    try:
        # 분석 결과 텍스트 추출
        safety_text = ""
        growth_text = ""
        
        if isinstance(safety_summary, dict):
            safety_text = safety_summary.get("analysis_result", str(safety_summary))
        else:
            safety_text = str(safety_summary) if safety_summary else ""
            
        if isinstance(growth_summary, dict):
            growth_text = growth_summary.get("analysis_result", str(growth_summary))
        else:
            growth_text = str(growth_summary) if growth_summary else ""

        # 최종 종합 분석 프롬프트 구성
        final_prompt = f"""
[종합 투자 분석] 📈 종목: {stock_name} ({ticker}) 📅 기준일: {base_date or datetime.now().strftime('%Y-%m-%d')}

■ 재무건전성 분석 결과:
{safety_text}

■ 성장성 분석 결과:
{growth_text}

■ 최종 종합 투자 판단 요청:
위의 재무건전성과 성장성 분석 결과를 종합하여 다음 사항을 평가해주세요:

1. 투자 매력도 종합 점수 (10점 만점)
2. 투자 추천 등급 (매수/보유/매도 중 선택)
3. 예상 목표 주가 및 기대 수익률 제시
4. 투자 시 주요 리스크 요인 3가지
5. 투자 적정 기간 (단기/중기/장기) 추천

■ 답변 형식:
- 각 항목별로 구체적인 근거와 함께 명확한 결론 제시
- 정량적 지표와 정성적 판단을 균형있게 반영
- 투자자 유형별(보수적/공격적) 추천사항 구분 제시

전문 투자 분석가로서 객관적이고 실용적인 최종 투자 의견을 한국어로 제공해주세요.
"""

        # HCX API 호출
        data = {
            "model": "HCX-005",
            "messages": [
                {"role": "system", "content": "당신은 종합 투자 분석 전문가입니다. 재무건전성과 성장성 분석을 바탕으로 최종 투자 판단을 제공합니다."},
                {"role": "user", "content": final_prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 3000
        }

        response = requests.post(url, headers=headers, json=data)
        result = response.json()
        
        final_analysis = result.get('result', {}).get('message', {}).get('content', '')
        
        return {
            "status": "success",
            "analysis_type": "final_investment_decision",
            "final_decision": final_analysis,
            "stock_info": {
                "stock_name": stock_name,
                "ticker": ticker,
                "analysis_date": base_date or datetime.now().strftime('%Y-%m-%d')
            },
            "component_analyses": {
                "safety_analysis": safety_text,
                "growth_analysis": growth_text
            },
            "prompt_used": final_prompt
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"최종 투자 판단 중 오류 발생: {str(e)}"
        }


# 통합 투자 분석 함수 추가
def analyze_investment_comprehensive(user_query: str) -> Dict[str, Any]:
    """
    사용자 질문을 받아 전체 투자 분석 과정을 순차적으로 실행하는 통합 함수
    """
    try:
        # 1. 종목 정보 추출
        stock_info = get_info_stock(user_query)
        if "error" in stock_info:
            return stock_info
            
        # 2. Yahoo Finance 데이터 수집
        yf_result = get_yfinance_data(stock_info["ticker"])
        if yf_result.get("status") != "success":
            return {"error": "Yahoo Finance 데이터 수집 실패", "details": yf_result}
            
        # 3. DART 데이터 수집
        dart_result = get_dart_disclosure_data(stock_info["stock_name"], stock_info["corp_code"])
        if dart_result.get("status") != "success":
            return {"error": "DART 데이터 수집 실패", "details": dart_result}
            
        # 4. 성장성 분석 (LLM 호출 포함)
        growth_analysis = format_growth_prompt(
            fin_data=yf_result["data"]["data"],
            news_list=[item.get("title", "") for item in yf_result["data"]["data"].get("news", [])]
        )
        
        # 5. 재무건전성 분석 (LLM 호출 포함)
        safety_analysis = format_financial_safety_prompt(dart_result["data"])
        
        # 6. 최종 종합 판단 (LLM 호출 포함)
        final_decision = generate_investment_prompt_summary(
            safety_summary=safety_analysis,
            growth_summary=growth_analysis,
            ticker=stock_info["ticker"],
            stock_name=stock_info["stock_name"]
        )
        
        return {
            "status": "success",
            "stock_info": stock_info,
            "growth_analysis": growth_analysis,
            "safety_analysis": safety_analysis,
            "final_decision": final_decision,
            "raw_data": {
                "yahoo_finance": yf_result,
                "dart_data": dart_result
            }
        }
        
    except Exception as e:
        return {
            "status": "error",
            "message": f"종합 투자 분석 중 오류 발생: {str(e)}"
        }
# 수정된 task5_py_funcs 딕셔너리
task5_py_funcs = {
    "get_info_stock": get_info_stock,
    "get_yfinance_data": get_yfinance_data,
    "get_dart_disclosure_data": get_dart_disclosure_data,
    "calculate_roe_peg": calculate_roe_peg,
    "format_growth_prompt": format_growth_prompt,  
    "format_financial_safety_prompt": format_financial_safety_prompt, 
    "generate_investment_prompt_summary": generate_investment_prompt_summary,  
    "analyze_investment_comprehensive": analyze_investment_comprehensive  
}