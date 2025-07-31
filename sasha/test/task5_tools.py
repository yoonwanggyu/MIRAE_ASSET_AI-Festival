"""
Task5: Fin문철의 블랙박스 - 투자 판단 분석 도구
- 투자 실패/성공의 원인과 맥락을 항공 블랙박스처럼 해부하여 분석하는 AI 도구
"""

import yfinance as yf
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple
from utils import name_to_ticker, normalize_date
import re
import json


class InvestmentBlackBox:
    """Fin문철의 블랙박스 - 투자 판단 분석 클래스"""
    
    def __init__(self, dart_api_key: str = None):
        """
        Args:
            dart_api_key: DART Open API 키 (공시 정보 수집용)
        """
        self.dart_api_key = '0778fdc977a04c6bc0516326fe22cea0224b233b' #'여기에 API 키를 입력'
        self.dart_base_url = "https://opendart.fss.or.kr/api"
    
    def _get_stock_info_at_date(self, ticker: str, date: str) -> Dict[str, Any]:
        """특정 날짜의 주식 정보 수집 (yfinance)"""
        try:
            stock = yf.Ticker(ticker)
            target_date = pd.to_datetime(date).tz_localize("Asia/Seoul")
            start_date = target_date - timedelta(days=30)  # 30일 전부터 데이터 수집
            end_date = target_date + timedelta(days=1)
            
            # 주가 데이터
            hist = stock.history(start=start_date, end=end_date)
            if hist.empty:
                return {"error": "해당 날짜의 주가 데이터를 찾을 수 없습니다."}
            
            # 해당 날짜와 가장 가까운 거래일 찾기
            closest_date = hist.index[hist.index <= target_date].max()
            if pd.isna(closest_date):
                closest_date = hist.index.min()
            
            price_data = hist.loc[closest_date]
            
            # 기업 정보 (현재 기준)
            info = stock.info
            
            # 뉴스 데이터 (해당 시점 전후)
            news = self._get_news_around_date(stock, target_date)
            
            return {
                "date": closest_date.strftime("%Y-%m-%d"),
                "price": {
                    "close": float(price_data["Close"]),
                    "volume": int(price_data["Volume"]),
                    "high": float(price_data["High"]),
                    "low": float(price_data["Low"])
                },
                "valuation": {
                    "market_cap": info.get("marketCap", 0),
                    "pe_ratio": info.get("trailingPE"),
                    "pb_ratio": info.get("priceToBook"),
                    "eps": info.get("trailingEps"),
                    "dividend_yield": info.get("dividendYield")
                },
                "analyst": {
                    "recommendation": info.get("recommendationKey"),
                    "target_price": info.get("targetMeanPrice"),
                    "analyst_count": info.get("numberOfAnalystOpinions")
                },
                "news": news[:5],  # 최근 5개 뉴스
                "sector": info.get("sector"),
                "industry": info.get("industry")
            }
        except Exception as e:
            return {"error": f"데이터 수집 중 오류: {str(e)}"}
    
    def _get_news_around_date(self, stock, target_date: pd.Timestamp) -> List[Dict]:
        """특정 날짜 전후의 뉴스 수집"""
        try:
            news = stock.news
            relevant_news = []
            
            for item in news:
                # Unix timestamp를 datetime으로 변환
                news_date = pd.to_datetime(item.get('providerPublishTime', 0), unit='s')
                
                # 목표 날짜 전후 30일 내의 뉴스만 선택
                if abs((news_date - target_date).days) <= 30:
                    relevant_news.append({
                        "title": item.get("title", ""),
                        "date": news_date.strftime("%Y-%m-%d"),
                        "publisher": item.get("publisher", ""),
                        "link": item.get("link", "")
                    })
            
            return sorted(relevant_news, key=lambda x: x["date"], reverse=True)
        except:
            return []
    
    def _get_dart_info(self, corp_code: str, date: str) -> Dict[str, Any]:
        """DART API를 통한 공시 정보 수집"""
        if not self.dart_api_key:
            return {"warning": "DART API 키가 설정되지 않아 공시 정보를 가져올 수 없습니다."}
        
        try:
            # 해당 날짜 전후의 공시 목록 조회
            target_date = pd.to_datetime(date).tz_localize("Asia/Seoul")
            start_date = (target_date - timedelta(days=90)).strftime("%Y%m%d")
            end_date = (target_date + timedelta(days=30)).strftime("%Y%m%d")
            
            # 공시 목록 API
            list_url = f"{self.dart_base_url}/list.json"
            params = {
                "crtfc_key": self.dart_api_key,
                "corp_code": corp_code,
                "bgn_de": start_date,
                "end_de": end_date,
                "page_no": 1,
                "page_count": 50
            }
            
            response = requests.get(list_url, params=params)
            if response.status_code != 200:
                return {"error": "DART API 요청 실패"}
            
            data = response.json()
            if data.get("status") != "000":
                return {"error": f"DART API 오류: {data.get('message', 'Unknown error')}"}
            
            disclosures = data.get("list", [])
            
            # 위험 신호 감지
            risk_signals = self._analyze_disclosure_risks(disclosures)
            
            # 재무제표 정보 수집
            financial_data = self._get_financial_data(corp_code, date)
            
            return {
                "disclosures": disclosures[:10],  # 최근 10개 공시
                "risk_signals": risk_signals,
                "financial_summary": financial_data
            }
        except Exception as e:
            return {"error": f"DART 정보 수집 중 오류: {str(e)}"}
    
    def _analyze_disclosure_risks(self, disclosures: List[Dict]) -> Dict[str, Any]:
        """공시 정보에서 리스크 신호 분석"""
        risk_keywords = {
            "capital_increase": ["유상증자", "신주발행", "제3자배정"],
            "audit_issues": ["감사의견", "한정", "부적정", "의견거절"],
            "legal_issues": ["소송", "중요한소송등", "중요계약"],
            "governance": ["최대주주", "지배구조", "경영권"],
            "financial_stress": ["자금조달", "차입", "회생절차", "기업회생"]
        }
        
        detected_risks = {category: [] for category in risk_keywords.keys()}
        
        for disclosure in disclosures:
            report_name = disclosure.get("report_nm", "").lower()
            
            for category, keywords in risk_keywords.items():
                for keyword in keywords:
                    if keyword in report_name:
                        detected_risks[category].append({
                            "report": disclosure.get("report_nm"),
                            "date": disclosure.get("rcept_dt"),
                            "keyword": keyword
                        })
        
        # 위험도 점수 계산
        risk_score = sum(len(risks) for risks in detected_risks.values())
        
        return {
            "risk_score": risk_score,
            "detected_risks": detected_risks,
            "risk_level": "높음" if risk_score >= 3 else "보통" if risk_score >= 1 else "낮음"
        }
    
    def _get_financial_data(self, corp_code: str, date: str) -> Dict[str, Any]:
        """재무제표 요약 정보 수집"""
        if not self.dart_api_key:
            return {"warning": "DART API 키 필요"}
        
        try:
            # 해당 연도의 재무제표 조회
            year = pd.to_datetime(date).year
            
            url = f"{self.dart_base_url}/fnlttSinglAcntAll.json"
            params = {
                "crtfc_key": self.dart_api_key,
                "corp_code": corp_code,
                "bsns_year": str(year),
                "reprt_code": "11011"  # 사업보고서
            }
            
            response = requests.get(url, params=params)
            if response.status_code != 200:
                return {"error": "재무제표 조회 실패"}
            
            data = response.json()
            if data.get("status") != "000":
                return {"error": "재무제표 데이터 없음"}
            
            # 주요 재무 지표 추출
            financial_items = data.get("list", [])
            summary = self._extract_financial_summary(financial_items)
            
            return summary
        except Exception as e:
            return {"error": f"재무데이터 수집 오류: {str(e)}"}
    
    def _extract_financial_summary(self, financial_items: List[Dict]) -> Dict[str, Any]:
        """재무제표에서 주요 지표 추출"""
        key_metrics = {
            "매출액": ["매출액", "수익(매출액)"],
            "영업이익": ["영업이익"],
            "당기순이익": ["당기순이익", "순이익"],
            "자산총계": ["자산총계"],
            "부채총계": ["부채총계"],
            "자본총계": ["자본총계", "자본금"]
        }
        
        extracted = {}
        
        for item in financial_items:
            account_nm = item.get("account_nm", "")
            thstrm_amount = item.get("thstrm_amount", "0")
            
            for metric_name, keywords in key_metrics.items():
                if any(keyword in account_nm for keyword in keywords):
                    try:
                        amount = int(thstrm_amount.replace(",", "")) if thstrm_amount.replace(",", "").isdigit() else 0
                        if metric_name not in extracted or amount > extracted[metric_name]:
                            extracted[metric_name] = amount
                    except:
                        continue
        
        return extracted


