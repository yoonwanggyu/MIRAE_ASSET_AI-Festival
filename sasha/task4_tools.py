from utils import *
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf
from typing import Dict, Any, List, Tuple
import concurrent.futures
import numpy as np
import time
import random

# Task5 Function Definitions for Function Calling
task5_functions = [
    {
    "name": "clarify_recent_period",
    "description": "사용자가 '최근', '요즘', '근래' 등 모호한 시간 표현을 사용했을 때 구체적인 분석 기간을 확인하는 함수입니다. 정확한 주식 분석을 위해 명확한 기간 설정이 필요할 때 호출됩니다.",
            "parameters": {
            "type": "object",
            "properties": {
                "query_type": {
                    "type": "string",
                    "enum": ["recent_gainers", "recent_losers", "high_drop"],
                    "description": "질문 유형 분류: recent_gainers(최근 상승 종목), recent_losers(최근 하락 종목), high_drop(고점 대비 하락), volume_surge(거래량 급증), price_trend(가격 추세 분석)"
            },
                "suggested_period": {
                    "type": "integer",
                    "default": 30,
                    "description":"사용자에게 제안할 기본 분석 기간(일 단위). 일반적으로 30일(1개월)을 기본값으로 사용"
            },
              "context_hint": {
                "type": "string",
                "description": "사용자 질문의 맥락 정보. 예: '단기 투자', '장기 추세', '급등주 발굴' 등"
            }
                
            },
            "required": ["query_type"]
        }
    },
    {
        "name": "get_stock_ranking",
        "description": "지정된 기간과 기준에 따라 주식 순위를 조회하는 범용 함수입니다. 상승률, 하락률, 거래량, 시가총액 등 다양한 기준으로 상위/하위 종목을 조회할 수 있습니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "ranking_type": {
                    "type": "string",
                    "enum": [
                        "gain_rate",      # 상승률
                        "loss_rate",      # 하락률  
                        "volume",         # 거래량
                        "volume_change",  # 거래량 변화율
                        "market_cap",     # 시가총액
                        "price_high",     # 주가 (고가순)
                        "price_low",      # 주가 (저가순)
                        "volatility"      # 변동성
                    ],
                    "description": "순위 기준 지표: gain_rate(상승률), loss_rate(하락률), volume(거래량), volume_change(거래량변화율), market_cap(시가총액), price_high(고가순), price_low(저가순), volatility(변동성)"
                },
                "sort_order": {
                    "type": "string",
                    "enum": ["desc", "asc"],
                    "default": "desc",
                    "description": "정렬 순서: desc(내림차순-상위), asc(오름차순-하위)"
                },
                "end_date": {
                    "type": "string", 
                    "format": "date",
                    "description": "조회 기준 종료일 (YYYY-MM-DD 형식)"
                },
                "period_days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 365,
                    "default": 30,
                    "description": "분석 기간 (일 단위, 1-365일)"
                },
                "top_n": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 10,
                    "description": "조회할 종목 수 (1-100개)"
                },
                "market": {
                    "type": "string",
                    "enum": ["KOSPI", "KOSDAQ", "ALL"],
                    "default": "ALL",
                    "description": "대상 시장: KOSPI(코스피), KOSDAQ(코스닥), ALL(전체)"
                },
                "min_price": {
                    "type": "number",
                    "minimum": 0,
                    "description": "최소 주가 필터 (원 단위, 선택사항)"
                },
                "min_market_cap": {
                    "type": "number", 
                    "minimum": 0,
                    "description": "최소 시가총액 필터 (억원 단위, 선택사항)"
                }
            },
            "required": ["ranking_type", "end_date"]
        }
    },
    {
        "name": "get_stocks_from_extreme_point",
        "description": "고점 혹은 저점을 기준으로 많이 변화한 종목 조회",
        "parameters": {
            "type": "object",
            "properties": {
                "end_date": {"type": "string", "format": "date"},
                "lookback_days": {"type": "integer", "default": 252},
                "top_n": {"type": "integer", "default": 10},
                "market": {"type": "string", "enum": ["KOSPI", "KOSDAQ", "ALL"]},
                "extreme_type": {
                    "type": "string",
                    "enum": ["peak_to_now", "trough_to_now"],
                    "description": "고점→현재인지, 저점→현재인지"
                }
            },
            "required": ["end_date", "extreme_type"]
        }
    },
    {
        "name": "analyze_ambiguous_query",
        "description": "모호한 질문을 분석하고 구체적인 매개변수를 제안",
        "parameters": {
            "type": "object",
            "properties": {
                "user_query": {"type": "string"},
                "context": {"type": "string", "description": "이전 대화 맥락"}
            },
            "required": ["user_query"]
        }
    }
]

