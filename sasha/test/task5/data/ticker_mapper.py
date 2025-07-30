
# =============================================================================
# data/ticker_mapper.py
import pandas as pd
import asyncio
from typing import Optional

class TickerMapper:
    """한국 종목명을 티커로 매핑"""
    
    def __init__(self):
        self.ticker_map = {}
        self._load_ticker_data()
    
    def _load_ticker_data(self):
        """티커 데이터 로드 (간소화 버전)"""
        # 실제로는 KRX에서 전체 종목 리스트를 가져와야 함
        self.ticker_map = {
            "삼성전자": "005930.KS",
            "SK하이닉스": "000660.KS",
            "네이버": "035420.KS",
            "카카오": "035720.KS",
            "LG에너지솔루션": "373220.KS",
            "현대차": "005380.KS",
            "기아": "000270.KS",
            "POSCO홀딩스": "005490.KS",
            "한국전력": "015760.KS",
            "셀트리온": "068270.KS",
            "삼성바이오로직스": "207940.KS",
            "LG화학": "051910.KS",
            "삼성SDI": "006400.KS",
            "현대모비스": "012330.KS",
            "한화솔루션": "009830.KS"
        }
    
    async def get_ticker(self, company_name: str) -> Optional[str]:
        """회사명으로 티커 조회"""
        # 정확한 매치 먼저 시도
        if company_name in self.ticker_map:
            return self.ticker_map[company_name]
        
        # 부분 매치 시도
        for name, ticker in self.ticker_map.items():
            if company_name in name or name in company_name:
                return ticker
        
        return None



