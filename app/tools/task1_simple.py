import pandas as pd
from datetime import datetime, timedelta
from typing import Literal, List, Tuple

from langchain.tools import tool

from app.data_fetcher import *
from app.utils import get_latest_trading_day, ticker_to_name, _load_krx_tickers


def _prepare_batch_fetch(date: str, market: Literal["KOSPI", "KOSDAQ", "ALL"]) -> tuple[dict | None, str | None]:
    """
    여러 종목 조회가 필요한 도구들의 공통 준비 작업을 처리하는 내부 헬퍼.
    성공 시 {tickers, date_str, d0, d1, mdf}, 실패 시 (None, 에러 메시지) 반환.
    """
    try:
        # 똑똑한 날짜 처리 적용
        date_str = get_latest_trading_day(date)
        d0 = pd.Timestamp(date_str)
        d1 = d0 + timedelta(days=1)
        
        market_u = market.upper()
        if market_u not in {"KOSPI", "KOSDAQ", "ALL"}:
            return None, "❌ market은 'KOSPI', 'KOSDAQ', 'ALL' 중 하나여야 합니다."

        tickers_df = _load_krx_tickers()
        
        # 시장에 따라 티커 목록 생성
        if market_u == "ALL":
            tickers_df["suffix"] = tickers_df["market"].apply(lambda x: ".KS" if x.upper() == "KOSPI" else ".KQ")
            tickers = (tickers_df["code"] + tickers_df["suffix"]).tolist()
            mdf = tickers_df # mdf를 전체 df로 설정
        else:
            mdf = tickers_df[tickers_df["market"].str.upper() == market_u]
            suffix = ".KS" if market_u == "KOSPI" else ".KQ"
            tickers = (mdf["code"] + suffix).tolist()
            
        return {"tickers": tickers, "date_str": date_str, "d0": d0, "d1": d1, "mdf": mdf}, None

    except (FileNotFoundError, KeyError) as e:
        return None, f"❌ 설정 오류: {e}"
    except Exception as e:
        return None, f"❌ 입력 처리 중 오류: {e}"

# --- Tools ---

@tool
def get_stock_info(stock_name: str, 
                   date: str, 
                   field: Literal["open", "high", "low", "close", "volume", "pbr", "per", "시가", "고가", "저가", "종가", "거래량"] = "close"
                   ) -> str:
    """
    단일 날짜의 시가·고가·저가·종가·거래량 조회
    """

    # 입력값 표준화 및 매핑 테이블 정의
    col_map = {
        "open": "Open", "시가": "Open", "high": "High", "고가": "High",
        "low": "Low", "저가": "Low", "close": "Close", "종가": "Close",
        "volume": "Volume", "거래량": "Volume", "pbr": "PBR", "per": "PER",
    }
    lookup_key = str(field).lower()
    target_col = col_map.get(lookup_key)
    if not target_col:
        return f"❌ field 값이 잘못되었습니다: {field}"

    # PBR/PER와 시계열 데이터를 분기하여 처리
    if target_col in ("PBR", "PER"):
        # --- PBR/PER 처리 로직 ---
        info, error = fetch_stock_metadata(stock_name)
        if error:
            return error

        val = info.get("priceToBook") if target_col == "PBR" else info.get("trailingPE")
        if val is None:
            return f"❌ {stock_name}의 {target_col} 정보를 가져올 수 없습니다."
        return f"{stock_name}의 현재 {target_col}는 {val:.2f} 입니다."

    else:
        # --- 시가/종가 등 시계열 데이터 처리 로직 ---
        date_str = get_latest_trading_day(date)
        hist, error = fetch_stock_history(stock_name, date, days_before=1)
        if error:
            return error
        
        day_data = hist[hist.index.strftime('%Y-%m-%d') == date_str]
        if day_data.empty:
            return f"❌ {date_str} 당일의 거래 데이터가 없습니다."

        value = day_data[target_col].iloc[0]
        value_fmt = f"{int(value):,}주" if target_col == "Volume" else f"{value:,.0f}원"
        return f"{stock_name}의 {date_str} {field}는 {value_fmt}입니다."


# app/tools/task1_inquiry.py

