import os, sys, json, time, yaml
from pathlib import Path
from typing import List, Dict

import yfinance as yf
import pandas as pd
from redis.cluster import RedisCluster, ClusterNode

# ── 1. 설정 파일 로드 ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
with (BASE_DIR / "config.yaml").open("r", encoding="utf-8") as f:
    cfg = yaml.safe_load(f)

startup_nodes_cfg = cfg["redis_cluster"]["startup_nodes"]  # [{'host':..., 'port':...}, ...]
startup_nodes = [ClusterNode(n["host"], n["port"]) for n in startup_nodes_cfg]

csv_path      = BASE_DIR / cfg["file_paths"]["krx_tickers"]  # 상대경로 → 절대경로
if not csv_path.exists():
    sys.exit(f"❌ CSV 파일을 찾을 수 없습니다: {csv_path}")

# ── 2. Redis 클러스터 연결 ─────────────────────────────────────────
# redis_pw = os.getenv("REDIS_PASSWORD")  # 필요 없으면 None
redis_cli = RedisCluster(
    startup_nodes=startup_nodes,
    decode_responses=True,
    # password=redis_pw,
)
print("✅ Redis 연결 완료")

# ── 3. 티커 목록 준비 (.KS suffix) ────────────────────────────────
df = pd.read_csv(csv_path)
required_cols = {"code", "market"}
if not required_cols.issubset(set(df.columns)):
    sys.exit(f"❌ CSV에 code·market 열이 없습니다: {df.columns}")
suffix_map = {"KOSPI": ".KS", "KOSDAQ": ".KQ", "KONEX": ".KN"}

def to_symbol(row):
    code6   = str(row["code"]).zfill(6)
    market  = row["market"]
    suffix  = suffix_map.get(market, ".KS")
    return f"{code6}{suffix}"

df["symbol"] = df.apply(to_symbol, axis=1)

symbols        = df["symbol"].tolist()
symbol2market  = dict(zip(df["symbol"], df["market"]))
symbol2code    = dict(zip(df["symbol"], df["code"].astype(str).str.zfill(6)))

print(f"📈 총 {len(symbols):,}개 티커 로드")

# ── 4. 기간 설정 & 배치 파라미터 ──────────────────────────────────
START_DATE = "2024-01-01"
END_DATE   = "2025-07-31"
BATCH_SIZE      = 100   # yfinance 동시 다운로드 종목수
SLEEP_SEC      = 2     # 배치 간 대기(초)

def chunks(lst: List[str], n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]

# ── 5. 다운로드 → Redis 저장 ──────────────────────────────────────
total_rows = 0

for batch_idx, batch_syms in enumerate(chunks(symbols, BATCH_SIZE), 1):
    print(f"\n🚚 Batch {batch_idx}: {len(batch_syms)} tickers")

    df_batch = yf.download(
        tickers=" ".join(batch_syms),
        start=START_DATE,
        end=END_DATE,
        group_by="ticker",
        progress=False,
        threads=True,
        auto_adjust=False,      # 실패 티커 무시
    )
    if df_batch.empty:
        print("⚠️  전부 다운로드 실패, 건너뜀")
        continue

    pipe = redis_cli.pipeline()
    for sym in batch_syms:
        if sym not in df_batch.columns.levels[0]:
            print(f"⚠️  {sym} 데이터 없음, 스킵")
            continue

        sub = df_batch[sym].dropna()
        market = symbol2market[sym]
        code6  = symbol2code[sym]

        for d, row in sub.iterrows():
            date_str = d.strftime("%Y-%m-%d")
            key = f"{date_str}:{market}:{code6}"
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

        total_rows += len(sub)

    pipe.execute()
    print(f"✅ Batch {batch_idx} 완료, 누적 {total_rows:,} rows 저장")
    time.sleep(SLEEP_SEC)

print(f"\n🎉 전체 완료: {total_rows:,} rows Redis 적재")
redis_cli.close()