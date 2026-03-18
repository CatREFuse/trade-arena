from __future__ import annotations

import json
from datetime import datetime

from redis.asyncio import Redis

CHANNEL = "events"


class EventService:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def publish(self, event: dict):
        payload = json.dumps(event, ensure_ascii=False, default=str)
        await self.redis.publish(CHANNEL, payload)
        await self.redis.lpush("events:recent", payload)
        await self.redis.ltrim("events:recent", 0, 199)