def analyze_investment_decision(stock_name: str, purchase_date: str, purchase_price: float = None) -> str:
    """
    투자 블랙박스 해부: 특정 시점의 매수 판단 분석
    
    Args:
        stock_name: 종목명
        purchase_date: 매수 날짜 (YYYY-MM-DD)
        purchase_price: 매수 가격 (선택사항)
    
    Returns:
        AI 판단 요약 및 분석 결과
    """
    try:
        # 1. 종목 티커 매핑
        ticker = name_to_ticker(stock_name)
        if not ticker:
            return f"❌ '{stock_name}' 종목을 찾을 수 없습니다."


        stock = yf.Ticker(ticker)
        d0 = pd.Timestamp(date_std)
        d1 = d0 + timedelta(days=1)
            
        # 2. 날짜 정규화
        try:
            normalized_date = normalize_date(purchase_date).split()[0]
        except ValueError as e:
            return f"❌ 날짜 형식 오류: {e}"
        
        # 3. 블랙박스 분석 시작
        blackbox = InvestmentBlackBox()
        
        # 4. 해당 시점 주식 정보 수집
        stock_info = blackbox._get_stock_info_at_date(ticker, normalized_date)
        
        if "error" in stock_info:
            return f"❌ {stock_info['error']}"
        
        # 5. 분석 결과 생성
        analysis_result = _generate_investment_analysis(
            stock_name, stock_info, purchase_price, normalized_date
        )
        
        return analysis_result
        
    except Exception as e:
        return f"❌ 분석 중 오류가 발생했습니다: {str(e)}"


