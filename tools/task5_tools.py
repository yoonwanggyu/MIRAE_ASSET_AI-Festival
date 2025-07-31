# task5_tools.py - 투자 판단 분석 도구
from utils import *
from datetime import datetime
import pandas as pd
import yfinance as yf
from typing import Dict, Any, List,Optional
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
        "description": "성장성 분석에 필요한 주요 데이터를 LLM 프롬프트용 요약 텍스트로 변환합니다.",
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
        "description": "DART 수집 데이터에서 재무건전성 판단에 필요한 주요 지표를 추출하고, 체계적 분석을 위한 프롬프트를 생성합니다.",
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
        "description": "재무건전성과 성장성 분석 결과를 종합하여 최종 투자 판단 프롬프트를 생성합니다.",
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
    }
]

# =============================================================================
# 1. 종목 정보 추출 모듈
# =============================================================================


def get_info_stock(user_query: str, csv_path="data/krx_tickers_cleaned.csv"):
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
    ticker = row["code"]
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
                        peg=None) -> str:
    """
    성장성 분석에 필요한 주요 데이터를 LLM 프롬프트용 요약 텍스트로 변환
    - fin_data: 시가총액, PER, PBR, EPS, 배당률 등 주요지표 dict
    - income_stmt: 손익계산서 등 재무 데이터(옵션)
    - news_list: 관련 뉴스 요약문 리스트(옵션)
    """
    roe_peg_summary = calculate_roe_peg(fin_data)

    # summary_table에 반영
    roe = roe_peg_summary.get("ROE", "N/A")
    peg = roe_peg_summary.get("PEG", "N/A")

    # 주요 수치 지표 요약
    prompt = []
    prompt.append(f"\n■ 성장성 주요 지표 요약")
    
    info = fin_data.get("info", {})
    if info.get("currentPrice"): 
        prompt.append(f"- 현재가: {info['currentPrice']:,.0f}")
    if info.get("marketCap"): 
        prompt.append(f"- 시가총액: {info['marketCap']/1e12:.2f}조")
    if info.get("trailingPE"): 
        prompt.append(f"- PER: {info['trailingPE']:.2f}")
    if info.get("priceToBook"): 
        prompt.append(f"- PBR: {info['priceToBook']:.2f}")
    if info.get("trailingEps"): 
        prompt.append(f"- EPS: {info['trailingEps']:,.0f}")
    if info.get("dividendYield"): 
        prompt.append(f"- 배당수익률: {info['dividendYield']*100:.2f}%")
    if info.get("recommendationKey"): 
        prompt.append(f"- 애널리스트 평균 등급: {info['recommendationKey']}")
    if info.get("targetMeanPrice"): 
        prompt.append(f"- 애널리스트 목표가: {info['targetMeanPrice']:,.0f}")
    
    # 손익계산서 등 성장 관련 실적
    if income_stmt:
        rev = income_stmt.get("매출액") or income_stmt.get("Revenue")
        op_profit = income_stmt.get("영업이익") or income_stmt.get("Operating Income")
        net_profit = income_stmt.get("당기순이익") or income_stmt.get("Net Income")
        year = income_stmt.get("연도", "")
        if rev or op_profit or net_profit:
            prompt.append(f"\n■ 최근 재무 성과")
            if year: prompt.append(f"- 연도: {year}")
            if rev: prompt.append(f"- 매출액: {rev}")
            if op_profit: prompt.append(f"- 영업이익: {op_profit}")
            if net_profit: prompt.append(f"- 순이익: {net_profit}")
        
    # 관련 뉴스 헤드라인 요약 추가
    if news_list:
        prompt.append(f"\n■ 최근 시장 뉴스 요약")
        for news in news_list[:3]:  # 최대 3개만 예시
            prompt.append(f"- {news}")

    if roe:
        prompt.append(f"- ROE(자기자본이익률): {roe}")
    if peg is not None:
        prompt.append(f"- PEG(성장반영 PER): {peg}")

    # 이론 및 평가 기준 요약 포함
    prompt.append("\n■ 투자매력 평가기준 안내")
    prompt.append("- 매출, 이익이 최근 몇 년간 꾸준히 성장했는가?")
    prompt.append("- ROE 등 수익성 지표가 업계 평균 대비 우수한가?")
    prompt.append("- PER, PBR 등 밸류에이션이 저평가/고평가 구간인지?")
    prompt.append("- 애널리스트 목표가·뉴스 등 시장의 기대/우려 요인은?")
    prompt.append("\n상기 계량적 지표와 기준을 참고해 기업의 성장성과 투자매력도를 논리적으로 종합 판단해줘.")
    
    return "\n".join(prompt)

