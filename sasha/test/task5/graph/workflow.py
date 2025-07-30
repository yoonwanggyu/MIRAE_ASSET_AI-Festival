
# =============================================================================
# graph/workflow.py
from langgraph.graph import StateGraph, END
from graph.state import InvestmentState
from graph.nodes import InvestmentNodes

def create_investment_workflow(config):
    """투자 분석 워크플로우 생성"""
    
    # 노드 인스턴스 생성
    nodes = InvestmentNodes(config)
    
    # 그래프 생성
    workflow = StateGraph(InvestmentState)
    
    # 노드 추가
    workflow.add_node("analyze_intent", nodes.analyze_intent_node)
    workflow.add_node("ticker_mapping", nodes.ticker_mapping_node)
    workflow.add_node("data_collection", nodes.data_collection_node)
    workflow.add_node("valuation", nodes.valuation_node)
    workflow.add_node("risk_analysis", nodes.risk_analysis_node)
    workflow.add_node("interpretation", nodes.interpretation_node)
    
    # 엣지 설정
    workflow.set_entry_point("analyze_intent")
    
    workflow.add_edge("analyze_intent", "ticker_mapping")
    workflow.add_edge("ticker_mapping", "data_collection")
    workflow.add_edge("data_collection", "valuation")
    workflow.add_edge("valuation", "risk_analysis")
    workflow.add_edge("risk_analysis", "interpretation")
    workflow.add_edge("interpretation", END)
    
    return workflow.compile()

