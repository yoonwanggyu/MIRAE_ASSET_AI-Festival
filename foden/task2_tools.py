from utils import *
import yfinance as yf

def get_volume_range(stock_name: str, start_date: str, end_date: str, aggregate: str = "sum"):
    '''
    기간별 거래량 조회
    - aggregate="sum"   → 기간 총합
    - aggregate="daily" → 일자별 상세표
    예) "거래량이 전날 대비 10% 오른 종목은?"
    '''
    try:
        start_std = normalize_date(start_date)
        end_std   = normalize_date(end_date)
    except ValueError as e:
        return f"❌ {e}"

    if start_std > end_std:
        return "❌ 시작 날짜가 종료 날짜보다 늦습니다."

    ticker = name_to_ticker(stock_name, start_std.replace("-", ""))
    if not ticker:
        return f"❌ '{stock_name}' 종목을 찾을 수 없습니다."

    # yfinance 범위 다운로드 (end는 포함 안 됨 → 하루 더)
    df = yf.download(
        ticker,
        start=start_std,
        end=(pd.Timestamp(end_std) + pd.Timedelta(days=1)).strftime("%Y-%m-%d"),
        progress=False,
    )

    if df.empty:
        return f"❌ {start_std}~{end_std} 구간에 거래 데이터가 없습니다."

    vol_series = df["Volume"]

    if aggregate == "daily":
        lines = [f"{d.date()}: {v:,}주" for d, v in vol_series.items()]
        return f"{stock_name} {start_std}~{end_std} 일별 거래량:\n" + "\n".join(lines)

    # 기본: 총합
    total_vol = int(vol_series.sum())
    return f"{stock_name}의 {start_std}~{end_std} 기간 총 거래량은 {total_vol:,}주입니다."

def get_change_pct(stock_name: str, date_from: str, date_to: str | None = None):
    """
    기간 대비 주가 변동률 계산 함수
    ex) “삼성전자 5월 28일 전일 대비 상승률은?”
        “삼성전자 5/02에서 5/04까지 주가 변동률 알려줘”
        “삼성전자 지난주 대비 얼마 올랐어?” (LLM이 날짜 파싱해 전달)
        “삼전 전주 대비 등락폭?”
    """

    try:
        date_from = normalize_date(date_from)
        date_to  = normalize_date(date_to)
    except ValueError as e:
        return f"❌ {e}"

    # date_to가 None이면 '전일 대비' 로 처리
    if date_to is None:
        d0 = pd.Timestamp(date_from)
        # d1 = d0 - pd.Timedelta(days=7)  # 주말 보정
        date_to = (d0 - pd.tseries.offsets.BDay(1)).strftime("%Y-%m-%d")
    
    ticker = name_to_ticker(stock_name, date_from.replace("-", ""))
    if not ticker:
        return f"❌ '{stock_name}' 종목을 찾을 수 없습니다."
    
    df = yf.download(ticker, start=date_to, end=pd.Timestamp(date_from)+pd.Timedelta(days=1),
                     progress=False)
    if len(df) < 2:
        return f"❌ 비교 구간 데이터가 부족합니다."
    
    price_from, price_to = df["Close"].iloc[[0, -1]]
    pct = (price_to / price_from - 1) * 100
    return f"{stock_name}의 {date_to} → {date_from} 변동률은 {pct:.2f}%입니다."