# =============================================================================
# 3. 재무건전성 평가 (DART API) 데이터 수집 & 처리 모듈
# =============================================================================

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

        # 3. 감사보고서
        if "audit_report" in data_types:
            try:
                report = dart_fss.api.finance.audit_report(corp_code, bsns_year, reprt_code)
                result["data"]["audit_report"] = pd.DataFrame(report['list']) if 'list' in report else {}
            except:
                result["data"]["audit_report"] = {}

        # 4. 최대주주 현황
        if "major_shareholders" in data_types:
            holders = dart_fss.api.info.hyslr_sttus(corp_code, bsns_year, reprt_code)
            result["data"]["major_shareholders"] = pd.DataFrame(holders['list']) if 'list' in holders else {}

        # 5. 배당 현황
        if "dividends" in data_types:
            dividends = dart_fss.api.info.alot_matter(corp_code, bsns_year, reprt_code)
            result["data"]["dividends"] = pd.DataFrame(dividends['list']) if 'list' in dividends else {}

        # 6. 직원 현황
        if "employees" in data_types:
            emp = dart_fss.api.info.emp_sttus(corp_code, bsns_year, reprt_code)
            result["data"]["employees"] = pd.DataFrame(emp['list']) if 'list' in emp else {}

        # 7. 주주 현황
        if "shareholders" in data_types:
            shareholders = dart_fss.api.shareholder.elestock(corp_code)
            result["data"]["shareholders"] = pd.DataFrame(shareholders['list']) if 'list' in shareholders else {}

        return {"status": "success", "data": result}

    except Exception as e:
        return {
            "status": "error",
            "message": f"DART 데이터 수집 오류: {str(e)}"
        }

def format_financial_safety_prompt(dart_data: Dict[str, Any]) -> str:
    """
    DART 수집 데이터에서 재무건전성 판단에 필요한 주요 지표를 추출하고,
    금융 전문가 수준의 체계적 분석을 위한 프롬프트 생성
    
    Args:
        dart_data: get_dart_disclosure_data()의 result["data"] 값
    
    Returns:
        str: 재무건전성 분석용 프롬프트 텍스트
    """
    prompt = ["\n■ 재무건전성 종합 분석 요약"]
    
    try:
        fin_df = dart_data.get("financial_summary", pd.DataFrame())
        shareholders_df = dart_data.get("shareholders", pd.DataFrame())
        
        if not isinstance(fin_df, pd.DataFrame) or fin_df.empty:
            prompt.append("- 재무제표 요약 데이터가 없습니다.")
            return "\n".join(prompt)
        
        # 재무제표 데이터 전처리
        fin_dict = _process_financial_data(fin_df)
        
        # 1. 유동성 분석 (Liquidity Analysis)
        prompt.extend(_analyze_liquidity(fin_dict))
        
        # 2. 활동성 분석 (Activity Analysis)  
        prompt.extend(_analyze_activity(fin_dict))
        
        # 3. 레버리지 분석 (Leverage Analysis)
        prompt.extend(_analyze_leverage(fin_dict))
        
        # 4. 수익성 분석 (Profitability Analysis)
        prompt.extend(_analyze_profitability(fin_dict))
        
        # 5. 성장성 분석 (Growth Analysis)
        prompt.extend(_analyze_growth(fin_dict))
        
        # 6. 지배구조 분석 (Corporate Governance)
        if not shareholders_df.empty:
            prompt.extend(_analyze_governance(shareholders_df))
        
        # 7. 신용위험 평가 (Credit Risk Assessment)
        prompt.extend(_assess_credit_risk(fin_dict))
        
        # 8. 종합 평가 기준
        prompt.extend(_comprehensive_evaluation_criteria())
        
        prompt.append("\n상기 재무지표와 평가기준을 바탕으로 기업의 재무건전성을 5단계(매우우수/우수/보통/주의/위험)로 평가하고, 각 영역별 강점과 개선점을 제시해주세요.")
        
        return "\n".join(prompt)
        
    except Exception as e:
        return f"❌ 재무건전성 분석 중 오류: {str(e)}"

