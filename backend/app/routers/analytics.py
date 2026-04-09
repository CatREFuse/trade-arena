from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.services.traffic_analytics import TrafficAnalyticsService

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


class PageViewPayload(BaseModel):
    path: str = "/"


def _extract_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "")
    if forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        if first:
            return first

    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip

    if request.client and request.client.host:
        return request.client.host
    return "unknown"


@router.post("/pageview")
async def record_pageview(payload: PageViewPayload, request: Request):
    service = TrafficAnalyticsService(request.app.state.redis)
    path = service.normalize_path(payload.path)
    if not service.should_track(path):
        return {"ok": True, "ignored": True}

    raw_ip = _extract_client_ip(request)
    await service.record_pageview(path=path, raw_ip=raw_ip)
    return {"ok": True}