# Python Function Implementations
def clarify_recent_period(query_type: str, suggested_period: int = 30) -> str:
    """
    '최근'이라는 모호한 표현에 대해 구체적인 기간을 재질의하는 함수
    """
    query_descriptions = {
        "recent_gainers": "많이 오른 주식",
        "recent_losers": "많이 떨어진 주식", 
        "high_drop": "고점 대비 떨어진 주식"
    }
    
    query_desc = query_descriptions.get(query_type, "주식")
    
    return f"""'{query_desc}'을 찾기 위해 구체적인 기간이 필요합니다.

다음 중 원하시는 기간을 선택해 주세요:
1. 최근 1주일 (7일)
2. 최근 1개월 (30일) 
3. 최근 3개월 (90일)
4. 최근 6개월 (180일)
5. 최근 1년 (252일)

또는 "YYYY-MM-DD부터 YYYY-MM-DD까지" 형식으로 직접 기간을 지정해 주세요.

예시: "최근 30일간 많이 오른 주식을 보여줘" 또는 "2024-01-01부터 2024-12-31까지 상승률 상위 10개 종목"

더 궁금하신가요?
"""


def get_stocks_from_extreme_point(
    end_date: str,
    lookback_days: int = 252,
    top_n: int = 10,
    market: str = "ALL",
    extreme_type: str = "peak_to_now"
) -> str:
    """
    고점 또는 저점을 기준으로 현재까지 가장 많이 변화한 종목 조회
    extreme_type: 
        - "peak_to_now" → 고점 대비 하락률
        - "trough_to_now" → 저점 대비 상승률
    """
    try:
        today = datetime.now()
        end_dt = pd.to_datetime(end_date)
        if end_dt > today:
            end_dt = today
            end_date = today.strftime("%Y-%m-%d")

        # 종목 리스트 로드
        try:
            tickers_df = pd.read_csv(
                "/mnt/c/Users/rladl/Desktop/Mirae_Agent/MIRAE_ASSET_AI-Festival/sasha/test/krx_tickers_cleaned.csv",
                dtype={"code": str}
            )
        except FileNotFoundError:
            return "❌ 종목 리스트 파일을 찾을 수 없습니다."

        if market.upper() != "ALL":
            tickers_df = tickers_df[tickers_df["market"].str.upper() == market.upper()]
        if tickers_df.empty:
            return f"❌ '{market}' 시장에 해당하는 종목이 없습니다."

        # 티커 샘플링
        max_tickers = 500
        if len(tickers_df) > max_tickers:
            tickers_df = tickers_df.sample(n=max_tickers, random_state=42)

        tickers_df["yf_ticker"] = tickers_df.apply(
            lambda x: f"{x['code']}.KS" if x['market'].upper() == "KOSPI" else f"{x['code']}.KQ",
            axis=1
        )
        tickers = tickers_df["yf_ticker"].tolist()

        # 병렬 실행
        results = []
        batch_size = 50
        max_workers = 3

        print(f"🔍 종목 변화율 분석 시작 ({extreme_type})...")

        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for i in range(0, len(tickers), batch_size):
                batch = tickers[i:i + batch_size]
                future = executor.submit(
                    _calculate_extreme_change_safe,
                    batch, end_dt, lookback_days, extreme_type
                )
                futures.append(future)
                if i > 0:
                    time.sleep(random.uniform(1, 3))

            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                try:
                    batch_results = future.result()
                    results.extend(batch_results)
                    print(f"✅ 배치 {i+1}/{len(futures)} 완료")
                except Exception as e:
                    print(f"⚠️ 배치 {i+1} 오류: {str(e)}")

        if not results:
            return f"❌ {end_date} 기준 결과를 불러올 수 없습니다."

        # 정렬 기준 (하락률은 오름차순, 상승률은 내림차순)
        if extreme_type == "peak_to_now":
            results.sort(key=lambda x: x[2])  # 가장 많이 떨어진 순
        elif extreme_type == "trough_to_now":
            results.sort(key=lambda x: x[2], reverse=True)  # 가장 많이 오른 순

        top_results = results[:top_n]

        # 메시지 생성
        direction = "하락률" if extreme_type == "peak_to_now" else "상승률"
        arrow = "▼" if extreme_type == "peak_to_now" else "▲"

        lines = [
            f"📈 {end_date} 기준 최근 {lookback_days}일 기준 {direction} 상위 {min(top_n, len(top_results))}개 종목:",
            f"(총 {len(results)}개 종목 중 분석)\n"
        ]

        for i, (ticker, name, change_pct) in enumerate(top_results):
            lines.append(f"{i+1}. {name}({ticker.split('.')[0]}) {arrow} {abs(change_pct):.2f}%")

        lines.append("\n더 궁금하신가요?")
        return "\n".join(lines)

    except Exception as e:
        return f"❌ 데이터 조회 중 오류가 발생했습니다: {str(e)}"