def _generate_investment_analysis(stock_name: str, stock_info: Dict, purchase_price: float, date: str) -> str:
    """투자 판단 분석 결과 생성"""
    
    price_data = stock_info.get("price", {})
    valuation = stock_info.get("valuation", {})
    analyst = stock_info.get("analyst", {})
    news = stock_info.get("news", [])
    
    # 실제 거래 가격
    actual_price = price_data.get("close", 0)
    
    # 밸류에이션 분석
    pe_ratio = valuation.get("pe_ratio")
    pb_ratio = valuation.get("pb_ratio")
    
    # 가격 비교 (매수가 vs 실제가)
    price_comparison = ""
    if purchase_price:
        price_diff_pct = ((actual_price - purchase_price) / purchase_price) * 100
        if abs(price_diff_pct) > 5:
            price_comparison = f"입력하신 매수가({purchase_price:,.0f}원)와 해당일 종가({actual_price:,.0f}원) 간 {price_diff_pct:+.1f}% 차이가 있습니다."
    
    # 밸류에이션 판단
    valuation_assessment = "밸류에이션 정보가 부족합니다."
    if pe_ratio and pb_ratio:
        if pe_ratio < 15 and pb_ratio < 1.5:
            valuation_assessment = f"PER {pe_ratio:.1f}, PBR {pb_ratio:.1f}로 상당한 저평가 상태였습니다."
        elif pe_ratio < 20 and pb_ratio < 2.0:
            valuation_assessment = f"PER {pe_ratio:.1f}, PBR {pb_ratio:.1f}로 적정~저평가 구간이었습니다."
        else:
            valuation_assessment = f"PER {pe_ratio:.1f}, PBR {pb_ratio:.1f}로 고평가 우려가 있었습니다."
    
    # 애널리스트 의견
    analyst_opinion = ""
    if analyst.get("recommendation"):
        rec_map = {
            "buy": "매수", "strong_buy": "적극매수", 
            "hold": "보유", "sell": "매도", "strong_sell": "적극매도"
        }
        recommendation = rec_map.get(analyst["recommendation"], analyst["recommendation"])
        analyst_opinion = f"당시 애널리스트 의견은 '{recommendation}'이었습니다."
    
    # 뉴스 요약
    news_summary = ""
    if news:
        recent_news = [item["title"] for item in news[:3]]
        news_summary = f"주요 뉴스: {', '.join(recent_news[:2])} 등이 있었습니다."
    
    # 종합 판단 생성
    judgment = _make_investment_judgment(valuation, analyst, len(news))
    
    # 최종 리포트 작성
    report = f"""
[Fin문철 투자 블랙박스 분석 결과]

📊 **{stock_name} ({date} 기준 분석)**

**가격 정보:**
- 해당일 종가: {actual_price:,.0f}원
- 거래량: {price_data.get('volume', 0):,}주
{price_comparison}

**밸류에이션 분석:**
{valuation_assessment}

**시장 의견:**
{analyst_opinion}

**시장 상황:**
{news_summary}

**[AI 종합 판단]**
{judgment}

더 궁금하신가요?
"""
    
    return report.strip()


