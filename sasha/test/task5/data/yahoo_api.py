# =============================================================================
# data/yahoo_api.py
import yfinance as yf
import asyncio
from typing import Dict, Optional

class YahooFinanceAPI:
    """야후파이낸스 API 클라이언트"""
    
    async def get_stock_data(self, ticker: str) -> Dict:
        """주식 데이터 수집"""
        try:
            # 비동기 처리를 위해 별도 스레드에서 실행
            loop = asyncio.get_event_loop()
            stock_data = await loop.run_in_executor(None, self._fetch_stock_data, ticker)
            return stock_data
        except Exception as e:
            raise Exception(f"야후파이낸스 데이터 수집 실패: {e}")
    
    def _fetch_stock_data(self, ticker: str) -> Dict:
        """실제 데이터 수집 (동기)"""
        stock = yf.Ticker(ticker)
        
        # 기본 정보
        info = stock.info
        
        # 재무제표
        financials = stock.financials
        balance_sheet = stock.balance_sheet
        cashflow = stock.cashflow
        
        # 역사적 데이터
        hist = stock.history(period="1y")
        
        return {
            "current_price": info.get("currentPrice", 0),
            "market_cap": info.get("marketCap", 0),
            "pe_ratio": info.get("trailingPE", 0),
            "pb_ratio": info.get("priceToBook", 0),
            "dividend_yield": info.get("dividendYield", 0),
            "eps": info.get("trailingEps", 0),
            "revenue": info.get("totalRevenue", 0),
            "profit_margin": info.get("profitMargins", 0),
            "debt_to_equity": info.get("debtToEquity", 0),
            "return_on_equity": info.get("returnOnEquity", 0),
            "analyst_target_price": info.get("targetMeanPrice", 0),
            "recommendation": info.get("recommendationKey", ""),
            "52_week_high": info.get("fiftyTwoWeekHigh", 0),
            "52_week_low": info.get("fiftyTwoWeekLow", 0),
            "volume": info.get("volume", 0),
            "avg_volume": info.get("averageVolume", 0),
            "beta": info.get("beta", 0),
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "historical_data": {
                "1_month_return": self._calculate_return(hist, 30),
                "3_month_return": self._calculate_return(hist, 90),
                "1_year_return": self._calculate_return(hist, 252)
            }
        }
    
    def _calculate_return(self, hist_data, days: int) -> float:
        """수익률 계산"""
        try:
            if len(hist_data) < days:
                return 0.0
            
            start_price = hist_data['Close'].iloc[-days]
            end_price = hist_data['Close'].iloc[-1]
            return ((end_price - start_price) / start_price) * 100
        except:
            return 0.0