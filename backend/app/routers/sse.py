from __future__ import annotations

import json

from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

router = APIRouter(tags=["sse"])


@router.get("/api/sse/events")
async def sse_events(request: Request):
    redis = request.app.state.redis

    async def event_generator():
        # 先发送最近的历史事件
        recent = await redis.lrange("events:recent", 0, 49)
        for item in reversed(recent):
            raw = item.decode() if isinstance(item, bytes) else item
            data = json.loads(raw)
            yield {"event": data.get("type", "unknown"), "data": raw}

        # 订阅实时事件
        pubsub = redis.pubsub()
        await pubsub.subscribe("events")
        try:
            async for message in pubsub.listen():
                if await request.is_disconnected():
                    break
                if message["type"] == "message":
                    raw = (
                        message["data"].decode()
                        if isinstance(message["data"], bytes)
                        else message["data"]
                    )
                    data = json.loads(raw)
                    yield {"event": data.get("type", "unknown"), "data": raw}
        finally:
            await pubsub.unsubscribe("events")

    return EventSourceResponse(event_generator())
