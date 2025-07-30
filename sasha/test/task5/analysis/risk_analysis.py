# =============================================================================
# analysis/risk_analysis.py
from typing import Dict
import asyncio

class RiskAnalyzer:
    """리스크 분석기"""
    
    async def analyze(self, dart_data: Dict) -> Dict:
        """DART 데이터 기반 리스크 분석"""
        result = {
            "financial_risk": "낮음",
            "audit_risk": "낮음",
            "liquidity_risk": "낮음",
            "overall_risk": "낮음",
            "risk_factors": []
        }
        
        try:
            financial_data = dart_data.get("financial_summary", {})
            audit_data = dart_data.get("audit_opinion", {})
            
            risk_score = 0
            
            # 재무 리스크 분석
            debt_ratio = financial_data.get("debt_ratio", 0)
            if debt_ratio > 70:
                result["financial_risk"] = "높음"
                result["risk_factors"].append("부채비율 과도(70% 초과)")
                risk_score += 2
            elif debt_ratio > 50:
                result["financial_risk"] = "보통"
                result["risk_factors"].append("부채비율 다소 높음(50% 초과)")
                risk_score += 1
            
            # ROE 분석
            roe = financial_data.get("roe", 0)
            if roe < 5:
                result["risk_factors"].append("낮은 자기자본이익률(5% 미만)")
                risk_score += 1
            
            # 감사의견 리스크
            audit_opinion = audit_data.get("audit_opinion", "적정")
            if audit_opinion != "적정":
                result["audit_risk"] = "높음"
                result["risk_factors"].append(f"감사의견: {audit_opinion}")
                risk_score += 2
            
            # 계속기업 불확실성
            if audit_data.get("going_concern_uncertainty", False):
                result["audit_risk"] = "높음"
                result["risk_factors"].append("계속기업 불확실성 존재")
                risk_score += 3
            
            # 내부통제 미비
            if audit_data.get("internal_control_deficiency", False):
                result["risk_factors"].append("내부회계관리제도 미비점 존재")
                risk_score += 1
            
            # 종합 리스크 평가
            if risk_score >= 4:
                result["overall_risk"] = "높음"
            elif risk_score >= 2:
                result["overall_risk"] = "보통"
            else:
                result["overall_risk"] = "낮음"
            
            result["risk_score"] = risk_score
            
        except Exception as e:
            result["error"] = f"리스크 분석 오류: {e}"
        
        return result
