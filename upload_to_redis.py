import os, sys, json, time, yaml
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv
load_dotenv()
import yfinance as yf
import pandas as pd
from redis.cluster import RedisCluster, ClusterNode


# ── 1. Redis 클러스터 연결 ─────────────────────────────────────────
# redis_pw = os.getenv("REDIS_PASSWORD")  # 필요 없으면 None
redis_cli = RedisCluster(
    host=os.getenv("REDIS_HOST"),
    port=os.getenv("REDIS_PORT", 6379),
    decode_responses=True,
    # password=redis_pw,
)
print("✅ Redis 연결 완료")

try:
    deleted_count = 0
    for key in redis_cli.scan_iter(match="*"):
        redis_cli.delete(key)
        deleted_count += 1
        if deleted_count % 10000 == 0:
            print(f"🗑️  {deleted_count:,}개 키 삭제 완료...")
    
    print(f"✅ Redis 모든 키 삭제 완료 (총 {deleted_count:,}개 키 삭제)")

except Exception as e:
    print(f"❌ Redis 키 삭제 실패: {e}")
# ── 2. 티커 목록 준비 (.KS suffix) ────────────────────────────────
df = pd.read_csv('data/krx_tickers_with_market.csv')
required_cols = {"code", "market", "name"}
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
symbol2name    = dict(zip(df["symbol"], df["name"]))

print(f"📈 총 {len(symbols):,}개 티커 로드")

# ── 3. 기간 설정 & 배치 파라미터 ──────────────────────────────────
START_DATE = "2024-01-01"
END_DATE   = "2025-07-31"
BATCH_SIZE      = 100   # yfinance 동시 다운로드 종목수
SLEEP_SEC      = 2     # 배치 간 대기(초)

def chunks(lst: List[str], n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]

# ── 4. 다운로드 → Redis 저장 ──────────────────────────────────────
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
        name   = symbol2name[sym]
        try:
            ticker_info = yf.Ticker(sym).info
            market_cap = ticker_info.get("marketCap")
            if market_cap is None:
                market_cap = 0
        except Exception as e:
            print(f"⚠️  {sym} 시가총액 정보 가져오기 실패: {e}")
            market_cap = 0
        for d, row in sub.iterrows():
            date_str = d.strftime("%Y-%m-%d")
            key = f"{date_str}:{market}:{code6}:{name}"
            index_key = f"date:{{{date_str}}}"
            value = json.dumps(
                {
                    "Open":   round(row["Open"],  2),
                    "High":   round(row["High"],  2),
                    "Low":    round(row["Low"],   2),
                    "Close":  round(row["Close"], 2),
                    "Volume": int(row["Volume"]),
                    "marketCap": market_cap,
                },
                ensure_ascii=False,
            )
            pipe.set(key, value)
            pipe.sadd(index_key, key)

        total_rows += len(sub)

    pipe.execute()
    print(f"✅ Batch {batch_idx} 완료, 누적 {total_rows:,} rows 저장")
    time.sleep(SLEEP_SEC)

print(f"\n🎉 전체 완료: {total_rows:,} rows Redis 적재")
redis_cli.close()