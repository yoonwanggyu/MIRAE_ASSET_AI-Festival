# task1_funcs.py 업데이트 버전

from task1_tools import *
from task4_tools import *  # Task4 추가
from typing import Dict, Any

# Task1 Function Definitions
task1_functions = [
    {
        "name": "get_info_stock",
        "description": "주어진 날짜(date)에 대해 특정 종목(stock_name)의 pbr,per,시가(Open), 고가(High), 저가(Low), 종가(Close) 또는 거래량(Volume) 중 하나(field)에 해당하는 값을 반환합니다. field 값은 한글(시가·고가·저가·종가·거래량)이나 영문(open·high·low·close·volume)으로 지정할 수 있으며, 반드시 그중 하나만 선택해야 합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "stock_name": {"type": "string"},
                "date": {"type": "string", "format": "date"},
                "field": {"type": "string", "enum": ["open", "high", "low", "close", "volume","pbr","per,","시가", "고가", "저가", "종가", "거래량"]}
            },
            "required": ["stock_name", "date", "field"]
        }
    },
    {
        "name": "get_top_volume",
        "description": "거래량 상위 N종목",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "format": "date"},
                "top_n": {"type": "integer", "default": 10}
            },
            "required": ["date"]
        }
    },
    {
        "name": "get_top_gain",
        "description": "상승률 상위 N종목",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "format": "date"},
                "top_n": {"type": "integer", "default": 10}
            },
            "required": ["date"]
        }
    },
    {
        "name": "get_top_drop",
        "description": "하락률 상위 N종목",
        "parameters": {
            "type": "object",
            "properties": {
                "date": {"type": "string", "format": "date"},
                "top_n": {"type": "integer", "default": 10}
            },
            "required": ["date"]
        }
    },
    {
        "name": "get_daily_change_rate",
        "description": "주어진 종목의 등락률(%) 계산",
        "parameters": {
            "type": "object",
            "properties": {
                "stock_name": {"type": "string"},
                "date": {"type": "string", "format": "date"},
            },
            "required": ["stock_name", "date"]
        }
    },
    {
        "name": "get_top_or_bottom_price_stocks",
        "description": (
            "특정 날짜(date)와 시장(market: 'KOSPI' 또는 'KOSDAQ')에서 "
            "종가 기준으로 가장 비싼(top) 혹은 가장 저렴한(bottom) 종목을 "
            "count개 반환합니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "date":   {"type": "string", "format": "date"},
                "market": {"type": "string", "enum": ["KOSPI", "KOSDAQ"]},
                "mode":   {"type": "string", "enum": ["top", "bottom"], "default": "top"},
                "count":  {"type": "integer", "minimum": 1, "default": 1}
            },
            "required": ["date", "market"]
        }
    },
    {
        "name": "get_rising_falling_counts",
        "description": (
            "특정 날짜(date)와 시장(market: 'KOSPI', 'KOSDAQ', 'ALL') 기준으로 "
            "상승 종목 수 또는 하락 종목 수를 반환합니다. "
            "mode는 'rising' 또는 'falling' 중 하나로 지정할 수 있습니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "date":   {"type": "string", "format": "date"},
                "market": {"type": "string", "enum": ["KOSPI", "KOSDAQ", "ALL"]},
                "mode":   {"type": "string", "enum": ["rising", "failing"]},
            },
            "required": ["date", "market","mode"]
        }
    },
    {
        "name": "count_traded_stocks",
        "description": (
            "특정 날짜(date)와 시장(market: 'KOSPI', 'KOSDAQ', 'ALL') 기준으로 "
            "거래된 종목 수를 반환합니다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "date":   {"type": "string", "format": "date"},
                "market": {"type": "string", "enum": ["KOSPI", "KOSDAQ", "ALL"]},
            },
            "required": ["date", "market"]
        }
    }
]

# Task1 Python Function Mapping
task1_py_funcs: Dict[str, Any] = {
    "get_info_stock": get_info_stock,
    "get_top_volume": get_top_volume,
    "get_top_gain": get_top_gain,
    "get_top_drop": get_top_drop,
    "get_daily_change_rate" : get_daily_change_rate,
    "get_top_or_bottom_price_stocks" : get_top_or_bottom_price_stocks,
    "get_rising_falling_counts" : get_rising_falling_counts,
    "count_traded_stocks": count_traded_stocks
}

# Task4는 별도 파일에서 정의됨 (task4_tools.py)
# task4_functions와 task4_py_funcs는 task4_tools.py에서 import됨