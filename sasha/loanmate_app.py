"""
LoanMate - 당신의 금융 계산 파트너
자연어 질의를 수학식으로 변환하여 금융 계산을 수행하는 애플리케이션
"""

import os
import streamlit as st
# import pandas as pd
import plotly.graph_objects as go
# import plotly.express as px
from typing import Dict, List, Optional
# import sympy as sp
# import numpy as np
from langchain_naver import ChatClovaX
from langchain.prompts import PromptTemplate
from langchain.schema import HumanMessage

import dotenv

dotenv.load_dotenv()

# 페이지 설정
st.set_page_config(
    page_title="LoanMate - 금융 계산 파트너",
    page_icon="💰",
    layout="wide"
)

class FinancialCalculator:
    """금융 계산 클래스"""
    
    @staticmethod
    def compound_interest(principal, rate, time):
        """복리 계산: A = P(1 + r)^t"""
        return principal * (1 + rate) ** time
    
    @staticmethod
    def simple_interest(principal, rate, time):
        """단리 계산: A = P(1 + rt)"""
        return principal * (1 + rate * time)
    
    @staticmethod
    def equal_payment_loan(principal, rate, time_years):
        """원리금균등상환 월납부액"""
        if rate == 0:
            return principal / (time_years * 12)
        
        monthly_rate = rate / 12
        n_payments = time_years * 12
        
        payment = principal * (monthly_rate * (1 + monthly_rate) ** n_payments) / \
                 ((1 + monthly_rate) ** n_payments - 1)
        return payment
    
    @staticmethod
    def bullet_payment_interest(principal, rate, time_years):
        """만기일시상환 총이자"""
        return principal * rate * time_years
    
    @staticmethod
    def max_loan_amount(monthly_payment, rate, time_years):
        """월납부액으로 가능한 최대 대출금액"""
        if rate == 0:
            return monthly_payment * time_years * 12
        
        monthly_rate = rate / 12
        n_payments = time_years * 12
        
        principal = monthly_payment * ((1 + monthly_rate) ** n_payments - 1) / \
                   (monthly_rate * (1 + monthly_rate) ** n_payments)
        return principal


class FinancialQueryProcessor:
    """자연어 금융 질의 처리 클래스"""
    
    def __init__(self):
        # Clova X 모델 초기화
        self.llm = ChatClovaX(
            api_key=os.getenv('NCP_CLOVASTUDIO_API_KEY'),
            model="HCX-005",
            temperature=0.2,
            max_tokens=2000,
        )
        
        self.prompt_template = PromptTemplate(
            input_variables=["query"],
            template="""
당신은 금융 계산 전문가입니다. 사용자의 질의를 분석하여 정확한 금융 계산을 수행하고 결과를 설명해주세요.

다음 공식들을 사용하여 계산하세요:

1. 복리 계산: A = P(1 + r)^t
   - A: 최종 금액, P: 원금, r: 연이자율, t: 기간(년)

2. 원리금균등상환 월납부액: PMT = P × [r(1+r)^n] / [(1+r)^n - 1]
   - PMT: 월납부액, P: 대출원금, r: 월이자율, n: 총 납부횟수

3. 만기일시상환 이자: I = P × r × t
   - I: 총 이자, P: 원금, r: 연이자율, t: 기간

4. 최대 대출액: P = PMT × [(1+r)^n - 1] / [r(1+r)^n]

사용자 질의: {query}

계산 과정과 결과를 명확하게 설명해주세요. 
단위 변환 (억=100,000,000원, 만=10,000원)도 적용하세요.
            """
        )
    
    def process_query(self, query: str) -> str:
        """자연어 질의 처리"""
        try:
            prompt = self.prompt_template.format(query=query)
            response = self.llm.invoke([HumanMessage(content=prompt)])
            
            # 텍스트 응답 그대로 반환
            return response.content
            
        except Exception as e:
            st.error(f"질의 처리 중 오류 발생: {e}")
            return f"죄송합니다. 처리 중 오류가 발생했습니다: {e}"