def _make_investment_judgment(valuation: Dict, analyst: Dict, news_count: int) -> str:
    """AI 기반 투자 판단 생성"""
    
    pe_ratio = valuation.get("pe_ratio")
    pb_ratio = valuation.get("pb_ratio")
    recommendation = analyst.get("recommendation", "")
    
    # 점수 기반 판단
    score = 0
    factors = []
    
    # 밸류에이션 점수
    if pe_ratio and pb_ratio:
        if pe_ratio < 15 and pb_ratio < 1.5:
            score += 3
            factors.append("저평가")
        elif pe_ratio < 20 and pb_ratio < 2.0:
            score += 1
            factors.append("적정가")
        else:
            score -= 2
            factors.append("고평가 우려")
    
    # 애널리스트 의견 점수
    if "buy" in recommendation.lower():
        score += 2
        factors.append("긍정적 애널리스트 의견")
    elif "hold" in recommendation.lower():
        score += 0
        factors.append("중립적 시장 의견")
    elif "sell" in recommendation.lower():
        score -= 2
        factors.append("부정적 시장 의견")
    
    # 뉴스 활동 점수 (뉴스가 많으면 변동성 위험)
    if news_count > 3:
        score -= 1
        factors.append("높은 뉴스 활동도")
    
    # 최종 판단
    if score >= 3:
        verdict = "정당한 매수 판단"
        reasoning = "기본적 분석 지표들이 긍정적이었고, 투자 판단이 합리적이었습니다."
    elif score >= 0:
        verdict = "보통 수준의 판단"
        reasoning = "일부 긍정적 요소가 있었으나, 신중한 접근이 필요했던 상황입니다."
    else:
        verdict = "위험했던 매수 타이밍"
        reasoning = "고평가 우려나 부정적 시장 신호가 존재했던 시점입니다."
    
    factor_summary = f"주요 고려 요소: {', '.join(factors)}"
    
    return f"{verdict}. {reasoning} {factor_summary}"


def check_current_investment_worthiness(stock_name: str) -> str:
    """
    사전 진단: 현재 시점에서 해당 종목의 투자 가치 분석
    
    Args:
        stock_name: 종목명
    
    Returns:
        현재 투자 가치 분석 결과
    """
    try:
        # 1. 종목 티커 매핑
        ticker = name_to_ticker(stock_name)
        if not ticker:
            return f"❌ '{stock_name}' 종목을 찾을 수 없습니다."
        
        # 2. 현재 시점 정보 수집
        today = datetime.now().strftime("%Y-%m-%d")
        blackbox = InvestmentBlackBox()
        
        stock_info = blackbox._get_stock_info_at_date(ticker, today)
        
        if "error" in stock_info:
            return f"❌ {stock_info['error']}"
        
        # 3. 투자 가치 분석
        analysis = _analyze_current_investment_value(stock_name, stock_info)
        
        return analysis
        
    except Exception as e:
        return f"❌ 분석 중 오류가 발생했습니다: {str(e)}"


def _analyze_current_investment_value(stock_name: str, stock_info: Dict) -> str:
    """현재 투자 가치 분석"""
    
    price_data = stock_info.get("price", {})
    valuation = stock_info.get("valuation", {})
    analyst = stock_info.get("analyst", {})
    news = stock_info.get("news", [])
    
    current_price = price_data.get("close", 0)
    pe_ratio = valuation.get("pe_ratio")
    pb_ratio = valuation.get("pb_ratio")
    dividend_yield = valuation.get("dividend_yield", 0)
    
    # 투자 매력도 점수 계산
    attractiveness_score = 0
    factors = []
    
    # 밸류에이션 평가
    if pe_ratio and pb_ratio:
        if pe_ratio < 12 and pb_ratio < 1.2:
            attractiveness_score += 4
            factors.append("매우 저평가")
        elif pe_ratio < 18 and pb_ratio < 1.8:
            attractiveness_score += 2
            factors.append("저평가")
        elif pe_ratio < 25 and pb_ratio < 2.5:
            attractiveness_score += 0
            factors.append("적정가")
        else:
            attractiveness_score -= 2
            factors.append("고평가")
    
    # 배당 수익률 평가
    if dividend_yield:
        dividend_pct = dividend_yield * 100
        if dividend_pct > 4:
            attractiveness_score += 2
            factors.append(f"높은 배당률({dividend_pct:.1f}%)")
        elif dividend_pct > 2:
            attractiveness_score += 1
            factors.append(f"양호한 배당률({dividend_pct:.1f}%)")
    
    # 애널리스트 의견 평가
    recommendation = analyst.get("recommendation", "")
    target_price = analyst.get("target_price")
    
    if "buy" in recommendation.lower():
        attractiveness_score += 2
        factors.append("긍정적 애널리스트 의견")
    elif "sell" in recommendation.lower():
        attractiveness_score -= 2
        factors.append("부정적 애널리스트 의견")
    
    # 목표가 대비 현재가
    if target_price and current_price:
        upside_potential = ((target_price - current_price) / current_price) * 100
        if upside_potential > 20:
            attractiveness_score += 2
            factors.append(f"높은 상승 여력({upside_potential:.1f}%)")
        elif upside_potential < -10:
            attractiveness_score -= 2
            factors.append(f"하락 위험({upside_potential:.1f}%)")
    
    # 최종 투자 권고 결정
    if attractiveness_score >= 5:
        recommendation_text = "✅ 매수 권고"
        risk_level = "낮음"
        action = "적극적 매수를 고려해볼 만합니다."
    elif attractiveness_score >= 2:
        recommendation_text = "⚖️ 신중한 매수"
        risk_level = "보통"
        action = "분할 매수나 추가 분석 후 투자를 권합니다."
    elif attractiveness_score >= -1:
        recommendation_text = "⏸️ 보류"
        risk_level = "보통"
        action = "당분간 관망하며 더 좋은 진입 기회를 기다리는 것이 좋겠습니다."
    else:
        recommendation_text = "⛔ 매수 비권고"
        risk_level = "높음"
        action = "현 시점에서는 투자를 피하는 것이 바람직합니다."
    
    # 리포트 생성
    report = f"""
[Fin문철 사전 진단 결과]

📈 **{stock_name} 현재 투자 가치 분석**

**현재 상황:**
- 현재가: {current_price:,.0f}원
- PER: {pe_ratio:.1f if pe_ratio else 'N/A'}
- PBR: {pb_ratio:.1f if pb_ratio else 'N/A'}
- 배당률: {dividend_yield*100:.1f}%" if dividend_yield else "- 배당률: N/A"

**주요 판단 요소:**
{' | '.join(factors)}

**종합 의견: {recommendation_text}**
위험도: {risk_level}

**투자 전략:**
{action}

**최근 뉴스:**
{news[0]['title'] if news else '관련 뉴스가 없습니다.'}

더 궁금하신가요?
"""
    
    return report.strip()


