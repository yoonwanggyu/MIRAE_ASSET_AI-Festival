"""
투자대법관 도와줘! Fin문철의 블랙박스
투자 판단을 객관적으로 분석하고 가이드하는 AI 투자 비서
"""

import os
import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from typing import Dict, List

from langchain_naver import ChatClovaX
from langchain.prompts import PromptTemplate
from langchain.schema import HumanMessage

# dotenv 추가
import dotenv
dotenv.load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="투자대법관 도와줘! Fin문철의 블랙박스",
    page_icon="📈",
    layout="wide"
)

class StockDataFetcher:
    """주식 데이터 수집 클래스"""
    
    @staticmethod
    def get_stock_info(symbol: str) -> Dict:
        """주식 기본 정보 조회"""
        try:
            # 한국 주식의 경우 .KS 추가
            if not '.' in symbol:
                symbol = f"{symbol}.KS"
            
            stock = yf.Ticker(symbol)
            info = stock.info
            
            # 최근 1년 데이터 조회
            
            hist = stock.history(period="1y")
            
            # 기술적 지표 계산
            current_price = hist['Close'][-1]
            sma_20 = hist['Close'].rolling(window=20).mean()[-1]
            sma_60 = hist['Close'].rolling(window=60).mean()[-1]
            
            # RSI 계산 (간단 버전)
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            return {
                'symbol': symbol,
                'company_name': info.get('longName', 'N/A'),
                'current_price': current_price,
                'market_cap': info.get('marketCap', 0),
                'pe_ratio': info.get('trailingPE', 0),
                'pb_ratio': info.get('priceToBook', 0),
                'dividend_yield': info.get('dividendYield', 0),
                'sma_20': sma_20,
                'sma_60': sma_60,
                'rsi': rsi[-1] if len(rsi) > 0 else 50,
                'volume': hist['Volume'][-1],
                'price_change_1d': ((current_price - hist['Close'][-2]) / hist['Close'][-2] * 100),
                'price_change_1w': ((current_price - hist['Close'][-5]) / hist['Close'][-5] * 100),
                'price_change_1m': ((current_price - hist['Close'][-21]) / hist['Close'][-21] * 100),
                'history': hist
            }
        except Exception as e:
            st.error(f"주식 데이터 조회 오류: {e}")
            return None

class InvestmentAnalyzer:
    """투자 분석 클래스"""
    
    def __init__(self):
        # Clova X 모델 초기화
        self.llm = ChatClovaX(
            api_key=os.getenv('NCP_CLOVASTUDIO_API_KEY'),
            model="HCX-005",
            temperature=0.3,
            max_tokens=3000,
        )
        
        self.analysis_prompt = PromptTemplate(
            input_variables=["stock_data", "user_query", "analysis_type"],
            template="""
당신은 전문적인 투자 분석가 "Fin문철"입니다. 사용자의 투자 판단을 블랙박스처럼 분해하여 객관적으로 분석해주세요.

**주식 데이터:**
{stock_data}

**사용자 질문:** {user_query}

**분석 유형:** {analysis_type}

다음 관점에서 종합적으로 분석해주세요:

**📊 정량적 분석 (Quantitative Analysis)**
1. 기술적 지표 분석 (RSI, 이동평균선 등)
2. 재무 지표 분석 (PER, PBR, 배당수익률 등)
3. 가격 변동성 및 거래량 분석

**📈 정성적 분석 (Qualitative Analysis)**
1. 현재 시장 상황 및 업종 전망
2. 회사 기본면 및 경쟁력
3. 리스크 요인 및 기회 요소

**🎯 투자 판단 종합 평가**
- 현재 가격의 적정성
- 투자 타이밍 평가
- 추천 투자 전략
- 위험도 평가 (1-10점)

**📋 블랙박스 분석 결과**
최종 평가: [매우 좋음/좋음/보통/주의/위험] 중 하나로 판단하고 근거를 명확히 제시해주세요.

투자는 본인의 판단과 책임입니다. 이 분석은 참고용이며 투자 권유가 아닙니다.
            """
        )
    
    def analyze_investment(self, stock_data: Dict, user_query: str, analysis_type: str = "종합분석") -> str:
        """투자 분석 수행"""
        try:
            # 주식 데이터를 텍스트로 변환
            stock_summary = f"""
종목명: {stock_data['company_name']} ({stock_data['symbol']})
현재가: {stock_data['current_price']:,.0f}원
시가총액: {stock_data['market_cap']:,}
PER: {stock_data['pe_ratio']:.2f}
PBR: {stock_data['pb_ratio']:.2f}
배당수익률: {stock_data['dividend_yield']*100:.2f}%
RSI: {stock_data['rsi']:.1f}
20일 이평: {stock_data['sma_20']:,.0f}원
60일 이평: {stock_data['sma_60']:,.0f}원
1일 변동률: {stock_data['price_change_1d']:+.2f}%
1주 변동률: {stock_data['price_change_1w']:+.2f}%
1개월 변동률: {stock_data['price_change_1m']:+.2f}%
거래량: {stock_data['volume']:,}주
            """
            
            prompt = self.analysis_prompt.format(
                stock_data=stock_summary,
                user_query=user_query,
                analysis_type=analysis_type
            )
            
            response = self.llm.invoke([HumanMessage(content=prompt)])
            return response.content
            
        except Exception as e:
            return f"분석 중 오류 발생: {e}"