@tool
def get_top_stocks_by_metric(date: str, top_n: int, metric: Literal["volume", "gain", "drop"]) -> str:
    """
    특정 날짜의 거래량(volume), 상승률(gain), 또는 하락률(drop) 상위 N개 종목을 조회합니다.
    """
    try:
        # 공통 준비 작업 헬퍼 호출 (날짜 처리, 티커 목록 로드 등)
        prep_result, error = _prepare_batch_fetch(date, "ALL")
        if error:
            return error

        # 중앙 데이터 페처를 통해 데이터 한번에 조회
        # 상승/하락률 계산을 위해 최소 2일치 데이터가 필요하므로 넉넉하게 조회
        df_all = fetch_batch_history(
            prep_result["tickers"], 
            start_date=prep_result["d0"] - timedelta(days=5), 
            end_date=prep_result["d1"]
            )

        if df_all is None or df_all.empty:
            return f"❌ {prep_result['date_str']} 시장 데이터를 가져오지 못했습니다."

        # 데이터 가공 및 metric 계산
        rows = []
        for tkr in df_all.columns.get_level_values(0).unique():
            try:
                s = df_all[tkr]
                # 해당 날짜에 종가 데이터가 없는 종목은 건너뜀
                if s['Close'].dropna().empty or pd.isna(s['Close'].iloc[-1]):
                    continue
                
                val = 0
                if metric == "volume":
                    val = s['Volume'].iloc[-1]
                else:  # gain or drop
                    # 등락률 계산에 필요한 데이터가 충분한지 확인
                    if len(s.dropna()) < 2 or pd.isna(s['Open'].iloc[-1]) or s['Open'].iloc[-1] == 0:
                        continue
                    # 종가/시가 기준으로 등락률 계산
                    val = (s['Close'].iloc[-1] / s['Open'].iloc[-1] - 1) * 100

                if not pd.isna(val):
                    rows.append((tkr.split('.')[0], val)) # .KS, .KQ 제거
            except (KeyError, IndexError):
                continue

        if not rows:
            return "❌ 계산 가능한 종목이 없습니다."
        
        # 정렬 및 출력 포맷팅
        reverse = (metric != "drop") # 하락률만 오름차순 정렬
        rows.sort(key=lambda x: x[1], reverse=reverse)
        
        title_map = {"volume": "거래량", "gain": "상승률", "drop": "하락률"}
        header = f"📅 {prep_result['date_str']} {title_map[metric]} TOP {top_n}"
        
        lines = []
        for i, (ticker, val) in enumerate(rows[:top_n]):
            name = ticker_to_name(ticker) or ticker
            if metric == "volume":
                lines.append(f"{i+1}. {name}({ticker}) – {int(val):,}주")
            elif metric == "gain":
                lines.append(f"{i+1}. {name}({ticker}) ▲ {val:.2f}%")
            else: # drop
                lines.append(f"{i+1}. {name}({ticker}) ▼ {val:.2f}%")
                
        return "\n".join([header, *lines])

    except Exception as e:
        return f"❌ 오류 발생: {e}"

@tool
def get_daily_change_rate(stock_name: str, date: str) -> str:
    """
    주어진 종목의 등락률(%) 계산
    등락률은 종가 기준 (전일 대비 얼마나 상승하거나 하락했는지를 백분율)
    """
    date_str = get_latest_trading_day(date)
    # 중앙 데이터 페처를 호출하여 데이터 요청
    hist, error = fetch_stock_history(stock_name, date, days_before=5)
    if error:
        return error

    # 받은 데이터를 가공하여 최종 답변 생성
    if len(hist) < 2:
        return "❌ 등락률 계산에 필요한 이전 거래일 데이터가 부족합니다."

    today_close = hist['Close'].iloc[-1]
    prev_close = hist['Close'].iloc[-2]
    
    if prev_close == 0:
        return "❌ 전일 종가가 0이라 등락률을 계산할 수 없습니다."
        
    rate = ((today_close - prev_close) / prev_close) * 100
    return f"{stock_name}의 {date_str} 등락률은 {rate:.2f}% 입니다."

@tool
def get_top_or_bottom_price_stocks(date: str, market: Literal["KOSPI", "KOSDAQ"], 
                                   mode: Literal["top", "bottom"] = "top", 
                                   count: int = 1) -> str:
    """
    특정 날짜와 시장 기준, 종가가 가장 비싼(top) 또는 가장 저렴한(bottom) 종목 N개를 조회
    """
    try:
        prep_result, error = _prepare_batch_fetch(date, market)
        if error:
            return error

        market_u = market.upper()
        date_str = prep_result['date_str']
        mdf = prep_result['mdf']
        
        # 중앙 데이터 페처를 통해 배치 데이터 조회
        data = fetch_batch_history(
            prep_result['tickers'],
            start_date=prep_result['d0'],
            end_date=prep_result['d1']
        )

        if data is None or data.empty:
            return f"❌ {date_str} {market_u} 시장에서 유효한 가격 데이터를 가져오지 못했습니다."

        # 조회된 데이터를 가공하여 결과 집계
        results_dict: dict[str, tuple[str, float]] = {}

        # 종가 데이터만 조회
        close_df = data.xs("Close", level=1, axis=1, drop_level=True)

        # 해당 날짜의 데이터 행을 가져옴
        day_data = close_df.loc[close_df.index.strftime('%Y-%m-%d') == date_str]
        if day_data.empty:
            return f"❌ {date_str} 당일의 종가 데이터가 없습니다."

        # 유효한 종가만 필터링
        valid_prices = day_data.iloc[0].dropna()
        
        for ticker, price in valid_prices.items():
            code = ticker.split(".")[0]
            name = ticker_to_name(code) or code # 캐시된 데이터 사용
            results_dict[code] = (name, float(price))

        if not results_dict:
            return f"❌ {date_str} {market_u} 시장에서 유효한 종가 데이터가 있는 종목이 없습니다."

        # 정렬 및 상위 N개 선택
        results = [(name, code, price) for code, (name, price) in results_dict.items()]
        results.sort(key=lambda x: x[2], reverse=(mode == "top"))
        selected = results[:count]

        # 결과 출력
        title = "가장 비싼" if mode == "top" else "가장 저렴한"
        header = f"📅 {date_str} {market_u} {title} 종목 Top {count}:"
        body = [f"{i+1}. {nm} ({cd}) – 종가: {pr:,.0f}원" 
                for i, (nm, cd, pr) in enumerate(selected)]
        
        return "\n".join([header, *body])
    
    except Exception as e:
        return f"❌ 오류 발생: {e}"

