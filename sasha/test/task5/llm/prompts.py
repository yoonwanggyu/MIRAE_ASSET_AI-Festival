# =============================================================================
# llm/prompts.py
class PromptTemplates:
    """프롬프트 템플릿 모음"""
    
    INTENT_ANALYSIS = """
    사용자 질문: "{query}"
    
    다음 중 어떤 의도인지 분류해주세요:
    1. past_purchase: 과거 매수 판단 진단
    2. current_analysis: 현재 매수 판단 요청  
    3. market_exploration: 종목 탐색
    4. detailed_analysis: 상세 분석 요청
    
    또한 종목명을 추출해주세요.
    응답 형식: intent|stock_name
    """
    
    INVESTMENT_ANALYSIS = """
    투자 분석 전문가로서 다음 데이터를 종합하여 투자 판단을 내려주세요.

    📊 기업명: {stock_name}
    📈 티커: {ticker}
    
    🔍 야후파이낸스 데이터:
    {yahoo_data}
    
    📋 DART 공시 데이터:
    {dart_data}
    
    📊 가치평가 결과:
    {valuation_result}
    
    ⚠️ 리스크 분석:
    {risk_analysis}
    
    다음 형식으로 응답해주세요:
    
    ## 🏛️ Fin문철의 투자 판결서
    
    ### 📊 핵심 지표 요약
    ### 💡 종합 분석  
    ### ⚖️ 투자 판단
    ### 🎯 투자 전략 제안
    """
