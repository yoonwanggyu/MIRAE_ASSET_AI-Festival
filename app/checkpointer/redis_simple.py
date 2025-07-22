# app/checkpointer/redis_simple.py
from __future__ import annotations
from typing import Any, Optional, Dict
import json
import asyncio

from langgraph.checkpoint.base import BaseCheckpointSaver  # 버전에 따라 경로 확인
# 0.5.x 대의 langgraph는 'from langgraph.checkpoint import BaseCheckpointSaver' 일 수도 있음
# 필요 시 실제 설치 버전에서 import 경로 확인하세요.

class AsyncSimpleRedisSaver(BaseCheckpointSaver):
    """RediSearch 없이도 동작하는, 최소 Redis 체크포인터.
    thread_id 를 key 로 쓰고, JSON 직렬화해 저장합니다.
    """
    def __init__(self, redis_client, prefix: str = "lg:ckpt"):
        self.redis = redis_client
        self.prefix = prefix

    def _key(self, thread_id: str) -> str:
        return f"{self.prefix}:{thread_id}"

    async def aput(
        self,
        thread_id: str,
        checkpoint: Dict[str, Any],
        *,
        parent_config: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        payload = {
            "checkpoint": checkpoint,
            "parent_config": parent_config or {},
            "metadata": metadata or {},
        }
        await self.redis.set(self._key(thread_id), json.dumps(payload))

    async def aget(
        self,
        thread_id: str,
    ) -> Optional[Dict[str, Any]]:
        data = await self.redis.get(self._key(thread_id))
        if not data:
            return None
        payload = json.loads(data)
        return payload.get("checkpoint")

    async def adelete(self, thread_id: str) -> None:
        await self.redis.delete(self._key(thread_id))

    # 필요 시 전체 목록 조회/검색 등을 직접 구현
    async def alist(self, limit: int = 50, offset: int = 0):
        # 간단 구현: KEYS 사용(규모 커지면 SCAN으로 교체)
        pattern = f"{self.prefix}:*"
        keys = await self.redis.keys(pattern)
        # 정렬/슬라이싱
        keys = sorted(keys)[offset:offset+limit]
        result = []
        for k in keys:
            tid = k.split(":")[-1]
            result.append({"thread_id": tid})
        return result