@tool
def get_rising_falling_counts(date: str, market: Literal["KOSPI", "KOSDAQ", "ALL"], mode: Literal["rising", "falling"]) -> str:
    """
    전일비(前日比) 기준으로 특정 날짜·시장 상승/하락 종목 수 반환
    ───────────────────────────────────────────────────────────
    • date   : "YYYY-MM-DD"
    • market : "KOSPI", "KOSDAQ", "ALL"
    • mode   : "rising" | "falling"   (기본: rising)
    """
    # ---- 날짜 정규화 ------------------------------------------------------
    try:
        prep_result, error = _prepare_batch_fetch(date, market)
        if error:
            return error

        # 헬퍼 함수로부터 필요한 변수들을 추출
        market_u = market.upper()
        date_str = prep_result['date_str']
        
        # 중앙 데이터 페처를 통해 배치 데이터 조회
        data = fetch_batch_history(
            prep_result['tickers'],
            start_date=prep_result['d0'] - timedelta(days=5),
            end_date=prep_result['d1']
        )

        if data is None or data.empty:
            return f"❌ {date_str} {market_u} 시장에서 유효한 가격 데이터를 가져오지 못했습니다."

        # ---- 전일비 계산 ------------------------------------------------------
        # Close 가격만 추출 → diff(1) → 0=보합, >0=상승, <0=하락
        close_df = data.xs("Close", level=1, axis=1, drop_level=True).diff()

        day_data = close_df.loc[close_df.index.strftime('%Y-%m-%d') == date_str]
        if day_data.empty:
            return f"❌ {date_str}에 대한 종가 데이터가 없습니다."

        today_row = day_data.iloc[0]
        rising = int((today_row > 0).sum())
        falling = int((today_row < 0).sum())

        # ---- 결과 포맷팅 --------------------------------------------------------
        count = rising if mode == "rising" else falling
        label = "📈 상승" if mode == "rising" else "📉 하락"

        return (
            f"📅 {date_str} {market_u} 시장 기준\n"
            f"{label} 종목 수: {count}개"
        )

    except Exception as e:
        return f"❌ 오류 발생: {e}"


@tool
def count_traded_stocks(date: str, market: Literal["KOSPI", "KOSDAQ", "ALL"]) -> str:
    """
    Volume > 0 인 종목만 '거래된 종목'으로 집계
    """
    try:
        prep_result, error = _prepare_batch_fetch(date, market)
        if error:
            return error

        market_u = market.upper()
        date_str = prep_result['date_str']
        
        # 중앙 데이터 페처를 통해 배치 데이터 조회
        df_all = fetch_batch_history(
            prep_result['tickers'],
            start_date=prep_result['d0'],
            end_date=prep_result['d1']
        )

        if df_all is None or df_all.empty:
            return f"❌ {date_str} {market_u} 시장의 가격 데이터를 가져오지 못했습니다."

        # 거래량 데이터 추출 및 집계
        # 'Volume' 데이터만 선택
        vol_df = df_all.xs("Volume", level=1, axis=1, drop_level=True)

        # 해당 날짜의 데이터 행 선택
        day_vol = vol_df.loc[vol_df.index.strftime('%Y-%m-%d') == date_str]
        if day_vol.empty:
            return f"❌ {date_str} 당일에 해당하는 거래량 데이터가 없습니다."

        day_vol_series = day_vol.iloc[0]
        traded = int((day_vol_series > 0).sum())
        skipped = int((day_vol_series <= 0).sum() + day_vol_series.isna().sum())

        # ---- 결과 포맷팅 --------------------------------------------------------
        return (
            f"📅 {date_str} {market_u} 시장 기준\n"
            f"- 전체 대상 종목 수: {len(prep_result['tickers'])}개\n"
            f"- 거래된 종목 수: {traded}개\n"
            f"- 거래 없거나 누락된 종목 수: {skipped}개"
        )
    except Exception as e:
        return f"❌ 오류 발생: {e}"