def _process_financial_data(fin_df: pd.DataFrame) -> Dict[str, float]:
    """재무제표 데이터를 딕셔너리로 변환"""
    fin_dict = {}
    
    # 주요 계정과목 매핑
    account_mapping = {
        # 자산
        "유동자산": ["유동자산"],
        "비유동자산": ["비유동자산"],
        "자산총계": ["자산총계"],
        "현금및현금성자산": ["현금및현금성자산", "현금및단기금융상품"],
        "매출채권": ["매출채권", "받을어음및매출채권"],
        "재고자산": ["재고자산"],
        
        # 부채
        "유동부채": ["유동부채"],
        "비유동부채": ["비유동부채"],
        "부채총계": ["부채총계"],
        "차입금": ["단기차입금", "장기차입금", "사채"],
        "이자비용": ["이자비용"],
        
        # 자본
        "자본총계": ["자본총계"],
        "자본금": ["자본금"],
        "이익잉여금": ["이익잉여금"],
        
        # 손익
        "매출액": ["매출액", "수익(매출액)"],
        "영업이익": ["영업이익"],
        "당기순이익": ["당기순이익"],
        "법인세비용": ["법인세비용"],
        "EBITDA": ["EBITDA"],
        "감가상각비": ["감가상각비"]
    }
    
    for key, account_names in account_mapping.items():
        for account_name in account_names:
            matching_rows = fin_df[fin_df["account_nm"] == account_name]
            if not matching_rows.empty:
                value = matching_rows.iloc[0]["thstrm_amount"]
                try:
                    fin_dict[key] = float(value) if value and str(value).replace('-','').replace('.','').isdigit() else 0
                    break
                except:
                    fin_dict[key] = 0
        
        if key not in fin_dict:
            fin_dict[key] = 0
    
    return fin_dict

def _analyze_liquidity(fin_dict: Dict[str, float]) -> list:
    """유동성 분석"""
    analysis = ["\n■ 1. 유동성 분석 (Liquidity Analysis)"]
    
    # 유동비율 (Current Ratio)
    current_ratio = (fin_dict["유동자산"] / fin_dict["유동부채"] * 100) if fin_dict["유동부채"] != 0 else 0
    analysis.append(f"- 유동비율: {current_ratio:.1f}% (유동자산/유동부채)")
    
    # 당좌비율 (Quick Ratio)
    quick_assets = fin_dict["유동자산"] - fin_dict["재고자산"]
    quick_ratio = (quick_assets / fin_dict["유동부채"] * 100) if fin_dict["유동부채"] != 0 else 0
    analysis.append(f"- 당좌비율: {quick_ratio:.1f}% ((유동자산-재고자산)/유동부채)")
    
    # 현금비율 (Cash Ratio)
    cash_ratio = (fin_dict["현금및현금성자산"] / fin_dict["유동부채"] * 100) if fin_dict["유동부채"] != 0 else 0
    analysis.append(f"- 현금비율: {cash_ratio:.1f}% (현금성자산/유동부채)")
    
    # 순운전자본 (Net Working Capital)
    nwc = fin_dict["유동자산"] - fin_dict["유동부채"]
    analysis.append(f"- 순운전자본: {nwc:,.0f}원 (유동자산-유동부채)")
    
    return analysis

def _analyze_activity(fin_dict: Dict[str, float]) -> list:
    """활동성 분석"""
    analysis = ["\n■ 2. 활동성 분석 (Activity Analysis)"]
    
    # 총자산회전율 (Total Asset Turnover)
    asset_turnover = fin_dict["매출액"] / fin_dict["자산총계"] if fin_dict["자산총계"] != 0 else 0
    analysis.append(f"- 총자산회전율: {asset_turnover:.2f}회 (매출액/총자산)")
    
    # 매출채권회전율 (Receivables Turnover)
    if fin_dict["매출채권"] != 0:
        receivable_turnover = fin_dict["매출액"] / fin_dict["매출채권"]
        receivable_days = 365 / receivable_turnover if receivable_turnover != 0 else 0
        analysis.append(f"- 매출채권회전율: {receivable_turnover:.1f}회, 회수기간: {receivable_days:.0f}일")
    
    # 재고자산회전율 (Inventory Turnover)
    if fin_dict["재고자산"] != 0:
        inventory_turnover = fin_dict["매출액"] / fin_dict["재고자산"]
        inventory_days = 365 / inventory_turnover if inventory_turnover != 0 else 0
        analysis.append(f"- 재고자산회전율: {inventory_turnover:.1f}회, 보유기간: {inventory_days:.0f}일")
    
    return analysis


