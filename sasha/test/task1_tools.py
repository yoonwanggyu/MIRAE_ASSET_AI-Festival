from utils import *
from datetime import datetime, timedelta
import pandas as pd
import yfinance as yf
from pykrx import stock
from typing import Literal, List, Tuple
import concurrent.futures


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

    df = pd.read_csv("/mnt/c/Users/rladl/Desktop/Mirae_Agent/MIRAE_ASSET_AI-Festival/sasha/test/krx_tickers_cleaned.csv",dtype=str)
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

def get_top_volume(date: str, top_n: int = 1):
    '''거래량 상위 N종목'''
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
    '''상승률 상위 N종목'''
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
    '''하락률 상위 N종목'''
    rows = _top_by(date, "drop", n=top_n, reverse=False)
    # txt = [f"{i+1}. {nm} ▼ {chg:.2f}%" for i, (nm, chg) in enumerate(rows)]
    # return f"{date} 하락률 TOP {top_n}:\n" + "\n".join(txt)
    lines = []
    for i, (ticker, chg) in enumerate(rows):
        name = ticker_to_name(ticker)
        lines.append(f"{i+1}. {name}({ticker}) ▼ {chg:.2f}%")

    header = f"{date} 하락률 TOP {top_n}:\n"
    return header + "\n".join(lines)


def get_daily_change_rate( stock_name: str, date: str):
    """
    주어진 종목의 등락률(%) 계산
    등락률은 종가 기준 (전일 대비 얼마나 상승하거나 하락했는지를 백분율)
    """

    try:
        date_std_raw = normalize_date(date)  
    except ValueError as e:
        return f"❌ {e}"
    
    date_std = date_std_raw.split(" ")[0] 

    ticker = name_to_ticker(stock_name)
    if not ticker:
        return f"❌ '{stock_name}' 종목을 찾을 수 없습니다."

    stock = yf.Ticker(ticker)
    d0 = pd.Timestamp(date_std)
    d1 = d0 + timedelta(days=1)

    hist = stock.history(start=d0, end=d1, interval="1d", auto_adjust=False)
    if hist.empty:
        return f"❌ {date_std_raw} 거래 데이터가 없습니다."

    # 등락률 계산 (수정된 부분)
    today_close = hist['Close'].iloc[0]

    # 휴장일(주말, 공휴일) 등으로 인해 바로 전날에 데이터가 없을 수 있으므로, 여유 있게 최근 5일 데이터를 가져와서 iloc[-1]로 가장 최근 거래일의 종가를 추출
    prev_day = d0 - timedelta(days=5)
    prev_hist = stock.history(start=prev_day, end=d0, interval="1d", auto_adjust=False)

    if prev_hist.empty:
        return f"❌ {date_std_raw} 이전 거래일 종가가 없어 등락률을 계산할 수 없습니다."

    prev_close = prev_hist['Close'].iloc[-1]

    rate = ((today_close - prev_close) / prev_close) * 100

    return f"{stock_name}의 {date_std_raw} 등락률은 {rate:.2f}% 입니다."

def get_top_or_bottom_price_stocks(date: str, market: str,
                                   mode: str = "top", count: int = 1) -> str:
    """
    특정 날짜·시장 기준 종가가 가장 비싼(top) 또는 가장 저렴한(bottom) 종목
    상위 count개를 반환.
    """
    # 0) 날짜 정규화
    try:
        date_std_raw = normalize_date(date)          # 사용자 정의 함수
    except ValueError as e:
        return f"❌ {e}"
    date_std = date_std_raw.split(" ")[0]
    d0, d1   = pd.Timestamp(date_std), pd.Timestamp(date_std) + timedelta(days=1)

    # 1) 입력 검증
    market_u = market.upper()
    if market_u not in {"KOSPI", "KOSDAQ"}:
        return "❌ market은 'KOSPI', 'KOSDAQ' 중 하나여야 합니다."
    if mode not in {"top", "bottom"}:
        return "❌ mode는 'top' 또는 'bottom' 중 하나여야 합니다."

    # 2) 종목 리스트 로드
    try:
        tickers_df = pd.read_csv(
            "/mnt/c/Users/rladl/Desktop/Mirae_Agent/MIRAE_ASSET_AI-Festival/sasha/test/krx_tickers_cleaned.csv",
            dtype={"code": str}
        )
    except FileNotFoundError:
        return "❌ 종목 리스트 파일을 찾을 수 없습니다."

    mdf = tickers_df[tickers_df["market"].str.upper() == market_u]
    codes   = mdf["code"].tolist()
    suffix  = ".KS" if market_u == "KOSPI" else ".KQ"
    tickers = [c + suffix for c in codes]

    # 3) 멀티스레드 배치 다운로드
    results_dict: dict[str, tuple[str, float]] = {}      # code → (name, close)
    start, end = d0, d1

    with concurrent.futures.ThreadPoolExecutor() as ex:
        futures = [ex.submit(download_batch, tickers[i:i+200], start, end)
                   for i in range(0, len(tickers), 200)]

        for fut in concurrent.futures.as_completed(futures):
            data = fut.result()
            if data is None:
                continue

            for tkr in data.columns.levels[0]:
                try:
                    close = data[tkr]["Close"].dropna()
                except (KeyError, TypeError):
                    continue
                if close.empty:
                    continue

                code = tkr.split(".")[0]
                try:
                    name = mdf.loc[mdf.code == code, "name"].iloc[0]
                except IndexError:
                    name = code
                # dict 에 저장 → 중복 자동 제거 & 마지막 값으로 덮어쓰기
                results_dict[code] = (name, float(close.iloc[0]))

    if not results_dict:
        return f"❌ {date_std_raw} {market_u} 시장에서 유효 종가 데이터가 없습니다."

    # 4) 딕셔너리를 리스트로 변환 후 정렬
    results = [(nm, cd, pr) for cd, (nm, pr) in results_dict.items()]
    results.sort(key=lambda x: x[2], reverse=(mode == "top"))
    selected = results[:count]

    # 5) 출력
    title  = "가장 비싼" if mode == "top" else "가장 저렴한"
    header = f"📅 {date_std_raw} {market_u} {title} 종목 Top {count}:"
    body   = [f"{i+1}. {nm} ({cd}) – 종가: {pr:,.0f}원"
              for i, (nm, cd, pr) in enumerate(selected)]
    return "\n".join([header, *body])


