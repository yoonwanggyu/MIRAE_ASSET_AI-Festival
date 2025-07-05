from utils import *
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf
from pykrx import stock
from typing import Literal, List, Tuple


def get_info_stock(stock_name: str,date: str,field: Literal["open", "high", "low", "close", "volume","pbr","per", "시가", "고가", "저가", "종가", "거래량"] = "close") -> str:
    """
    단일 날짜의 시가·고가·저가·종가·거래량 조회
    """
    try:
        date_std_raw = normalize_date(date)  
    except ValueError as e:
        return f"❌ {e}"
    
    date_std = date_std_raw.split(" ")[0] 

    ticker = name_to_ticker(stock_name)
    if not ticker:
        return f"❌ '{stock_name}' 종목을 찾을 수 없습니다."
    
    col_map = {
        "open":   "Open",   "시가":   "Open",
        "high":   "High",   "고가":   "High",
        "low":    "Low",    "저가":   "Low",
        "close":  "Close",  "종가":   "Close",
        "volume": "Volume", "거래량": "Volume",
        "pbr":    "PBR",    "per":    "PER",
    }
    key = col_map.get(field.lower() if field.isascii() else field)
    if not key:
        return "❌ field 값이 잘못되었습니다. (시가/고가/저가/종가/거래량)"

    # ── yf.Ticker 객체: 내부적으로 1번만 다운로드 후 캐시 ──
    stock = yf.Ticker(ticker)
    d0 = pd.Timestamp(date_std)
    d1 = d0 + timedelta(days=1)

    # ─────────────── PBR / PER 처리 ───────────────
    if key in ("PBR", "PER"):
        info = stock.info  # yfinance 에서 제공하는 메타데이터
        if key == "PBR":
            val = info.get("priceToBook")
        else:  # PER
            # trailingPE 또는 forwardPE 중 선호하시는 것으로
            val = info.get("trailingPE") # or info.get("forwardPE")
        if val is None:
            return f"❌ {stock_name}의 {key} 정보를 가져올 수 없습니다."
        return f"{stock_name}의 현재 {key}는 {val:.2f} 입니다."

    hist = stock.history(start=d0, end=d1, interval="1d", auto_adjust=False)
    if hist.empty:
        return f"❌ {date_std_raw} 거래 데이터가 없습니다."

    value = hist[key].iloc[0]
    value_fmt = f"{int(value):,}주" if key == "Volume" else f"{value:,.0f}원"

    field_disp = field.upper() if field.isascii() else field  # 출력용
    return f"{stock_name}의 {date_std_raw} {field_disp}는 {value_fmt}입니다."

def _top_by(date: str, metric: Literal["volume", "gain", "drop"], n: int = 10,reverse=True) -> List[Tuple[str, float]]:
    '''
    거래량‧상승률‧하락률 TOP N 종목 뽑는 함수
    ex) 5월28일에서 거래량 기준 상위 10개 종목은?
        5월 2일 하락률 1~3위는?
        오늘 상승률 상위 5개 종목?
    '''
    try:
        date_std_raw = normalize_date(date)  
    except ValueError as e:
        return f"❌ {e}"
    
    date_std = date_std_raw.split(" ")[0] 
    # krx_codes = stock.get_market_ticker_list(date_std.replace("-", ""))

    df = pd.read_csv("/Users/yoon/MIRAE_ASSET_AI-Festival/krx_tickers.csv",dtype=str)
    krx_codes = df['code'].tolist() 
    if not krx_codes:
        raise ValueError(f"{date_std} 기준 상장 종목을 찾을 수 없습니다.")

    # 2) Yahoo 코드 (.KS/.KQ) 변환
    yf_codes = [f"{c}.KS" if c[0] == "0" else f"{c}.KQ" for c in krx_codes]

    def chunks(lst, size):  # 간단한 제네레이터
        for i in range(0, len(lst), size):
            yield lst[i : i + size]

    d0 = pd.Timestamp(date_std)
    d1 = d0 + pd.Timedelta(days=1)
    frames = []
    for batch in chunks(yf_codes, 200):
        try:
            df = yf.download(
                batch,
                start=d0.strftime("%Y-%m-%d"),
                end=d1.strftime("%Y-%m-%d"),
                group_by="ticker",
                progress=False,
            )
            frames.append(df)
        except Exception as e:
            print(f"[WARN] yfinance batch 실패: {e}")
    if not frames:
        raise RuntimeError("야후 파이낸스 데이터를 가져오지 못했습니다.")
    data = pd.concat(frames, axis=1)

    rows: List[Tuple[str, float]] = []
    for code in yf_codes:
        try:
            s = data[code]
            if s.empty:
                continue
            if metric == "volume":
                vol = s["Volume"].iloc[0]
                if pd.isna(vol):    # 결측값 건너뛰기
                    continue
                val = int(vol)
            else:
                open_, close_ = s["Open"].iloc[0], s["Close"].iloc[0]
                if pd.isna(open_) or pd.isna(close_):
                    continue
                val = (close_ / open_ - 1) * 100
            rows.append((code[:-3], val))  # ".KS" → 제거
        except KeyError:
            continue

    if not rows:
        raise RuntimeError("계산 가능한 종목이 없습니다.")

    # 5) 정렬 및 상위 N 추출
    reverse = (metric != "drop")  # drop(하락률)은 오름차순
    rows.sort(key=lambda x: x[1], reverse=reverse)
    return rows[: n]

def get_top_volume(date: str, top_n: int = 10):
    rows = _top_by(date, "volume", n=top_n, reverse=True)
    # txt = [f"{i+1}. {nm} - {vol:,}주" for i, (nm, vol) in enumerate(rows)]
    # return f"{date} 거래량 TOP {top_n}:\n" + "\n".join(txt)
    lines = []
    for i, (ticker, vol) in enumerate(rows):
        name = ticker_to_name(ticker)
        lines.append(f"{i+1}. {name}({ticker}) – {vol:,}주")

    header = f"{date} 거래량 TOP {top_n}:\n"
    return header + "\n".join(lines)

def get_top_gain(date: str, top_n: int = 10):
    rows = _top_by(date, "gain", n=top_n, reverse=True)
    # txt = [f"{i+1}. {nm} ▲ {chg:.2f}%" for i, (nm, chg) in enumerate(rows)]
    # return f"{date} 상승률 TOP {top_n}:\n" + "\n".join(txt)
    lines = []
    for i, (ticker, chg) in enumerate(rows):
        name = ticker_to_name(ticker)
        lines.append(f"{i+1}. {name}({ticker}) ▲ {chg:.2f}%")

    header = f"{date} 상승률 TOP {top_n}:\n"
    return header + "\n".join(lines)

def get_top_drop(date: str, top_n: int = 10):
    rows = _top_by(date, "drop", n=top_n, reverse=False)
    # txt = [f"{i+1}. {nm} ▼ {chg:.2f}%" for i, (nm, chg) in enumerate(rows)]
    # return f"{date} 하락률 TOP {top_n}:\n" + "\n".join(txt)
    lines = []
    for i, (ticker, chg) in enumerate(rows):
        name = ticker_to_name(ticker)
        lines.append(f"{i+1}. {name}({ticker}) ▼ {chg:.2f}%")

    header = f"{date} 하락률 TOP {top_n}:\n"
    return header + "\n".join(lines)