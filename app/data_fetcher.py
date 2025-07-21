import pandas as pd
import yfinance as yf
from datetime import timedelta
from typing import Dict, Any
import concurrent.futures

from utils import *


def fetch_stock_metadata(stock_name: str) -> tuple[Dict[str, Any] | None, str | None]:
    """
    특정 종목의 실시간 메타데이터(PBR, PER 등)를 조회합니다.
    성공 시 (info 딕셔너리, None), 실패 시 (None, 에러 메시지)를 반환합니다.
    """
    try:
        ticker = name_to_ticker(stock_name)
        if not ticker:
            return None, f"❌ '{stock_name}' 종목을 찾을 수 없습니다."

        stock_info = yf.Ticker(ticker).info
        if not stock_info or stock_info.get('regularMarketPrice') is None:
             return None, f"❌ '{stock_name}'의 메타데이터를 가져올 수 없습니다."
        
        return stock_info, None
    except Exception as e:
        return None, f"❌ 메타데이터 조회 중 오류 발생: {e}"


def fetch_stock_history(stock_name: str, date: str, days_before: int = 1) -> tuple[pd.DataFrame | None, str | None]:
    """
    지정된 종목과 날짜에 대한 시계열 데이터를 조회합니다.
    성공 시 (DataFrame, None), 실패 시 (None, 에러 메시지)를 반환합니다.
    """
    try:
        date_std_raw = normalize_date(date)
        date_std = pd.Timestamp(date_std_raw.split(" ")[0])
        ticker = name_to_ticker(stock_name)
        if not ticker:
            return None, f"❌ '{stock_name}' 종목을 찾을 수 없습니다."

        start_date = date_std - timedelta(days=days_before)
        end_date = date_std + timedelta(days=1)
        
        hist = yf.Ticker(ticker).history(start=start_date, end=end_date, auto_adjust=False)
        
        if hist.empty:
            return None, f"❌ '{date_std_raw}'을 포함한 기간의 거래 데이터가 없습니다."
        
        return hist, None
    except Exception as e:
        return None, f"❌ 시계열 데이터 조회 중 오류 발생: {e}"

def fetch_batch_history(tickers: List[str], start_date: pd.Timestamp, end_date: pd.Timestamp, batch_size: int = 200) -> pd.DataFrame | None:
    """
    여러 티커의 시계열 데이터를 배치 단위로 병렬 다운로드합니다.
    성공 시 MultiIndex DataFrame, 실패 시 None을 반환합니다.
    """
    def download_single_batch(batch: List[str]) -> pd.DataFrame | None:
        """단일 배치 다운로드를 위한 내부 함수"""
        try:
            df = yf.download(
                batch,
                start=start_date.strftime("%Y-%m-%d"),
                end=end_date.strftime("%Y-%m-%d"),
                interval="1d",
                group_by="ticker",
                progress=False,
                threads=True,
                auto_adjust=False
            )
            if df.empty: return None
            # 전부 NaN인 열 제거
            df = df.dropna(axis=1, how='all')
            if df.empty: return None
            # 단일 티커 결과가 MultiIndex가 아닐 경우 변환
            if not isinstance(df.columns, pd.MultiIndex):
                if len(batch) == 1:
                    df.columns = pd.MultiIndex.from_product([batch, df.columns])
                else:
                    return None
            return df
        except Exception:
            return None

    all_data_frames = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [
            executor.submit(download_single_batch, tickers[i:i + batch_size])
            for i in range(0, len(tickers), batch_size)
        ]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result is not None:
                all_data_frames.append(result)

    if not all_data_frames:
        return None

    # 모든 DataFrame을 하나로 합치고 중복 티커 제거
    combined_df = pd.concat(all_data_frames, axis=1)
    return combined_df.loc[:, ~combined_df.columns.get_level_values(0).duplicated(keep='first')]