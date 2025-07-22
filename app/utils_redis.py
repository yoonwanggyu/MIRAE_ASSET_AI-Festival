# app/utils_redis.py
import time
import json
from typing import Dict, Any, List

async def save_qa(redis, user_id: str, question: str, answer: str, meta: Dict[str, Any] | None = None):
    ts = int(time.time()*1000)
    key = f"qa:{user_id}:{ts}"
    await redis.hset(key, mapping={
        "question": question,
        "answer": answer,
        "ts": ts,
        "meta": json.dumps(meta or {})
    })
    await redis.zadd(f"qa:idx:user:{user_id}", {key: ts})

async def get_latest_qa(redis, user_id: str, n: int = 10) -> List[Dict[str, Any]]:
    keys = await redis.zrevrange(f"qa:idx:user:{user_id}", 0, n-1)
    result = []
    for k in keys:
        h = await redis.hgetall(k)
        if h:
            h["meta"] = json.loads(h.get("meta","{}"))
            result.append(h)
    return result
