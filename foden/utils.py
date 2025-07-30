from datetime import datetime, timedelta
import pandas as pd
import re
import yfinance as yf

def get_today_date() -> str:
    '''
    오늘 날짜를 "YYYY-MM-DD" 형식으로 반환합니다.
    '''
    return datetime.now().strftime("%Y-%m-%d")

def name_to_ticker(name: str, csv_path="/Users/yoon/MIRAE_ASSET_AI-Festival/krx_tickers.csv"):
    '''
    코스피/코스닥 한글명(종목명) → 6자리 코드.KS/KQ(티커명)
    '''

    df = pd.read_csv(csv_path)
    name_std = name.strip()
    row = df.loc[df["name"] == name_std]
    if row.empty:
        return None

    ticker = row["code"].iloc[0].zfill(6)
    return f"{ticker}.KS" if ticker[0] == "0" else f"{ticker}.KQ"

def ticker_to_name(ticker: str, csv_path="/Users/yoon/MIRAE_ASSET_AI-Festival/krx_tickers.csv") -> str | None:
    """
    6자리 코드.KS/KQ(티커명) → 코스피/코스닥 한글명(종목명)
    """
    code = ticker.split(".")[0].zfill(6)

    df = pd.read_csv(csv_path, dtype=str)
    row = df.loc[df["code"] == code]
    if row.empty:
        return None

    return row["name"].iloc[0]

def normalize_date(date_str: str | None = None) -> str:
    """
    • date_str가 None 이면 → 오늘 날짜
    • '오늘', '어제', '그제', '일주일전' 같은 한국어 상대표현 처리
    • 숫자·슬래시·'월/일' 포맷 등 폭넓게 지원
    ▸ 반환: 'YYYY-MM-DD'
    """

    # 기준 날짜
    today = datetime.today()
    weekday_num = today.weekday()  
    kor = ["월", "화", "수", "목", "금", "토", "일"]
    weekday_kr = kor[weekday_num] + "요일"  

    # ── 0) '지난주 ○요일' 핸들링 ───────────────────
    m = re.fullmatch(r"^지난주\s*([월화수목금토일])요일?$", date_str or "", re.I)
    if m:
        target_wd = kor.index(m.group(1))
        # 지난주 기준일 = today - 7일
        last_week = today - timedelta(days=7)
        # 그 주(지난주)의 target_wd 계산
        # last_week.weekday(): Mon=0…Sun=6
        delta = target_wd - last_week.weekday()
        return (last_week + timedelta(days=delta)).strftime("%Y-%m-%d")

    # 1) None → 오늘
    if date_str is None or str(date_str).strip() == "":
        return today.strftime("%Y-%m-%d")(weekday_kr)

    s = date_str.strip()

    # 2) 상대 표현 매핑
    rel_map = {
        r"^오늘$": 0,
        r"^어제$": -1,
        r"^그제$": -2,
        r"^(\d+)일[전 ago]*$": lambda m: -int(m.group(1)),
        r"^(일|1)주일?전$": -7,
        r"^지난주$": -7,
        r"^(한|1)달전$": -30,
    }
    for pat, delta in rel_map.items():
        m = re.fullmatch(pat, s, re.I)
        if m:
            offset = delta(m) if callable(delta) else delta
            dt = today + timedelta(days=offset).strftime("%Y-%m-%d")
            weekday = kor[dt.weekday()]
            return f"{dt} ({weekday})"

    # 3) YYYYMMDD
    if re.fullmatch(r"\d{8}", s):
        date_std = datetime.strptime(s, "%Y%m%d").strftime("%Y-%m-%d")
        dt       = datetime.strptime(date_std, "%Y-%m-%d")
        weekday_kr = kor[dt.weekday()] + "요일"
        return f"{date_std} ({weekday_kr})"

    # 4) ISO(YYYY-MM-DD)
    try:
        date_std = datetime.strptime(s, "%Y-%m-%d").strftime("%Y-%m-%d")
        dt       = datetime.strptime(date_std, "%Y-%m-%d")
        weekday_kr = kor[dt.weekday()] + "요일"
        return f"{date_std} ({weekday_kr})"
    except ValueError:
        pass

    # 5) 'M월D일', 'MM/DD', 'MM.DD'
    m = re.fullmatch(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일", s)
    if m:
        month, day = map(int, m.groups())
        date_std   = datetime(today.year, month, day).strftime("%Y-%m-%d")
        dt         = datetime.strptime(date_std, "%Y-%m-%d")
        weekday_kr = kor[dt.weekday()] + "요일"
        return f"{date_std} ({weekday_kr})"

    m = re.fullmatch(r"(\d{1,2})[./\s](\d{1,2})", s)
    if m:
        month, day = map(int, m.groups())
        date_std   = datetime(today.year, month, day).strftime("%Y-%m-%d")
        dt         = datetime.strptime(date_std, "%Y-%m-%d")
        weekday_kr = kor[dt.weekday()] + "요일"
        return f"{date_std} ({weekday_kr})"

    # 6) 파이널 폴백
    try:
        date_std = pd.to_datetime(s).strftime("%Y-%m-%d")
        weekday_kr = kor[dt.weekday()] + "요일"
        return f"{date_std} ({weekday_kr})"
    except Exception:
        raise ValueError(f"지원하지 않는 날짜 형식: {date_str}")

def download_batch(tickers: list[str], start: str, end: str) -> pd.DataFrame | None:
    """
    - 빈 DataFrame 이면 None
    - NaN-only 티커 열 제거(dropna)
    - 남은 것이 0개면 None
    - MultiIndex·단일 Index 관계없이 DataFrame 반환
    """
    try:
        df = yf.download(
            " ".join(tickers),
            start=start,
            end=end,
            interval="1d",
            group_by="ticker",
            threads=False,
            progress=False,
            auto_adjust=False        # ← 경고 억제용(기존 기본값 유지)
        )
    except ValueError as e:
        # "No objects to concatenate" → 빈 배치
        if "No objects to concatenate" in str(e):
            return None
        raise

    if df.empty:
        return None

    # 티커 단위로 모두 NaN 인 열 제거
    df = df.dropna(axis=1, how="all")
    if df.empty:
        return None

    # 단일 DF(컬럼: Open/High/…) → MultiIndex 로 강제
    # if not isinstance(df.columns, pd.MultiIndex):
    #     tkr = df.name if hasattr(df, "name") else tickers[0]
    #     df = pd.concat({tkr: df}, axis=1)
    if not isinstance(df.columns, pd.MultiIndex):
        df.columns = pd.MultiIndex.from_product([[tickers[0]], df.columns])

    return df