def _analyze_leverage(fin_dict: Dict[str, float]) -> list:
    """레버리지 분석"""
    analysis = ["\n■ 3. 레버리지 분석 (Leverage Analysis)"]
    
    # 부채비율 (Debt Ratio)
    debt_ratio = (fin_dict["부채총계"] / fin_dict["자본총계"] * 100) if fin_dict["자본총계"] != 0 else 0
    analysis.append(f"- 부채비율: {debt_ratio:.1f}% (총부채/총자본)")
    
    # 부채대자산비율 (Debt to Asset Ratio)
    debt_to_asset = (fin_dict["부채총계"] / fin_dict["자산총계"] * 100) if fin_dict["자산총계"] != 0 else 0
    analysis.append(f"- 부채대자산비율: {debt_to_asset:.1f}% (총부채/총자산)")
    
    # 이자보상배율 (Interest Coverage Ratio)
    interest_coverage = fin_dict["영업이익"] / fin_dict["이자비용"] if fin_dict["이자비용"] != 0 else float('inf')
    if interest_coverage == float('inf'):
        analysis.append("- 이자보상배율: 무한대 (이자비용 없음)")
    else:
        analysis.append(f"- 이자보상배율: {interest_coverage:.1f}배 (영업이익/이자비용)")
    
    # 차입금의존도 (Borrowings Dependency)
    borrowing_dependency = (fin_dict["차입금"] / fin_dict["자산총계"] * 100) if fin_dict["자산총계"] != 0 else 0
    analysis.append(f"- 차입금의존도: {borrowing_dependency:.1f}% (차입금/총자산)")
    
    # 자기자본비율 (Equity Ratio)
    equity_ratio = (fin_dict["자본총계"] / fin_dict["자산총계"] * 100) if fin_dict["자산총계"] != 0 else 0
    analysis.append(f"- 자기자본비율: {equity_ratio:.1f}% (총자본/총자산)")
    
    return analysis


def _analyze_profitability(fin_dict: Dict[str, float]) -> list:
    """수익성 분석"""
    analysis = ["\n■ 4. 수익성 분석 (Profitability Analysis)"]
    
    # 매출액영업이익률 (Operating Margin)
    operating_margin = (fin_dict["영업이익"] / fin_dict["매출액"] * 100) if fin_dict["매출액"] != 0 else 0
    analysis.append(f"- 영업이익률: {operating_margin:.1f}% (영업이익/매출액)")
    
    # 매출액순이익률 (Net Margin)
    net_margin = (fin_dict["당기순이익"] / fin_dict["매출액"] * 100) if fin_dict["매출액"] != 0 else 0
    analysis.append(f"- 순이익률: {net_margin:.1f}% (당기순이익/매출액)")
    
    # 총자산이익률 (ROA)
    roa = (fin_dict["당기순이익"] / fin_dict["자산총계"] * 100) if fin_dict["자산총계"] != 0 else 0
    analysis.append(f"- ROA: {roa:.1f}% (당기순이익/총자산)")
    
    # 자기자본이익률 (ROE)
    roe = (fin_dict["당기순이익"] / fin_dict["자본총계"] * 100) if fin_dict["자본총계"] != 0 else 0
    analysis.append(f"- ROE: {roe:.1f}% (당기순이익/총자본)")
    
    # EBITDA 마진
    if fin_dict["EBITDA"] != 0:
        ebitda_margin = (fin_dict["EBITDA"] / fin_dict["매출액"] * 100) if fin_dict["매출액"] != 0 else 0
        analysis.append(f"- EBITDA 마진: {ebitda_margin:.1f}% (EBITDA/매출액)")
    
    return analysis


def _analyze_growth(fin_dict: Dict[str, float]) -> list:
    """성장성 분석 (전년대비 데이터가 있을 경우)"""
    analysis = ["\n■ 5. 성장성 분석 (Growth Analysis)"]
    analysis.append("- 성장성 분석을 위해서는 전년도 데이터와의 비교가 필요합니다.")
    analysis.append("- 매출액 성장률, 영업이익 성장률, 자산 성장률 등을 평가하세요.")
    
    return analysis