def generate_investment_verdict(stock_name: str, purchase_date: str, purchase_price: float, 
                              current_performance: str = None) -> str:
    """
    AI 판결 시스템: 매수 판단에 대한 법정 스타일 평가
    
    Args:
        stock_name: 종목명
        purchase_date: 매수 날짜
        purchase_price: 매수가
        current_performance: 현재 수익률 (선택사항)
    
    Returns:
        법정 스타일의 투자 판결문
    """
    try:
        # 1. 기본 투자 분석 수행
        analysis_result = analyze_investment_decision(stock_name, purchase_date, purchase_price)
        
        if analysis_result.startswith("❌"):
            return analysis_result
        
        # 2. 현재 주가와 비교
        ticker = name_to_ticker(stock_name)
        current_stock = yf.Ticker(ticker)
        current_price = current_stock.history(period="1d")["Close"].iloc[-1]
        
        # 3. 수익률 계산
        if purchase_price:
            return_pct = ((current_price - purchase_price) / purchase_price) * 100
        else:
            return_pct = 0
        
        # 4. 판결문 생성
        verdict = _generate_verdict_document(
            stock_name, purchase_date, purchase_price, 
            current_price, return_pct, analysis_result
        )
        
        return verdict
        
    except Exception as e:
        return f"❌ 판결문 생성 중 오류: {str(e)}"


def _generate_verdict_document(stock_name: str, purchase_date: str, purchase_price: float,
                             current_price: float, return_pct: float, analysis: str) -> str:
    """법정 스타일의 판결문 생성"""
    
    # 판결 유형 결정
    if return_pct > 10:
        verdict_type = "우수한 투자 판단"
        verdict_icon = "⚖️✅"
    elif return_pct > 0:
        verdict_type = "양호한 투자 판단"
        verdict_icon = "⚖️➡️"
    elif return_pct > -10:
        verdict_type = "보통 수준의 판단"
        verdict_icon = "⚖️⚠️"
    else:
        verdict_type = "아쉬운 투자 판단"
        verdict_icon = "⚖️❌"
    
    # 판결 사유 분석
    if "저평가" in analysis:
        reasoning = "피투자인은 밸류에이션 분석을 통해 저평가 구간에서 매수하였음이 인정됩니다."
    elif "고평가" in analysis:
        reasoning = "피투자인은 고평가 우려가 있는 시점에 진입한 점이 아쉽습니다."
    else:
        reasoning = "피투자인의 매수 시점은 적정 가치 구간이었던 것으로 판단됩니다."
    
    # 권고사항
    if return_pct < -15:
        recommendation = "향후 손절 타이밍을 신중히 고려하고, 위험 관리 원칙을 재정립할 것을 권고합니다."
    elif return_pct > 15:
        recommendation = "우수한 성과를 거두었으나, 이익 실현 시점을 고려해볼 것을 제안합니다."
    else:
        recommendation = "현 보유 지속 또는 추가 매수 기회를 모색해볼 것을 권고합니다."
    
    verdict_document = f"""
{verdict_icon} [Fin문철 판결문]

**사건명:** {stock_name} 투자 판단 적정성 심사
**판결일:** {datetime.now().strftime("%Y년 %m월 %d일")}

**사실관계:**
- 매수일: {purchase_date}
- 매수가: {purchase_price:,.0f}원
- 현재가: {current_price:,.0f}원
- 수익률: {return_pct:+.1f}%

**판결 요지:**
{reasoning}

**종합 판단:** {verdict_type}

**권고사항:**
{recommendation}

**재판장 Fin문철**
"투자에는 완벽한 답이 없으나, 합리적 근거는 반드시 필요하다."

더 궁금하신가요?
"""
    
    return verdict_document.strip()


