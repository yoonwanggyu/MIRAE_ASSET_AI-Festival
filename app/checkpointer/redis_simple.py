# app/checkpointer/redis_simple.py
import json
from typing import Any, Dict, Optional, Tuple
from langgraph.checkpoint.base import BaseCheckpointSaver  # 실제 버전 경로 확인
# aget_tuple 반환 타입은 (checkpoint, metadata, parent_config) 형태

class AsyncSimpleRedisSaver(BaseCheckpointSaver):
    def __init__(self, redis_client, prefix: str = "lg:ckpt"):
        self.redis = redis_client
        self.prefix = prefix

    def _key(self, config: Dict[str, Any]) -> str:
        """LangGraph가 넘겨주는 config 내부에 thread_id가 들어있습니다.
           기본 예시: {"configurable": {"thread_id": "xyz"}}
        """
        thread_id = config.get("configurable", {}).get("thread_id", "default")
        return f"{self.prefix}:{thread_id}"

    # --- 필수 ---
    async def aget_tuple(
        self,
        config: Dict[str, Any],
    ) -> Optional[Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]]:
        raw = await self.redis.get(self._key(config))
        if not raw:
            return None
        payload = json.loads(raw)
        return (
            payload.get("checkpoint", {}),
            payload.get("metadata", {}),
            payload.get("parent_config", {}),
        )

    async def aput_tuple(
        self,
        config: Dict[str, Any],
        checkpoint: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        parent_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        payload = {
            "checkpoint": checkpoint,
            "metadata": metadata or {},
            "parent_config": parent_config or {},
        }
        await self.redis.set(self._key(config), json.dumps(payload))

    # --- 호환용 (일부 노드에서 사용) ---
    async def aget(self, thread_id: str):
        raw = await self.redis.get(f"{self.prefix}:{thread_id}")
        if not raw:
            return None
        return json.loads(raw).get("checkpoint")

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
            "metadata": metadata or {},
            "parent_config": parent_config or {},
        }
        await self.redis.set(f"{self.prefix}:{thread_id}", json.dumps(payload))
