# =============================================================================
# graph/nodes.py
import re
import asyncio
from typing import Dict, Any
from graph.state import InvestmentState
from data.yahoo_api import YahooFinanceAPI
from data.dart_api import DartAPI
from data.ticker_mapper import TickerMapper
from analysis.valuation import ValuationAnalyzer
from analysis.risk_analysis import RiskAnalyzer
from llm.clova_client import ClovaClient

class InvestmentNodes:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.yahoo_api = YahooFinanceAPI()
        self.dart_api = DartAPI(config['dart_api_key'])
        self.ticker_mapper = TickerMapper()
        self.valuation_analyzer = ValuationAnalyzer()
        self.risk_analyzer = RiskAnalyzer()
        self.clova_client = ClovaClient(config['clova_api_key'])
    
    async def analyze_intent_node(self, state: InvestmentState) -> InvestmentState:
        """질문 의도 분석 노드"""
        try:
            prompt = f"""
            사용자 질문: "{state.user_input}"
            
            다음 중 어떤 의도인지 분류해주세요:
            1. past_purchase: 과거 매수 판단 진단 (예: "작년에 산 삼성전자 잘 산 걸까?")
            2. current_analysis: 현재 매수 판단 요청 (예: "삼성전자 지금 사도 돼?")
            3. market_exploration: 종목 탐색 (예: "오늘 오른 종목 뭐 있어?")
            4. detailed_analysis: 상세 분석 요청 (예: "리스크 더 보여줘")
            
            또한 종목명을 추출해주세요.
            
            응답 형식: intent|stock_name
            """
            
            response = await self.clova_client.generate(prompt)
            
            if '|' in response:
                intent, stock_name = response.split('|', 1)
                state.intent = intent.strip()
                state.stock_name = stock_name.strip()
            else:
                # 정규식으로 종목명 추출 시도
                stock_pattern = r'([가-힣]+(?:전자|화학|생명|에너지|건설|금융|보험|증권|은행|카드|캐피탈|리츠|바이오|제약|반도체|디스플레이|모터스|타이어|철강|조선|항공|통신|미디어|엔터|게임|소프트|시스템|솔루션|테크|IT)?)'
                matches = re.findall(stock_pattern, state.user_input)
                if matches:
                    state.stock_name = matches[0]
                    state.intent = "current_analysis"  # 기본값
                
        except Exception as e:
            state.errors.append(f"의도 분석 오류: {e}")
            state.intent = "current_analysis"  # 기본값
            
        return state
    
    async def ticker_mapping_node(self, state: InvestmentState) -> InvestmentState:
        """종목코드 매핑 노드"""
        try:
            if state.stock_name:
                ticker = await self.ticker_mapper.get_ticker(state.stock_name)
                if ticker:
                    state.ticker = ticker
                else:
                    state.errors.append(f"'{state.stock_name}' 종목을 찾을 수 없습니다.")
        except Exception as e:
            state.errors.append(f"티커 매핑 오류: {e}")
            
        return state
    
    async def data_collection_node(self, state: InvestmentState) -> InvestmentState:
        """데이터 수집 노드 (병렬 처리)"""
        if not state.ticker:
            return state
            
        try:
            # 야후파이낸스와 DART 데이터를 병렬로 수집
            yahoo_task = self.yahoo_api.get_stock_data(state.ticker)
            dart_task = self.dart_api.get_company_data(state.stock_name)
            
            yahoo_result, dart_result = await asyncio.gather(
                yahoo_task, dart_task, return_exceptions=True
            )
            
            if not isinstance(yahoo_result, Exception):
                state.yahoo_data = yahoo_result
            else:
                state.errors.append(f"야후파이낸스 데이터 수집 실패: {yahoo_result}")
                
            if not isinstance(dart_result, Exception):
                state.dart_data = dart_result
            else:
                state.errors.append(f"DART 데이터 수집 실패: {dart_result}")
                
        except Exception as e:
            state.errors.append(f"데이터 수집 오류: {e}")
            
        return state
    
    async def valuation_node(self, state: InvestmentState) -> InvestmentState:
        """가치평가 노드"""
        try:
            if state.yahoo_data:
                valuation_result = await self.valuation_analyzer.analyze(
                    state.yahoo_data, state.dart_data
                )
                state.valuation_result = valuation_result
        except Exception as e:
            state.errors.append(f"가치평가 오류: {e}")
            
        return state
    
    async def risk_analysis_node(self, state: InvestmentState) -> InvestmentState:
        """리스크 분석 노드"""
        try:
            if state.dart_data:
                risk_result = await self.risk_analyzer.analyze(state.dart_data)
                state.risk_analysis = risk_result
        except Exception as e:
            state.errors.append(f"리스크 분석 오류: {e}")
            
        return state
    
    async def interpretation_node(self, state: InvestmentState) -> InvestmentState:
        """클로바X를 통한 해석 노드"""
        try:
            prompt = self._create_interpretation_prompt(state)
            interpretation = await self.clova_client.generate(prompt)
            
            follow_up_prompt = self._create_follow_up_prompt(state)
            follow_up_options = await self.clova_client.generate(follow_up_prompt)
            
            state.final_output = interpretation
            if follow_up_options:
                state.follow_up_options = [
                    option.strip() for option in follow_up_options.split('\n') 
                    if option.strip()
                ][:4]  # 최대 4개
                
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            state.errors.append(f"해석 생성 오류: {e}")
            state.final_output = f"분석 중 오류가 발생했습니다.\n상세 오류: {e}\n{error_details}"
            print(f"🔍 해석 노드 오류: {e}")
            print(f"상세 정보: {error_details}")
            
        return state
    
    def _create_interpretation_prompt(self, state: InvestmentState) -> str:
        """해석용 프롬프트 생성"""
        prompt = f"""
        투자 분석 전문가로서 다음 데이터를 종합하여 투자 판단을 내려주세요.

        📊 기업명: {state.stock_name}
        📈 티커: {state.ticker}
        
        🔍 야후파이낸스 데이터:
        {self._format_yahoo_data(state.yahoo_data)}
        
        📋 DART 공시 데이터:
        {self._format_dart_data(state.dart_data)}
        
        📊 가치평가 결과:
        {state.valuation_result}
        
        ⚠️ 리스크 분석:
        {state.risk_analysis}
        
        다음 형식으로 응답해주세요:
        
        ## 🏛️ Fin문철의 투자 판결서
        
        ### 📊 핵심 지표 요약
        - 현재가: [가격]
        - PER: [수치] (업계 평균 대비 [상황])
        - PBR: [수치] (적정성 평가)
        - 기타 주요 지표들...
        
        ### 💡 종합 분석
        [정량적 지표와 정성적 요소를 종합한 분석]
        
        ### ⚖️ 투자 판단
        **결론: [매수/보류/매도]**
        
        📌 핵심 근거:
        1. [근거 1]
        2. [근거 2]
        3. [근거 3]
        
        ### 🎯 투자 전략 제안
        [구체적인 투자 전략 및 주의사항]
        """
        
        return prompt
    
    def _create_follow_up_prompt(self, state: InvestmentState) -> str:
        """후속 질문 옵션 생성 프롬프트"""
        return f"""
        {state.stock_name} 분석을 완료했습니다. 
        사용자가 추가로 알고 싶어할 만한 후속 질문 4개를 제안해주세요.
        
        각 줄에 하나씩 작성해주세요:
        예시:
        유사 종목 추천받기
        리스크 요인 상세 분석
        기술적 분석 확인
        투자 타이밍 전략
        """
    
    def _format_yahoo_data(self, data: Dict) -> str:
        """야후파이낸스 데이터 포맷팅"""
        if not data:
            return "데이터 없음"
        
        formatted = []
        for key, value in data.items():
            if isinstance(value, (int, float)):
                formatted.append(f"- {key}: {value:,.2f}")
            else:
                formatted.append(f"- {key}: {value}")
        
        return "\n".join(formatted)
    
    def _format_dart_data(self, data: Dict) -> str:
        """DART 데이터 포맷팅"""
        if not data:
            return "데이터 없음"
        
        formatted = []
        for key, value in data.items():
            formatted.append(f"- {key}: {value}")
        
        return "\n".join(formatted)