# Task5 함수 매핑
task5_py_funcs = {
    "analyze_investment_decision": analyze_investment_decision,
    "check_current_investment_worthiness": check_current_investment_worthiness,
    "generate_investment_verdict": generate_investment_verdict
}

# Task5 함수 스키마 정의
task5_funcs_schema = [
    {
        "name": "analyze_investment_decision",
        "description": (
            "투자 블랙박스 해부: 특정 시점의 매수 판단을 분석합니다. "
            "해당 시점의 PER/PBR, 애널리스트 의견, 뉴스 등을 종합하여 "
            "매수 판단이 합리적이었는지 AI가 평가합니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "stock_name": {
                    "type": "string", 
                    "description": "분석할 종목명 (예: 삼성전자, 애플)"
                },
                "purchase_date": {
                    "type": "string", 
                    "format": "date",
                    "description": "매수 날짜 (YYYY-MM-DD 형식)"
                },
                "purchase_price": {
                    "type": "number",
                    "description": "매수 가격 (원 단위, 선택사항)"
                }
            },
            "required": ["stock_name", "purchase_date"]
        }
    },
    {
        "name": "check_current_investment_worthiness", 
        "description": (
            "사전 진단: 현재 시점에서 해당 종목의 투자 가치를 분석합니다. "
            "실시간 밸류에이션, 애널리스트 의견, 뉴스 등을 종합하여 "
            "지금 매수해도 되는지 AI가 판단합니다."
        ),
        "parameters": {
            "type": "object", 
            "properties": {
                "stock_name": {
                    "type": "string",
                    "description": "분석할 종목명 (예: 한화솔루션, 테슬라)"
                }
            },
            "required": ["stock_name"]
        }
    },
    {
        "name": "generate_investment_verdict",
        "description": (
            "AI 판결 시스템: 매수 판단에 대해 법정 스타일로 평가합니다. "
            "투자 근거의 타당성을 분석하여 '정당/불충분/무모' 등으로 "
            "판결문 형태의 결과를 제공합니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "stock_name": {
                    "type": "string",
                    "description": "종목명"
                },
                "purchase_date": {
                    "type": "string",
                    "format": "date", 
                    "description": "매수 날짜"
                },
                "purchase_price": {
                    "type": "number",
                    "description": "매수 가격"
                },
                "current_performance": {
                    "type": "string",
                    "description": "현재 수익률 정보 (선택사항)"
                }
            },
            "required": ["stock_name", "purchase_date", "purchase_price"]
        }
    }
]


# 추가 유틸리티 함수들

def extract_company_name_from_query(query: str) -> str:
    """질문에서 종목명 추출"""
    # 간단한 종목명 추출 로직 (실제로는 더 정교한 NLP 필요)
    import re
    
    # 일반적인 종목명 패턴 매칭
    patterns = [
        r'([가-힣]+전자)',
        r'([가-힣]+화학)', 
        r'([가-힣]+솔루션)',
        r'([가-힣]+바이오)',
        r'([A-Z]+)',  # 영문 종목명
    ]
    
    for pattern in patterns:
        match = re.search(pattern, query)
        if match:
            return match.group(1)
    
    return ""


# def detect_query_intent(query: str) -> str:
#     """질문 의도 파악"""
    
#     # 과거 매수 분석 키워드
#     past_keywords = ["매수한", "샀", "산", "매입한", "투자한", "잘 산", "판단"]
    
#     # 현재 투자 문의 키워드  
#     current_keywords = ["지금", "현재", "사도", "매수해도", "투자해도", "어때"]
    
#     # 판결 요청 키워드
#     verdict_keywords = ["판단", "평가", "판결", "어떻게", "잘못", "실수"]
    
#     query_lower = query.lower()
    
#     if any(keyword in query_lower for keyword in past_keywords):
#         return "past_analysis"
#     elif any(keyword in query_lower for keyword in current_keywords):
#         return "current_analysis" 
#     elif any(keyword in query_lower for keyword in verdict_keywords):
#         return "verdict_request"
#     else:
#         return "general_inquiry"