def get_rising_falling_counts(date: str, market: str, mode: str) -> str:
    """
    전일비(前日比) 기준으로 특정 날짜·시장 상승/하락 종목 수 반환
    ───────────────────────────────────────────────────────────
    • date   : "YYYY-MM-DD"
    • market : "KOSPI", "KOSDAQ", "ALL"
    • mode   : "rising" | "falling"   (기본: rising)
    """
    # ---- 날짜 정규화 ------------------------------------------------------
    try:
        date_std_raw = normalize_date(date)          # 사용자 정의 함수
    except ValueError as e:
        return f"❌ {e}"

    date_std = date_std_raw.split(" ")[0]
    d0 = pd.Timestamp(date_std)

    start    = d0 - timedelta(days=1)   # 휴일 대비 5일 여유
    end      = d0 + timedelta(days=1)   # end는 exclusive → d0 포함

    # ---- 시장 입력 검증 ---------------------------------------------------
    market_u = market.upper()
    if market_u not in {"KOSPI", "KOSDAQ", "ALL"}:
        return "❌ market은 'KOSPI', 'KOSDAQ', 'ALL' 중 하나여야 합니다."
    if mode not in {"rising", "falling"}:
        return "❌ mode는 'rising' 또는 'falling' 중 하나여야 합니다."

    # ---- 종목 리스트 ------------------------------------------------------
    try:
        tickers_df = pd.read_csv(
            "/mnt/c/Users/rladl/Desktop/Mirae_Agent/MIRAE_ASSET_AI-Festival/sasha/test/krx_tickers_cleaned.csv",
            dtype={"code": str}
        )
    except FileNotFoundError:
        return "❌ 종목 리스트 파일을 찾을 수 없습니다."

    if market_u == "ALL":
        tickers_df["suffix"] = tickers_df["market"].apply(
            lambda x: ".KS" if x.upper() == "KOSPI" else ".KQ"
        )
        tickers = (tickers_df["code"] + tickers_df["suffix"]).tolist()
    else:
        mdf     = tickers_df[tickers_df["market"].str.upper() == market_u]
        suffix  = ".KS" if market_u == "KOSPI" else ".KQ"
        tickers = (mdf["code"] + suffix).tolist()

    # ---- 배치 다운로드 (MultiIndex 유지) ----------------------------------
    def download_batch(batch):
        df = yf.download(
            batch,
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
            interval="1d",
            group_by="ticker",
            progress=False,
            threads=False,
            auto_adjust=False
        )
        if df.empty:
            return None
        # 전부 NaN 열 제거
        df = df.dropna(axis=1, how="all")
        if df.empty:
            return None
        if not isinstance(df.columns, pd.MultiIndex):
            df.columns = pd.MultiIndex.from_product([[batch[0]], df.columns])
        return df

    batch_size = 200
    merged = []
    with concurrent.futures.ThreadPoolExecutor() as ex:
        futs = [
            ex.submit(download_batch, tickers[i:i+batch_size])
            for i in range(0, len(tickers), batch_size)
        ]
        for fut in concurrent.futures.as_completed(futs):
            res = fut.result()
            if res is not None:
                merged.append(res)

    if not merged:
        return f"❌ {date_std} {market_u} 시장의 가격 데이터를 불러오지 못했습니다."

    df_all = pd.concat(merged, axis=1)

    # ---- 전일비 계산 ------------------------------------------------------
    # Close 가격만 추출 → diff(1) → 0=보합, >0=상승, <0=하락
    close_df = (
        df_all.loc[:, (slice(None), "Close")]
              .droplevel(1, axis=1)                 # (티커, Close) → 티커 수준
              .diff()                               # 전일비
    )

    if date_std not in close_df.index.strftime("%Y-%m-%d"):
        return f"❌ {date_std}에 대한 종가 데이터가 없습니다."

    today_row = close_df.loc[close_df.index.strftime("%Y-%m-%d") == date_std].iloc[0]
    rising    = (today_row > 0).sum()
    falling   = (today_row < 0).sum()
    skipped   = today_row.isna().sum()              # NaN → 전일 가격 없거나 데이터 누락

    # ---- 결과 포맷 --------------------------------------------------------
    count = rising if mode == "rising" else falling
    label = "📈 상승" if mode == "rising" else "📉 하락"

    return (
        f"📅 {date_std} {market_u} 시장 기준\n"
        f"{label} 종목 수: {int(count)}개\n"
        # f"⏭️ 데이터 누락/전일가격 없음: {int(skipped)}개"
    )

