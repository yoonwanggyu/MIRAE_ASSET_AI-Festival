# =============================================================================
# analysis/valuation.py
from typing import Dict
import asyncio

class ValuationAnalyzer:
    """가치평가 분석기"""
    
    async def analyze(self, yahoo_data: Dict, dart_data: Dict) -> Dict:
        """종합 가치평가 분석"""
        result = {}
        
        try:
            # PER 분석
            per = yahoo_data.get("pe_ratio", 0)
            if per > 0:
                if per < 10:
                    per_assessment = "매우 저평가"
                elif per < 15:
                    per_assessment = "저평가"
                elif per < 25:
                    per_assessment = "적정평가"
                else:
                    per_assessment = "고평가"
            else:
                per_assessment = "판단불가"
            
            result["per_analysis"] = {
                "value": per,
                "assessment": per_assessment
            }
            
            # PBR 분석
            pbr = yahoo_data.get("pb_ratio", 0)
            if pbr > 0:
                if pbr < 1:
                    pbr_assessment = "저평가"
                elif pbr < 2:
                    pbr_assessment = "적정평가"
                else:
                    pbr_assessment = "고평가"
            else:
                pbr_assessment = "판단불가"
            
            result["pbr_analysis"] = {
                "value": pbr,
                "assessment": pbr_assessment
            }
            
            # 배당수익률 분석
            dividend_yield = yahoo_data.get("dividend_yield", 0) * 100
            result["dividend_analysis"] = {
                "yield": dividend_yield,
                "assessment": "우수" if dividend_yield > 3 else "보통" if dividend_yield > 1 else "낮음"
            }
            
            # 종합 평가
            scores = []
            if per_assessment in ["매우 저평가", "저평가"]:
                scores.append(1)
            elif per_assessment == "적정평가":
                scores.append(0)
            else:
                scores.append(-1)
            
            if pbr_assessment == "저평가":
                scores.append(1)
            elif pbr_assessment == "적정평가":
                scores.append(0)
            else:
                scores.append(-1)
            
            avg_score = sum(scores) / len(scores) if scores else 0
            
            if avg_score > 0.3:
                overall_assessment = "매수"
            elif avg_score > -0.3:
                overall_assessment = "보유"
            else:
                overall_assessment = "매도"
            
            result["overall_assessment"] = {
                "score": avg_score,
                "recommendation": overall_assessment
            }
            
        except Exception as e:
            result["error"] = f"가치평가 분석 오류: {e}"
        
        return result