async def get_intent_from_llm(query: str) -> str:
    """HCX를 통한 질문 의도 추론"""
    prompt = [
        {"role": "system", "content": (
            "다음 사용자 질문의 의도를 'past_analysis', 'current_analysis', 'verdict_request', 'general_inquiry' 중 하나로 분류하세요.\n"
            "- past_analysis: 과거에 샀던 종목의 투자 타당성 평가 요청\n"
            "- current_analysis: 지금 사도 될지 투자 가치 분석 요청\n"
            "- verdict_request: 판결문 형태로 매수 판단을 평가해달라는 요청\n"
            "- general_inquiry: 위 세 가지에 해당하지 않는 질문\n"
            "정답은 반드시 JSON 형식으로 반환하세요. 예: {\"intent\": \"past_analysis\"}"
        )},
        {"role": "user", "content": query}
    ]

    intent_data = {
        "model": "HCX-005",
        "messages": prompt,
        "temperature": 0.0
    }

    response = requests.post(url, headers=headers, json=intent_data)
    intent_json = response.json()
    try:
        intent = json.loads(intent_json["result"]["message"]["content"])["intent"]
    except Exception:
        intent = "general_inquiry"
    
    return intent



def get_market_sentiment_indicators() -> Dict[str, Any]:
    """시장 심리 지표 수집 (VIX, 공포/탐욕 지수 등)"""
    try:
        # VIX 지수 (공포 지수)
        vix = yf.Ticker("^VIX")
        vix_data = vix.history(period="5d")
        current_vix = vix_data["Close"].iloc[-1] if not vix_data.empty else None
        
        # 원달러 환율
        usdkrw = yf.Ticker("USDKRW=X")
        krw_data = usdkrw.history(period="5d") 
        current_usdkrw = krw_data["Close"].iloc[-1] if not krw_data.empty else None
        
        # 시장 심리 해석
        sentiment = "중립"
        if current_vix:
            if current_vix > 30:
                sentiment = "극도의 공포"
            elif current_vix > 20:
                sentiment = "공포"
            elif current_vix < 12:
                sentiment = "과도한 낙관"
            else:
                sentiment = "안정"
        
        return {
            "vix": current_vix,
            "usd_krw": current_usdkrw,
            "market_sentiment": sentiment,
            "fear_greed_level": _calculate_fear_greed_score(current_vix)
        }
        
    except Exception as e:
        return {"error": f"시장 지표 수집 오류: {str(e)}"}


def _calculate_fear_greed_score(vix_value: float) -> str:
    """VIX 기반 공포/탐욕 점수 계산"""
    if not vix_value:
        return "정보 없음"
    
    if vix_value > 35:
        return "극도의 공포 (90-100점)"
    elif vix_value > 25:
        return "공포 (75-89점)"
    elif vix_value > 20:
        return "불안 (50-74점)" 
    elif vix_value > 15:
        return "중립 (25-49점)"
    elif vix_value > 12:
        return "탐욕 (10-24점)"
    else:
        return "극도의 탐욕 (0-9점)"


def get_industry_comparison(stock_name: str, ticker: str) -> Dict[str, Any]:
    """동종업계 비교 분석"""
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        sector = info.get("sector", "")
        industry = info.get("industry", "")
        
        # 업종 평균 PER/PBR (실제로는 별도 DB나 API 필요)
        industry_averages = {
            "Technology": {"avg_pe": 25.0, "avg_pb": 3.5},
            "Healthcare": {"avg_pe": 22.0, "avg_pb": 2.8},
            "Financial Services": {"avg_pe": 12.0, "avg_pb": 1.2},
            "Consumer Cyclical": {"avg_pe": 18.0, "avg_pb": 2.1},
            "Energy": {"avg_pe": 15.0, "avg_pb": 1.8}
        }
        
        current_pe = info.get("trailingPE")
        current_pb = info.get("priceToBook")
        
        comparison_result = {
            "sector": sector,
            "industry": industry,
            "current_pe": current_pe,
            "current_pb": current_pb
        }
        
        if sector in industry_averages:
            avg_data = industry_averages[sector]
            comparison_result.update({
                "industry_avg_pe": avg_data["avg_pe"],
                "industry_avg_pb": avg_data["avg_pb"],
                "pe_vs_industry": "저평가" if current_pe and current_pe < avg_data["avg_pe"] else "고평가",
                "pb_vs_industry": "저평가" if current_pb and current_pb < avg_data["avg_pb"] else "고평가"
            })
        
        return comparison_result
        
    except Exception as e:
        return {"error": f"업종 비교 분석 오류: {str(e)}"}


