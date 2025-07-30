import pandas as pd
import yfinance as yf
import yaml
from datetime import datetime, timedelta

# [수정] Redis 클러스터 클라이언트를 임포트합니다.
from rediscluster import RedisCluster
from rediscluster.exceptions import RedisClusterException

def connect_to_ncloud_redis_cluster(config):
    """
    nCloud Redis Cluster에 연결하는 함수.
    config.prod.yaml의 startup_nodes 정보를 사용합니다.
    """
    # [수정] 클러스터 노드 정보를 읽어옵니다.
    redis_config = config['redis_cluster']
    startup_nodes = [
        {"host": node['host'], "port": node['port']} 
        for node in redis_config['startup_nodes']
    ]

    try:
        # [수정] RedisCluster 클라이언트를 생성합니다.
        client = RedisCluster(startup_nodes=startup_nodes, decode_responses=True)
        client.ping()
        print("✅ nCloud Redis Cluster 연결 성공")
        return client
    except RedisClusterException as e:
        print(f"❌ nCloud Redis Cluster 연결 실패: {e}")
        raise

def main():
    """최근 1년 치의 KOSPI/KOSDAQ 종가 및 거래량 데이터를 nCloud Redis Cluster에 저장합니다."""
    # 1. 설정 및 티커 목록 로드
    # [수정] nCloud 접속 정보가 담긴 'production'용 설정 파일을 사용합니다.
    with open("config.yaml", 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    r = connect_to_ncloud_redis_cluster(config)

    ticker_file_path = config['file_paths']['krx_tickers']
    tickers_df = pd.read_csv(ticker_file_path, dtype={"code": str})
    
    tickers_df["suffix"] = tickers_df["market"].apply(lambda x: ".KS" if x.upper() == "KOSPI" else ".KQ")
    tickers = (tickers_df["code"] + tickers_df["suffix"]).tolist()
    
    # 2. 데이터 조회 기간 설정 (최근 1년)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730)
    
    print(f"데이터 조회 기간: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}")
    print(f"총 {len(tickers)}개 종목의 데이터 저장 시작...")

    # 3. yfinance로 데이터 다운로드
    hist_df = yf.download(tickers, start=start_date, end=end_date, progress=True)

    if hist_df.empty:
        print("❌ 데이터를 다운로드하지 못했습니다.")
        return

    # 4. Redis에 저장하기 좋은 형태로 데이터 가공
    close_df = hist_df['Close'].stack().reset_index()
    close_df.columns = ['Date', 'Ticker', 'Close']
    
    volume_df = hist_df['Volume'].stack().reset_index()
    volume_df.columns = ['Date', 'Ticker', 'Volume']
    
    print("데이터 가공 완료. Redis에 저장을 시작합니다...")

    # 5. Redis 파이프라인을 사용하여 데이터 저장
    # 클러스터 클라이언트도 파이프라인을 지원하여 효율적인 저장이 가능합니다.
    pipeline = r.pipeline()
    total_saved = 0
    
    # 종가 저장
    for _, row in close_df.dropna().iterrows():
        date_str = row['Date'].strftime('%Y-%m-%d')
        key = f"hist:{row['Ticker']}:Close"
        pipeline.hset(key, date_str, row['Close'])
        total_saved += 1

    # 거래량 저장
    for _, row in volume_df.dropna().iterrows():
        date_str = row['Date'].strftime('%Y-%m-%d')
        key = f"hist:{row['Ticker']}:Volume"
        pipeline.hset(key, date_str, row['Volume'])
        total_saved += 1

    pipeline.execute()
    print(f"✅ 총 {total_saved // 2}개 종목의 {total_saved}개 데이터 포인트를 Redis에 저장했습니다.")


if __name__ == "__main__":
    main()