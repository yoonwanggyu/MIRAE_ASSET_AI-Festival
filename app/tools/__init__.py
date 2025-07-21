from .task1_simple import (
    get_stock_info,
    get_daily_change_rate,
    get_top_stocks_by_metric,
    get_top_or_bottom_price_stocks,
    get_rising_falling_counts,
    count_traded_stocks
)

from .task2_conditional import screen_stocks_by_conditions

all_tools = [
    get_stock_info,
    get_daily_change_rate,
    get_top_stocks_by_metric,
    get_top_or_bottom_price_stocks,
    get_rising_falling_counts,
    count_traded_stocks,
    screen_stocks_by_conditions,
]