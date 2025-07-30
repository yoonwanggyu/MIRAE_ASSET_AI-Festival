
# =============================================================================
# utils/helpers.py
import logging
import sys
from typing import Any

def setup_logging(level: str = "INFO"):
    """로깅 설정"""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

def format_currency(amount: float, currency: str = "KRW") -> str:
    """통화 포맷팅"""
    if currency == "KRW":
        if amount >= 1_000_000_000_000:  # 조
            return f"{amount/1_000_000_000_000:.1f}조원"
        elif amount >= 100_000_000:  # 억
            return f"{amount/100_000_000:.1f}억원"
        elif amount >= 10_000:  # 만
            return f"{amount/10_000:.1f}만원"
        else:
            return f"{amount:,.0f}원"
    else:
        return f"{amount:,.2f} {currency}"

def format_percentage(value: float) -> str:
    """퍼센트 포맷팅"""
    return f"{value:.2f}%"

def safe_divide(numerator: float, denominator: float) -> float:
    """안전한 나눗셈"""
    try:
        return numerator / denominator if denominator != 0 else 0.0
    except:
        return 0.0