def _analyze_governance(shareholders_df: pd.DataFrame) -> list:
    """지배구조 분석"""
    analysis = ["\n■ 6. 지배구조 분석 (Corporate Governance)"]
    
    try:
        # 최대주주 지분율
        if not shareholders_df.empty and 'stkrt' in shareholders_df.columns:
            max_ownership = shareholders_df['stkrt'].max()
            analysis.append(f"- 최대주주 지분율: {max_ownership}%")
            
            # 소유집중도 평가
            if max_ownership > 50:
                analysis.append("- 소유구조: 지배주주 존재 (지분율 50% 초과)")
            elif max_ownership > 30:
                analysis.append("- 소유구조: 상당한 영향력 보유 (지분율 30-50%)")
            else:
                analysis.append("- 소유구조: 분산된 소유구조 (지분율 30% 이하)")
        else:
            analysis.append("- 주주구조 데이터가 불충분합니다.")
            
    except Exception as e:
        analysis.append(f"- 지배구조 분석 오류: {str(e)}")
    
    return analysis


def _assess_credit_risk(fin_dict: Dict[str, float]) -> list:
    """신용위험 평가"""
    analysis = ["\n■ 7. 신용위험 평가 (Credit Risk Assessment)"]
    
    # Altman Z-Score 계산 (상장기업용)
    try:
        # Z = 1.2*X1 + 1.4*X2 + 3.3*X3 + 0.6*X4 + 1.0*X5
        # X1 = 순운전자본/총자산
        # X2 = 이익잉여금/총자산  
        # X3 = 영업이익/총자산
        # X4 = 시가총액/총부채 (여기서는 자기자본/총부채로 대체)
        # X5 = 매출액/총자산
        
        x1 = (fin_dict["유동자산"] - fin_dict["유동부채"]) / fin_dict["자산총계"] if fin_dict["자산총계"] != 0 else 0
        x2 = fin_dict["이익잉여금"] / fin_dict["자산총계"] if fin_dict["자산총계"] != 0 else 0
        x3 = fin_dict["영업이익"] / fin_dict["자산총계"] if fin_dict["자산총계"] != 0 else 0
        x4 = fin_dict["자본총계"] / fin_dict["부채총계"] if fin_dict["부채총계"] != 0 else 0
        x5 = fin_dict["매출액"] / fin_dict["자산총계"] if fin_dict["자산총계"] != 0 else 0
        
        z_score = 1.2*x1 + 1.4*x2 + 3.3*x3 + 0.6*x4 + 1.0*x5
        
        analysis.append(f"- Altman Z-Score: {z_score:.2f}")
        
        if z_score > 2.99:
            analysis.append("  → 안전 구간 (부도위험 낮음)")
        elif z_score > 1.81:
            analysis.append("  → 회색 구간 (주의 필요)")
        else:
            analysis.append("  → 위험 구간 (부도위험 높음)")
            
    except Exception as e:
        analysis.append(f"- Z-Score 계산 오류: {str(e)}")
    
    # 현금흐름 안정성 (데이터가 있는 경우)
    if fin_dict["현금및현금성자산"] > 0:
        cash_to_debt = (fin_dict["현금및현금성자산"] / fin_dict["부채총계"] * 100) if fin_dict["부채총계"] != 0 else 0
        analysis.append(f"- 현금 대비 부채비율: {cash_to_debt:.1f}%")
    
    return analysis


