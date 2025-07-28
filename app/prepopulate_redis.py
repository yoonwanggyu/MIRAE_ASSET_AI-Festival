# app/prepopulate_redis.py
"""
config.yaml에 정의된 Redis‑Cluster 노드와 KRX 티커 CSV 경로를 읽어
2024‑01‑01~2025‑07‑31 일별 시세를 yfinance → Redis 에 일괄 적재합니다.
"""

import os, json, time, yaml, sys
from datetime import datetime
from pathlib import Path
from typing import List

import pandas as pd
import yfinance as yf
from redis.cluster import RedisCluster, ClusterNode

# ── 1. 설정 파일 로드 ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
with (BASE_DIR / "config.yaml").open("r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

startup_nodes_cfg = cfg["redis_cluster"]["startup_nodes"]  # [{'host':..., 'port':...}, ...]
startup_nodes = [ClusterNode(n["host"], n["port"]) for n in startup_nodes_cfg]

csv_path      = BASE_DIR / cfg["file_paths"]["krx_tickers"]  # 상대경로 → 절대경로

# ── 2. Redis 클러스터 연결 ─────────────────────────────────────────
# redis_pw = os.getenv("REDIS_PASSWORD")  # 필요 없으면 None
redis_cli = RedisCluster(
    startup_nodes=startup_nodes,
    decode_responses=True,
    # password=redis_pw,
)
print("✅ Redis 연결 완료")

# ── 3. 티커 목록 준비 (.KS suffix) ────────────────────────────────
tickers = (
    pd.read_csv(csv_path)["ticker"]
    .astype(str).str.zfill(6)
    .apply(lambda x: f"{x}.KS")
    .tolist()
)
print(f"📈 총 {len(tickers):,}개 티커 로드")

# ── 4. 기간 설정 & 배치 파라미터 ──────────────────────────────────
START_DATE = "2024-01-01"
END_DATE   = "2025-07-31"
BATCH      = 100   # yfinance 동시 다운로드 종목수
PAUSE      = 2     # 배치 간 대기(초)

def chunks(lst: List[str], n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]

# ── 5. 다운로드 → Redis 저장 ──────────────────────────────────────
total_rows = 0
for idx, batch in enumerate(chunks(tickers, BATCH), 1):
    print(f"\n🚚 Batch {idx}: {len(batch)} tickers")
    df = yf.download(
        tickers=" ".join(batch),
        start=START_DATE,
        end=END_DATE,
        group_by="ticker",
        threads=True,
        progress=False,
    )

    pipe = redis_cli.pipeline()
    for code_full in batch:
        code = code_full.split(".")[0]      # '005930'
        if code not in df.columns.levels[0]:
            continue

        for date, row in df[code].dropna().iterrows():
            key = f"stock:{code}:{date.strftime('%Y-%m-%d')}"
            value = json.dumps(
                {
                    "open":   round(row["Open"],  2),
                    "high":   round(row["High"],  2),
                    "low":    round(row["Low"],   2),
                    "close":  round(row["Close"], 2),
                    "volume": int(row["Volume"]),
                },
                ensure_ascii=False,
            )
            pipe.set(key, value)

        total_rows += len(df[code].dropna())

    pipe.execute()
    print(f"✅ Batch {idx} 완료, 누적 {total_rows:,} rows 저장")
    time.sleep(PAUSE)

print(f"\n🎉 전체 완료: {total_rows:,} rows Redis 적재")
redis_cli.close()