def create_comparison_chart(results: List[Dict]) -> go.Figure:
    """비교 차트 생성"""
    fig = go.Figure()
    
    periods = [r['period'] for r in results]
    amounts = [r['total_amount'] for r in results]
    interests = [r['total_interest'] for r in results]
    
    fig.add_trace(go.Bar(
        name='총 상환액',
        x=periods,
        y=amounts,
        marker_color='lightblue'
    ))
    
    fig.add_trace(go.Bar(
        name='총 이자',
        x=periods,
        y=interests,
        marker_color='coral'
    ))
    
    fig.update_layout(
        title='대출 기간별 비교',
        xaxis_title='기간',
        yaxis_title='금액 (원)',
        barmode='group',
        height=400
    )
    
    return fig


def main():
    st.title("💰 LoanMate - 당신의 금융 계산 파트너")
    st.write("자연어로 질문하면 정확한 금융 계산을 해드립니다!")
    
    # API 키 확인
    if not os.getenv('NCP_CLOVASTUDIO_API_KEY'):
        st.error("NCP_CLOVASTUDIO_API_KEY 환경변수를 설정해주세요.")
        st.stop()
    
    # 초기화
    if 'processor' not in st.session_state:
        st.session_state.processor = FinancialQueryProcessor()
        st.session_state.calculator = FinancialCalculator()
    
    # 예제 질문들
    st.sidebar.header("💡 예제 질문들")
    examples = [
        "1억 원을 연 4%로 3년간 예금하면?",
        "이자율은 연 5%, 매달 50만 원씩 갚을 때 3년 만에 얼마까지 대출 가능해?",
        "같은 조건에서 3년 vs 5년 vs 10년 만기일시상환의 이자 차이 보여줘"
    ]
    
    for i, example in enumerate(examples):
        if st.sidebar.button(f"예제 {i+1}", key=f"example_{i}"):
            st.session_state.user_query = example
    
    # 사용자 입력
    user_query = st.text_area(
        "질문을 입력하세요:",
        value=getattr(st.session_state, 'user_query', ''),
        height=100,
        placeholder="예: 1억 원을 연 4%로 3년간 예금하면 얼마가 될까요?"
    )
    
    if st.button("💫 계산하기", type="primary"):
        if user_query:
            with st.spinner("AI가 계산 중..."):
                # 질의 처리
                ai_response = st.session_state.processor.process_query(user_query)
                
                if ai_response:
                    st.success("💰 LoanMate 계산 완료!")
                    
                    # AI 응답 표시
                    st.markdown("### 📊 계산 결과")
                    st.markdown(ai_response)
                    
                    # 비교 질문인 경우 추가 차트 생성
                    if any(keyword in user_query for keyword in ['비교', 'vs', '차이', '년']):
                        st.markdown("### 📈 시각화 비교")
                        
                        # 예시 데이터로 차트 생성 (실제로는 AI 응답을 파싱해서 데이터 추출)
                        import re
                        years = re.findall(r'(\d+)\s*년', user_query)
                        
                        if len(years) >= 2:
                            # 간단한 예시 계산 (실제로는 더 정교한 파싱 필요)
                            example_results = []
                            for year in years[:3]:  # 최대 3개까지
                                year_num = int(year)
                                # 예시: 1억원 기준 연 5% 만기일시상환
                                principal = 100000000
                                rate = 0.05
                                total_interest = principal * rate * year_num
                                total_amount = principal + total_interest
                                
                                example_results.append({
                                    'period': f"{year}년",
                                    'total_amount': total_amount,
                                    'total_interest': total_interest
                                })
                            
                            if example_results:
                                fig = create_comparison_chart(example_results)
                                st.plotly_chart(fig, use_container_width=True)
                                
                                st.info("💡 **참고**: 위 차트는 1억원, 연 5% 만기일시상환 기준 예시입니다.")
                
                else:
                    st.error("질의를 이해할 수 없습니다. 다시 시도해주세요.")
        else:
            st.warning("질문을 입력해주세요.")
    
    # 사용법 안내
    st.sidebar.header("📖 사용법")
    st.sidebar.write("""
    **지원하는 계산 유형:**
    - ✅ 복리/단리 이자 계산
    - ✅ 대출 월납부액 계산
    - ✅ 최대 대출 가능액 계산
    - ✅ 여러 조건 비교 분석
    
    **입력 예시:**
    - "1억원을 연 4%로 3년간 예금하면?"
    - "월 50만원씩 갚을 때 최대 대출액은?"
    - "3년 vs 5년 대출 이자 비교해줘"
    """)


if __name__ == "__main__":
    main()