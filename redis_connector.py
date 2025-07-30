import yaml
import redis
from redis.cluster import RedisCluster
import os
from dotenv import load_dotenv

load_dotenv()

# 이 변수는 애플리케이션 시작 시 생성된 연결 객체를 저장합니다.
redis_conn = None

def get_redis_connection():
    """
    생성된 Redis 연결 객체를 반환합니다.
    """
    global redis_conn
    return redis_conn

def connect_to_redis():
    """
    config.yaml을 읽어 Redis Cluster에 연결하고,
    성공 시 연결 객체를 전역 변수 redis_conn에 할당합니다.
    """
    global redis_conn

    # redis-py-cluster의 표준 방식인 startup_nodes를 사용하여 연결
    connection = RedisCluster(
        host=os.getenv('REDIS_HOST'),
        port=os.getenv('REDIS_PORT', 6379),
        decode_responses=True,
        skip_full_coverage_check=True
    )
    connection.ping()
    redis_conn = connection
    print("✅ Redis Cluster에 성공적으로 연결되었습니다.")


def close_redis_connection():
    """
    활성화된 Redis 연결을 종료합니다.
    """
    global redis_conn
    if redis_conn:
        redis_conn.close()
        print("Redis Cluster 연결이 종료되었습니다.")