def get_stock_ranking(ranking_type: str, end_date: str, period_days: int = 30, 
                     top_n: int = 10, market: str = "ALL", sort_order: str = "desc",
                     min_price: float = None, min_market_cap: float = None) -> str:
    """
    지정된 기간과 기준에 따라 주식 순위를 조회하는 범용 함수
    """
    try:
        # 현재 시간 기준으로 조정 (미래 날짜 방지)
        today = datetime.now()
        end_dt = pd.to_datetime(end_date)
        
        if end_dt > today:
            end_dt = today
            end_date = today.strftime("%Y-%m-%d")
        
        # 순위 기준별 설정
        ranking_config = {
            "gain_rate": {"label": "상승률", "unit": "%", "reverse": True},
            "loss_rate": {"label": "하락률", "unit": "%", "reverse": False},
            "volume": {"label": "거래량", "unit": "주", "reverse": True},
            "volume_change": {"label": "거래량변화율", "unit": "%", "reverse": True},
            "market_cap": {"label": "시가총액", "unit": "억원", "reverse": True},
            "price_high": {"label": "주가(고가순)", "unit": "원", "reverse": True},
            "price_low": {"label": "주가(저가순)", "unit": "원", "reverse": False},
            "volatility": {"label": "변동성", "unit": "%", "reverse": True}
        }
        
        if ranking_type not in ranking_config:
            return f"❌ 지원하지 않는 순위 기준입니다: {ranking_type}"
        
        config = ranking_config[ranking_type]
        
        # 종목 리스트 로드
        try:
            tickers_df = pd.read_csv(
                "/mnt/c/Users/rladl/Desktop/Mirae_Agent/MIRAE_ASSET_AI-Festival/sasha/test/krx_tickers_cleaned.csv",
                dtype={"code": str}
            )
        except FileNotFoundError:
            try:
                tickers_df = pd.read_csv(
                    "/Users/yoon/MIRAE_ASSET_AI-Festival/krx_tickers.csv",
                    dtype={"code": str}
                )
            except FileNotFoundError:
                return "❌ 종목 리스트 파일을 찾을 수 없습니다."
        
        # 시장 필터링
        if market.upper() != "ALL":
            tickers_df = tickers_df[tickers_df["market"].str.upper() == market.upper()]
        
        # 샘플링 (성능 최적화)
        max_tickers = 500
        if len(tickers_df) > max_tickers:
            tickers_df = tickers_df.sample(n=max_tickers, random_state=42)
        
        tickers_df["yf_ticker"] = tickers_df.apply(
            lambda x: f"{x['code']}.KS" if x['market'].upper() == "KOSPI" else f"{x['code']}.KQ", 
            axis=1
        )
        
        tickers = tickers_df["yf_ticker"].tolist()
        
        # 배치 처리
        results = []
        batch_size = 50
        max_workers = 3
        
        print(f"총 {len(tickers)}개 종목을 {len(tickers)//batch_size + 1}개 배치로 처리합니다...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for i in range(0, len(tickers), batch_size):
                batch = tickers[i:i+batch_size]
                future = executor.submit(
                    _download_and_calculate_metrics, 
                    batch, end_dt, period_days, ranking_type, min_price, min_market_cap
                )
                futures.append(future)
                
                if i > 0:
                    time.sleep(random.uniform(1, 3))
            
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                try:
                    batch_results = future.result()
                    results.extend(batch_results)
                    print(f"배치 {i+1}/{len(futures)} 완료: {len(batch_results)}개 종목 처리됨")
                except Exception as e:
                    print(f"배치 {i+1} 처리 중 오류: {str(e)}")
                    continue
        
        if not results:
            return f"❌ {end_date} 기준 {period_days}일간 {config['label']} 데이터를 불러올 수 없습니다."
        
        # 정렬 (sort_order 파라미터 적용)
        reverse_sort = (sort_order == "desc") == config["reverse"]
        results.sort(key=lambda x: x[2], reverse=reverse_sort)
        top_results = results[:top_n]
        
        # 결과 포맷팅
        order_label = "상위" if sort_order == "desc" else "하위"
        lines = [f"{config['symbol']} {end_date} 기준 최근 {period_days}일간 {config['label']} {order_label} {min(top_n, len(top_results))}개 종목:"]
        lines.append(f"(총 {len(results)}개 종목 중 분석)\n")
        
        for i, (ticker, name, value) in enumerate(top_results):
            if config["unit"] == "주":
                value_str = f"{int(value):,}{config['unit']}"
            elif config["unit"] == "원" or config["unit"] == "억원":
                value_str = f"{value:,.0f}{config['unit']}"
            else:  # 퍼센트
                # 상승률/하락률은 값에 따라 심볼 결정
                if ranking_type in ["gain_rate", "loss_rate"]:
                    symbol = "▲" if value >= 0 else "▼"
                    value_str = f"{symbol} {value:.2f}{config['unit']}"
                else:
                    value_str = f"{value:.2f}{config['unit']}"
            
            lines.append(f"{i+1}. {name}({ticker.split('.')[0]}) {value_str}")
        
        lines.append(f"\n더 궁금하신가요?")
        return "\n".join(lines)
        
    except Exception as e:
        return f"❌ 데이터 조회 중 오류가 발생했습니다: {str(e)}\n\n더 궁금하신가요?"


def _download_and_calculate_metrics(tickers: list, end_dt: pd.Timestamp, period_days: int, 
                                   ranking_type: str, min_price: float = None, 
                                   min_market_cap: float = None) -> list:
    """
    배치별 데이터 다운로드 및 지표 계산
    """
    results = []
    start_dt = end_dt - pd.Timedelta(days=period_days + 10)  # 여유 기간
    
    try:
        # Yahoo Finance 데이터 다운로드
        data = yf.download(
            tickers,
            start=start_dt.strftime("%Y-%m-%d"),
            end=(end_dt + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
            group_by="ticker",
            progress=False,
            threads=False
        )
        
        if data.empty:
            return results
        
        for ticker in tickers:
            try:
                if len(tickers) == 1:
                    stock_data = data
                else:
                    stock_data = data[ticker]
                
                if stock_data.empty:
                    continue
                
                # 기본 필터링
                latest_price = stock_data["Close"].iloc[-1] if not stock_data["Close"].empty else None
                if min_price and (latest_price is None or latest_price < min_price):
                    continue
                
                # 지표별 계산
                value = _calculate_metric(stock_data, ranking_type, period_days, min_market_cap)
                if value is None:
                    continue
                
                # 종목명 조회
                code = ticker.split('.')[0]
                name = ticker_to_name(code) or code
                
                results.append((ticker, name, value))
                
            except Exception as e:
                print(f"종목 {ticker} 처리 중 오류: {e}")
                continue
                
    except Exception as e:
        print(f"배치 다운로드 오류: {e}")
    
    return results


def _calculate_metric(stock_data: pd.DataFrame, ranking_type: str, period_days: int, 
                     min_market_cap: float = None) -> float:
    """
    순위 기준별 지표 계산
    """
    try:
        if stock_data.empty or len(stock_data) < 2:
            return None
        
        if ranking_type == "gain_rate" or ranking_type == "loss_rate":
            # 수익률 계산
            start_price = stock_data["Close"].iloc[0]
            end_price = stock_data["Close"].iloc[-1]
            if pd.isna(start_price) or pd.isna(end_price) or start_price <= 0:
                return None
            return ((end_price / start_price) - 1) * 100
        
        elif ranking_type == "volume":
            # 평균 거래량
            return stock_data["Volume"].mean()
        
        elif ranking_type == "volume_change":
            # 거래량 변화율
            if len(stock_data) < period_days // 2:
                return None
            early_vol = stock_data["Volume"].iloc[:len(stock_data)//2].mean()
            recent_vol = stock_data["Volume"].iloc[len(stock_data)//2:].mean()
            if early_vol <= 0:
                return None
            return ((recent_vol / early_vol) - 1) * 100
        
        elif ranking_type == "market_cap":
            # 시가총액 (단순 계산: 최근 종가 * 상장주식수 추정)
            latest_price = stock_data["Close"].iloc[-1]
            avg_volume = stock_data["Volume"].mean()
            estimated_shares = avg_volume * 1000  # 추정치
            market_cap = latest_price * estimated_shares / 100000000  # 억원 단위
            
            if min_market_cap and market_cap < min_market_cap:
                return None
            return market_cap
        
        elif ranking_type == "price_high" or ranking_type == "price_low":
            # 최근 종가
            return stock_data["Close"].iloc[-1]
        
        elif ranking_type == "volatility":
            # 변동성 (표준편차)
            returns = stock_data["Close"].pct_change().dropna()
            return returns.std() * 100
        
        return None
        
    except Exception as e:
        print(f"지표 계산 오류: {e}")
        return None

def analyze_ambiguous_query(user_query: str, context: str = "") -> str:
    """
    모호한 질문을 분석하고 구체적인 매개변수를 제안
    """
    query_lower = user_query.lower()
    
    # 키워드 매핑
    ambiguous_patterns = {
        "많이 오른": {
            "type": "recent_gainers",
            "description": "상승률이 높은 종목",
            "default_period": 30,
            "threshold": "상위 10개"
        },
        "많이 떨어진": {
            "type": "recent_losers", 
            "description": "하락률이 높은 종목",
            "default_period": 30,
            "threshold": "하위 10개"
        },
        "고점 대비": {
            "type": "high_drop",
            "description": "최근 고점 대비 하락한 종목",
            "default_period": 252,
            "threshold": "하락률 상위 10개"
        },
        "급등": {
            "type": "recent_gainers",
            "description": "단기간 급상승한 종목", 
            "default_period": 7,
            "threshold": "상위 5개"
        },
        "급락": {
            "type": "recent_losers",
            "description": "단기간 급하락한 종목",
            "default_period": 7, 
            "threshold": "하위 5개"
        }
    }
    
    detected_pattern = None
    for pattern, info in ambiguous_patterns.items():
        if pattern in query_lower:
            detected_pattern = info
            break
    
    if not detected_pattern:
        return """질문을 좀 더 구체적으로 말씀해 주세요.

다음과 같은 정보가 필요합니다:
1. 기간: "최근 30일", "1개월", "3개월" 등
2. 조건: "상승률", "하락률", "거래량" 등
3. 개수: "상위 10개", "5개" 등

예시:
- "최근 1개월간 상승률 상위 10개 종목"
- "최근 3개월간 고점 대비 하락률이 큰 5개 종목"

더 궁금하신가요?
"""
    
    return f"""'{detected_pattern['description']}'을 조회하기 위해 다음 정보를 확인해 주세요:

🔍 **분석 조건 제안:**
- 기본 조회 기간: 최근 {detected_pattern['default_period']}일
- 결과 개수: {detected_pattern['threshold']}
- 대상 시장: 전체 (KOSPI + KOSDAQ)

**구체적으로 다시 질문해 주세요:**
예시: "최근 {detected_pattern['default_period']}일간 {detected_pattern['description']} {detected_pattern['threshold']}를 보여줘"

또는 원하시는 기간과 개수를 직접 지정해 주세요:
- "최근 7일간..." (단기)
- "최근 90일간..." (장기)
- "상위 5개..." (소수 정예)
- "상위 20개..." (많은 종목)

더 궁금하신가요?
"""

def _calculate_extreme_change_safe(tickers, end_dt, lookback_days, extreme_type):
    results = []
    for ticker in tickers:
        try:
            df = yf.download(ticker, end=end_dt.strftime('%Y-%m-%d'), period=f"{lookback_days}d", progress=False)
            if df.empty:
                continue
            close_prices = df["Close"]

            current_price = close_prices.iloc[-1]
            if extreme_type == "peak_to_now":
                extreme_price = close_prices.max()
            elif extreme_type == "trough_to_now":
                extreme_price = close_prices.min()
            else:
                continue

            change_pct = (current_price - extreme_price) / extreme_price * 100
            name = ticker.split('.')[0]
            results.append((ticker, name, change_pct))

        except Exception:
            continue
    return results

# Task5 함수 매핑
task5_py_funcs: Dict[str, Any] = {
    "clarify_recent_period": clarify_recent_period,
    "get_stock_ranking": get_stock_ranking,
    "get_stocks_from_extreme_point": get_stocks_from_extreme_point,
    "analyze_ambiguous_query": analyze_ambiguous_query
}