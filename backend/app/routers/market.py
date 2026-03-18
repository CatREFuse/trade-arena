from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas import QuoteOut
from app.services.market_data import MarketDataService

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/quote/{ticker}", response_model=QuoteOut)
async def get_quote(ticker: str, request: Request):
    redis = request.app.state.redis
    svc = MarketDataService(redis)
    return await svc.get_quote(ticker.upper())