def generate_comprehensive_report(stock_name: str, analysis_type: str = "full") -> str:
    """종합 투자 리포트 생성"""
    
    ticker = name_to_ticker(stock_name)
    if not ticker:
        return f"❌ '{stock_name}' 종목을 찾을 수 없습니다."
    
    try:
        # 1. 기본 정보 수집
        today = datetime.now().strftime("%Y-%m-%d")
        blackbox = InvestmentBlackBox()
        stock_info = blackbox._get_stock_info_at_date(ticker, today)
        
        # 2. 시장 심리 지표
        market_sentiment = get_market_sentiment_indicators()
        
        # 3. 업종 비교
        industry_comp = get_industry_comparison(stock_name, ticker)
        
        # 4. 종합 리포트 작성
        report = f"""
📊 **{stock_name} 종합 투자 분석 리포트**
생성일: {datetime.now().strftime("%Y년 %m월 %d일")}

**1. 기본 정보**
- 현재가: {stock_info.get('price', {}).get('close', 0):,.0f}원
- 업종: {industry_comp.get('sector', 'N/A')}
- PER: {stock_info.get('valuation', {}).get('pe_ratio', 'N/A')}
- PBR: {stock_info.get('valuation', {}).get('pb_ratio', 'N/A')}

**2. 시장 환경**
- VIX 지수: {market_sentiment.get('vix', 'N/A')}
- 시장 심리: {market_sentiment.get('market_sentiment', 'N/A')}
- 원달러 환율: {market_sentiment.get('usd_krw', 'N/A')}

**3. 업종 대비 평가**
- 섹터 평균 PER 대비: {industry_comp.get('pe_vs_industry', 'N/A')}
- 섹터 평균 PBR 대비: {industry_comp.get('pb_vs_industry', 'N/A')}

**4. 최종 투자 의견**
[종합 분석 결과는 check_current_investment_worthiness 함수 참조]

더 궁금하신가요?
"""
        
        return report.strip()
        
    except Exception as e:
        return f"❌ 리포트 생성 중 오류: {str(e)}"



# Task5 전용 유틸리티 함수들

def extract_multiple_stocks(query: str) -> list:
    """질문에서 여러 종목명 추출"""
    
    # 한국 주식 패턴
    korean_patterns = [
        r'([가-힣]+(?:전자|화학|물산|건설|금융|보험|증권|카드|은행|통신|에너지|바이오|제약|식품|유통|항공|해운|철강|자동차|반도체|디스플레이))',
        r'([가-힣]{2,}(?:그룹|홀딩스|솔루션|테크|시스템|소프트))',
        r'([가-힣]{2,6})'  # 일반적인 한글 종목명
    ]
    
    # 해외 주식 패턴
    foreign_patterns = [
        r'\b([A-Z]{1,5})\b',  # 티커 (예: AAPL, TSLA)
        r'\b([A-Za-z]+(?:\s+[A-Za-z]+)*)\b'  # 회사명 (예: Apple, Tesla Motors)
    ]
    
    found_stocks = []
    
    # 한국 종목 검색
    for pattern in korean_patterns:
        matches = re.findall(pattern, query)
        found_stocks.extend(matches)
    
    # 해외 종목 검색 (조건부)
    if not found_stocks:  # 한국 종목이 없을 때만
        for pattern in foreign_patterns:
            matches = re.findall(pattern, query)
            # 길이 필터링 (너무 짧거나 긴 것 제외)
            filtered_matches = [m for m in matches if 2 <= len(m) <= 20]
            found_stocks.extend(filtered_matches)
    
    # 중복 제거 및 정리
    unique_stocks = list(set(found_stocks))
    
    return unique_stocks[:3]  # 최대 3개까지만 반환


def analyze_query_complexity(query: str) -> Dict[str, Any]:
    """질문 복잡도 및 요구사항 분석"""
    
    complexity_indicators = {
        "simple": ["어때", "괜찮", "좋아", "나빠"],
        "detailed": ["분석", "자세히", "상세히", "구체적"],
        "comparative": ["비교", "대비", "vs", "차이"],
        "predictive": ["전망", "예상", "미래", "앞으로"]
    }
    
    analysis = {
        "complexity_level": "simple",
        "requires_comparison": False,
        "requires_prediction": False,
        "multiple_stocks": False,
        "time_specific": False
    }
    
    query_lower = query.lower()
    
    # 복잡도 레벨 판단
    for level, keywords in complexity_indicators.items():
        if any(keyword in query_lower for keyword in keywords):
            analysis["complexity_level"] = level
            break
    
    # 특수 요구사항 체크
    if any(word in query_lower for word in ["비교", "대비", "vs"]):
        analysis["requires_comparison"] = True
    
    if any(word in query_lower for word in ["전망", "예상", "미래"]):
        analysis["requires_prediction"] = True
    
    # 여러 종목 언급 체크
    stocks = extract_multiple_stocks(query)
    if len(stocks) > 1:
        analysis["multiple_stocks"] = True
    
    # 시간 특정성 체크
    time_keywords = ["오늘", "어제", "내일", "이번주", "다음주", "월", "년"]
    if any(keyword in query for keyword in time_keywords):
        analysis["time_specific"] = True
    
    return analysis