def _comprehensive_evaluation_criteria() -> list:
    """종합 평가 기준"""
    criteria = ["\n■ 8. 재무건전성 평가 기준"]
    
    criteria.extend([
        "\n【유동성 기준】",
        "- 매우우수: 유동비율 200%↑, 당좌비율 100%↑",
        "- 우수: 유동비율 150-200%, 당좌비율 80-100%", 
        "- 보통: 유동비율 100-150%, 당좌비율 50-80%",
        "- 주의: 유동비율 80-100%, 당좌비율 30-50%",
        "- 위험: 유동비율 80%↓, 당좌비율 30%↓",
        
        "\n【레버리지 기준】",
        "- 매우우수: 부채비율 100%↓, 이자보상배율 10배↑",
        "- 우수: 부채비율 100-150%, 이자보상배율 5-10배",
        "- 보통: 부채비율 150-200%, 이자보상배율 2-5배", 
        "- 주의: 부채비율 200-300%, 이자보상배율 1-2배",
        "- 위험: 부채비율 300%↑, 이자보상배율 1배↓",
        
        "\n【수익성 기준】",
        "- 매우우수: ROE 15%↑, ROA 10%↑, 영업이익률 15%↑",
        "- 우수: ROE 10-15%, ROA 5-10%, 영업이익률 10-15%",
        "- 보통: ROE 5-10%, ROA 3-5%, 영업이익률 5-10%",
        "- 주의: ROE 0-5%, ROA 0-3%, 영업이익률 0-5%", 
        "- 위험: ROE 0%↓, ROA 0%↓, 영업손실",
        
        "\n【신용위험 기준】",
        "- Altman Z-Score > 2.99: 안전",
        "- Altman Z-Score 1.81-2.99: 회색지대",
        "- Altman Z-Score < 1.81: 위험"
    ])
    
    return criteria

def generate_investment_prompt_summary(
    safety_summary: Optional[str] = None,
    growth_summary: Optional[str] = None,
    ticker: Optional[str] = None,
    stock_name: Optional[str] = None,
    base_date: Optional[str] = None
) -> str:
    """
    최종 투자 판단 프롬프트 요약 생성 (재무건전성, 성장성 요약 결합)
    - safety_summary: format_financial_safety_prompt() 결과
    - growth_summary: format_growth_prompt() 결과
    - ticker / stock_name / base_date: 리포트 메타 정보
    """
    
    header = f"""[Fin문철 종합 리포트] 📈 종목: {stock_name} ({ticker}) 📅 기준일: {base_date or 'N/A'}\n"""
    
    if safety_summary and growth_summary:
        return header + f"""
🔍 <1> 재무 건전성 진단 요약:
{safety_summary}

🚀 <2> 시장 지표 기반 성장성 분석:
{growth_summary}

📌 <AI 종합 판단 요약>
- 해당 종목은 현재 **재무구조의 안정성**과 **시장지표 상 저평가 여부**를 종합적으로 고려할 때, {"상대적으로 안정된 투자처로 평가됨" if "양호" in safety_summary and "저평가" in growth_summary else "투자 시 주의가 요구됨"}.
- 단기 수익보다는 중장기적 관점에서 접근하는 것이 바람직함.
"""
    
    elif safety_summary:
        return header + f"""
🔍 <1> 재무 건전성 진단 요약:
{safety_summary}

📌 <AI 종합 판단 요약>
- 공시 기반 재무구조 평가 결과, 해당 기업은 {"재무적으로 안정된 편" if "양호" in safety_summary or "안정" in safety_summary else "재무 리스크가 존재"}.
- {"재무구조가 튼튼하여 안정적인 투자 기반이 될 수 있음" if "양호" in safety_summary else "현 시점 투자에는 보수적 접근이 필요함"}.
"""
    
    elif growth_summary:
        return header + f"""
🚀 <1> 시장 지표 기반 성장성 분석:
{growth_summary}

📌 <AI 종합 판단 요약>
- 시장 데이터에 따르면 해당 종목은 현재 {"PER/PBR 기준 저평가 상태로 보이며" if "저평가" in growth_summary else "고평가 상태로 보이며"}, {"기대 수익 가능성이 존재" if "저평가" in growth_summary else "신중한 접근이 필요"}.
- {"단기 모멘텀이 강하므로 매수 타이밍 포착이 중요" if "강세" in growth_summary else "시장 흐름 변화에 유의 필요"}.
"""

    else:
        return header + """
⚠️ 데이터 부족
- 재무건전성 및 성장성에 대한 분석 데이터가 부족하여 투자 판단을 내리기 어려움.
- 공시 또는 시장 데이터를 확인 후 다시 분석을 요청하세요.
"""

task5_py_funcs = {
    "get_info_stock": get_info_stock,
    "get_yfinance_data": get_yfinance_data,
    "get_dart_disclosure_data": get_dart_disclosure_data,
    "calculate_roe_peg": calculate_roe_peg,
    "format_growth_prompt": format_growth_prompt,
    "format_financial_safety_prompt": format_financial_safety_prompt,
    "generate_investment_prompt_summary": generate_investment_prompt_summary
}