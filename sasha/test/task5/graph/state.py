# =============================================================================
# graph/state.py
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, field
from langgraph.graph import StateGraph

@dataclass
class InvestmentState:
    """투자 분석 상태 관리"""
    user_input: str = ""
    conversation_history: List[Dict] = field(default_factory=list)
    
    # 분석 단계
    intent: str = ""
    stock_name: str = ""
    ticker: str = ""
    
    # 데이터
    yahoo_data: Dict = field(default_factory=dict)
    dart_data: Dict = field(default_factory=dict)
    
    # 분석 결과
    valuation_result: Dict = field(default_factory=dict)
    risk_analysis: Dict = field(default_factory=dict)
    
    # 출력
    final_output: str = ""
    follow_up_options: List[str] = field(default_factory=list)
    
    # 오류 처리
    errors: List[str] = field(default_factory=list)