def count_traded_stocks(date: str, market: str = "KOSPI") -> str:
    """
    Volume > 0 인 종목만 '거래된 종목'으로 집계
    """
    # ── 날짜 정규화 ───────────────────────────────────────
    d0 = pd.to_datetime(date)
    d1 = d0 + timedelta(days=1)

    # ── 시장 검증 ────────────────────────────────────────
    mkt = market.upper()
    if mkt not in {"KOSPI", "KOSDAQ", "ALL"}:
        return "❌ market은 'KOSPI', 'KOSDAQ', 'ALL' 중 하나여야 합니다."

    # ── 티커 리스트 로드 ─────────────────────────────────
    df_t = pd.read_csv(
        "/mnt/c/Users/rladl/Desktop/Mirae_Agent/MIRAE_ASSET_AI-Festival/sasha/test/krx_tickers_cleaned.csv",
        dtype={"code": str}
    )
    if mkt != "ALL":
        df_t = df_t[df_t["market"].str.upper() == mkt]

    suffix_map = {"KOSPI": ".KS", "KOSDAQ": ".KQ"}
    df_t["suffix"] = df_t["market"].str.upper().map(suffix_map)
    tickers = (df_t["code"] + df_t["suffix"]).tolist()

    # ── 배치 다운로드 (200개씩) ───────────────────────────
    batch_size, dfs = 200, []
    with concurrent.futures.ThreadPoolExecutor() as ex:
        futs = [
            ex.submit(
                yf.download,
                " ".join(tickers[i:i + batch_size]),
                start=d0.strftime("%Y-%m-%d"),
                end=d1.strftime("%Y-%m-%d"),
                interval="1d",
                group_by="ticker",
                progress=False,
                threads=False,
                auto_adjust=False
            )
            for i in range(0, len(tickers), batch_size)
        ]
        for fut in concurrent.futures.as_completed(futs):
            sub = fut.result()
            if not sub.empty:
                # 전부 NaN 컬럼 제거
                sub = sub.dropna(axis=1, how="all")
                if not sub.empty:
                    # 단일 티커일 경우 MultiIndex로 변환
                    if not isinstance(sub.columns, pd.MultiIndex):
                        sub.columns = pd.MultiIndex.from_product([[tickers[0]], sub.columns])
                    dfs.append(sub)

    if not dfs:
        raise RuntimeError("yfinance에서 데이터를 받아오지 못했습니다.")

    df = pd.concat(dfs, axis=1)

    # ── ① 중복 티커 열 제거 ────────────────────────────────
    #    첫 번째 등장 열만 남기고 이후 중복 MultiIndex 열은 버림
    dup_mask = df.columns.get_level_values(0).duplicated(keep="first")
    if dup_mask.any():
        df = df.loc[:, ~dup_mask]

    # ── ② Volume 한 번에 추출 → 거래 여부 판정 ────────────
    vol_df   = df.xs("Volume", level=1, axis=1, drop_level=True)
    if date not in vol_df.index.strftime("%Y-%m-%d"):
        return f"❌ {date} Volume 데이터가 없습니다."

    day_vol  = vol_df.loc[vol_df.index.strftime("%Y-%m-%d") == date].iloc[0]
    traded   = int((day_vol > 0).sum())          # Volume > 0
    skipped  = int((day_vol <= 0).sum() + day_vol.isna().sum())

    return (
        f"전체 티커 수 : {len(tickers)}개\n"
        f"📅 {date} {mkt} 시장 기준\n"
        f"거래된 종목 수 : {traded}개\n"
        f"누락·0거래량   : {skipped}개"
    )