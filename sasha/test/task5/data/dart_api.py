# =============================================================================
# data/dart_api.py
import requests
import asyncio
from typing import Dict, List
import xml.etree.ElementTree as ET

class DartAPI:
    """DART 전자공시 API 클라이언트"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://opendart.fss.or.kr/api"
    
    async def get_company_data(self, company_name: str) -> Dict:
        """기업 공시 데이터 수집"""
        try:
            # 기업 코드 조회
            corp_code = await self._get_corp_code(company_name)
            if not corp_code:
                return {"error": f"{company_name} 기업 코드를 찾을 수 없습니다."}
            
            # 병렬로 데이터 수집
            tasks = [
                self._get_financial_summary(corp_code),
                self._get_audit_opinion(corp_code),
                self._get_disclosure_list(corp_code)
            ]
            
            financial_data, audit_data, disclosure_data = await asyncio.gather(
                *tasks, return_exceptions=True
            )
            
            return {
                "corp_code": corp_code,
                "financial_summary": financial_data if not isinstance(financial_data, Exception) else {},
                "audit_opinion": audit_data if not isinstance(audit_data, Exception) else {},
                "recent_disclosures": disclosure_data if not isinstance(disclosure_data, Exception) else []
            }
            
        except Exception as e:
            return {"error": f"DART 데이터 수집 실패: {e}"}
    
    async def _get_corp_code(self, company_name: str) -> str:
        """기업 고유번호 조회"""
        url = f"{self.base_url}/company.json"
        params = {
            "crtfc_key": self.api_key,
            "corp_name": company_name
        }
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, requests.get, url, params)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "000" and data.get("list"):
                return data["list"][0]["corp_code"]
        
        return ""
    
    async def _get_financial_summary(self, corp_code: str) -> Dict:
        """재무제표 요약 조회"""
        url = f"{self.base_url}/fnlttSinglAcntAll.json"
        params = {
            "crtfc_key": self.api_key,
            "corp_code": corp_code,
            "bsns_year": "2023",  # 최신년도
            "reprt_code": "11011"  # 사업보고서
        }
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, requests.get, url, params)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "000":
                return self._parse_financial_data(data.get("list", []))
        
        return {}
    
    async def _get_audit_opinion(self, corp_code: str) -> Dict:
        """감사의견 조회"""
        # 실제 구현에서는 감사보고서 문서를 파싱해야 함
        # 여기서는 간소화된 버전으로 구현
        return {
            "audit_opinion": "적정",
            "going_concern_uncertainty": False,
            "internal_control_deficiency": False
        }
    
    async def _get_disclosure_list(self, corp_code: str) -> List[Dict]:
        """최근 공시 목록 조회"""
        url = f"{self.base_url}/list.json"
        params = {
            "crtfc_key": self.api_key,
            "corp_code": corp_code,
            "bgn_de": "20240101",  # 올해부터
            "page_count": "10"
        }
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, requests.get, url, params)
        
        if response.status_code == 200:
            data = response.json()
            if data.get("status") == "000":
                return data.get("list", [])
        
        return []
    
    def _parse_financial_data(self, financial_list: List[Dict]) -> Dict:
        """재무데이터 파싱"""
        result = {}
        
        for item in financial_list:
            account_nm = item.get("account_nm", "")
            thstrm_amount = item.get("thstrm_amount", "0")
            
            # 주요 계정과목만 추출
            if "매출액" in account_nm:
                result["revenue"] = self._parse_amount(thstrm_amount)
            elif "당기순이익" in account_nm:
                result["net_income"] = self._parse_amount(thstrm_amount)
            elif "자산총계" in account_nm:
                result["total_assets"] = self._parse_amount(thstrm_amount)
            elif "부채총계" in account_nm:
                result["total_liabilities"] = self._parse_amount(thstrm_amount)
            elif "자본총계" in account_nm:
                result["total_equity"] = self._parse_amount(thstrm_amount)
        
        # 재무비율 계산
        if result.get("total_assets") and result.get("total_liabilities"):
            result["debt_ratio"] = (result["total_liabilities"] / result["total_assets"]) * 100
        
        if result.get("net_income") and result.get("total_equity"):
            result["roe"] = (result["net_income"] / result["total_equity"]) * 100
        
        return result
    
    def _parse_amount(self, amount_str: str) -> float:
        """금액 문자열을 숫자로 변환"""
        try:
            # 쉼표 제거 후 숫자로 변환
            return float(amount_str.replace(",", ""))
        except:
            return 0.0