class ScenarioSimulator:
    """시나리오 시뮬레이션 클래스"""
    
    @staticmethod
    def simulate_scenarios(stock_data: Dict, scenarios: List[Dict]) -> pd.DataFrame:
        """다양한 시나리오 하에서 주가 영향 시뮬레이션"""
        current_price = stock_data['current_price']
        results = []
        
        for scenario in scenarios:
            name = scenario['name']
            impact = scenario['impact']  # -0.2 ~ +0.3 등
            
            new_price = current_price * (1 + impact)
            change_pct = impact * 100
            
            results.append({
                '시나리오': name,
                '예상 주가': f"{new_price:,.0f}원",
                '변동률': f"{change_pct:+.1f}%",
                '영향도': '긍정적 🔺' if impact > 0 else '부정적 🔻' if impact < 0 else '중립적'
            })
        
        return pd.DataFrame(results)

def create_price_chart(stock_data: Dict) -> go.Figure:
    """주가 차트 생성"""
    hist = stock_data['history']
    
    fig = go.Figure()
    
    # 캔들스틱 차트
    fig.add_trace(go.Candlestick(
        x=hist.index,
        open=hist['Open'],
        high=hist['High'],
        low=hist['Low'],
        close=hist['Close'],
        name='주가'
    ))
    
    # 이동평균선
    fig.add_trace(go.Scatter(
        x=hist.index,
        y=hist['Close'].rolling(window=20).mean(),
        name='20일 이평선',
        line=dict(color='orange', width=2)
    ))
    
    fig.add_trace(go.Scatter(
        x=hist.index,
        y=hist['Close'].rolling(window=60).mean(),
        name='60일 이평선',
        line=dict(color='blue', width=2)
    ))
    
    fig.update_layout(
        title=f"{stock_data['company_name']} 주가 차트",
        yaxis_title="주가 (원)",
        xaxis_title="날짜",
        height=400,
        xaxis_rangeslider_visible=False
    )
    
    return fig

def main():
    st.title("📈 투자대법관 도와줘! Fin문철의 블랙박스")
    st.markdown("### 🔍 투자 판단을 객관적으로 분석하는 AI 투자 비서")
    
    # API 키 확인
    if not os.getenv('NCP_CLOVASTUDIO_API_KEY'):
        st.error("NCP_CLOVASTUDIO_API_KEY 환경변수를 설정해주세요.")
        st.stop()
    
    # 세션 상태 초기화
    if 'analyzer' not in st.session_state:
        st.session_state.analyzer = InvestmentAnalyzer()
        st.session_state.fetcher = StockDataFetcher()
        st.session_state.simulator = ScenarioSimulator()
    
    # 사이드바 - 분석 옵션
    st.sidebar.header("🛠️ 분석 설정")
    
    # 종목 입력
    stock_symbol = st.sidebar.text_input(
        "종목 코드 입력",
        value="005930",  # 삼성전자 기본값
        help="예: 005930 (삼성전자), 000660 (SK하이닉스)"
    )
    
    analysis_type = st.sidebar.selectbox(
        "분석 유형 선택",
        ["종합분석", "기술적 분석", "기본면 분석", "시나리오 분석"]
    )
    
    # 예제 질문
    st.sidebar.header("💡 예제 질문")
    examples = [
        "삼성전자 7만원에 매수한 판단 어때?",
        "지금 매수 타이밍이 맞나?",
        "향후 3개월 전망은?",
        "리스크 요인이 뭐야?"
    ]
    
    for i, example in enumerate(examples):
        if st.sidebar.button(f"예제 {i+1}", key=f"example_{i}"):
            st.session_state.user_query = example
    
    # 메인 영역
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # 사용자 질문 입력
        user_query = st.text_area(
            "💬 투자 관련 질문을 입력하세요:",
            value=getattr(st.session_state, 'user_query', ''),
            height=100,
            placeholder="예: 삼성전자를 7만원에 매수한 판단이 어떤가요?"
        )
        
        if st.button("🔍 투자 분석 시작", type="primary"):
            if user_query and stock_symbol:
                with st.spinner("📊 투자 데이터 분석 중..."):
                    # 주식 데이터 조회
                    stock_data = st.session_state.fetcher.get_stock_info(stock_symbol)
                    
                    if stock_data:
                        # 투자 분석 수행
                        analysis_result = st.session_state.analyzer.analyze_investment(
                            stock_data, user_query, analysis_type
                        )
                        
                        # 결과 표시
                        st.success("✅ Fin문철의 블랙박스 분석 완료!")
                        
                        # 분석 결과
                        st.markdown("### 📋 블랙박스 분석 결과")
                        st.markdown(analysis_result)
                        
                        # 주요 지표 표시
                        col1_metric, col2_metric, col3_metric, col4_metric = st.columns(4)
                        
                        with col1_metric:
                            st.metric(
                                "현재가", 
                                f"{stock_data['current_price']:,.0f}원",
                                f"{stock_data['price_change_1d']:+.2f}%"
                            )
                        
                        with col2_metric:
                            st.metric("PER", f"{stock_data['pe_ratio']:.2f}")
                        
                        with col3_metric:
                            st.metric("RSI", f"{stock_data['rsi']:.1f}")
                        
                        with col4_metric:
                            rsi_status = "과매수" if stock_data['rsi'] > 70 else "과매도" if stock_data['rsi'] < 30 else "중립"
                            st.metric("RSI 상태", rsi_status)
                        
                        # 주가 차트
                        st.markdown("### 📈 주가 차트 분석")
                        fig = create_price_chart(stock_data)
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # 시나리오 분석 (선택적)
                        if analysis_type == "시나리오 분석":
                            st.markdown("### 🎯 시나리오 시뮬레이션")
                            
                            scenarios = [
                                {"name": "기준 시나리오 (현재 유지)", "impact": 0.0},
                                {"name": "금리 0.5%p 상승", "impact": -0.15},
                                {"name": "GDP 0.5% 상승", "impact": 0.10},
                                {"name": "업종 호재 발생", "impact": 0.20},
                                {"name": "시장 충격 발생", "impact": -0.25}
                            ]
                            
                            scenario_df = st.session_state.simulator.simulate_scenarios(stock_data, scenarios)
                            st.dataframe(scenario_df, use_container_width=True)
                    
                    else:
                        st.error("주식 데이터를 조회할 수 없습니다. 종목 코드를 확인해주세요.")
            else:
                st.warning("종목 코드와 질문을 모두 입력해주세요.")

if __name__ == "__main__":
    main()