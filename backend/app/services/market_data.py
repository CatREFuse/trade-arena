from __future__ import annotations

import asyncio
import json
import logging
import random

from redis.asyncio import Redis

from app.schemas import QuoteOut

logger = logging.getLogger(__name__)

CACHE_TTL = 60

# Mock prices for development when yfinance is unavailable
MOCK_PRICES = {
    "AAPL": 195.0, "MSFT": 425.0, "NVDA": 890.0, "GOOGL": 175.0,
    "AMZN": 205.0, "META": 510.0, "TSLA": 245.0, "BRK-B": 420.0,
    "JPM": 215.0, "V": 290.0, "UNH": 520.0, "MA": 485.0,
    # A股
    "600519.SS": 1680.0, "601318.SS": 48.0, "600036.SS": 35.0,
    "000858.SZ": 135.0, "300750.SZ": 210.0, "601899.SS": 18.0,
}


def fetch_yfinance_quote(ticker: str) -> dict:
    import yfinance as yf

    t = yf.Ticker(ticker)
    info = t.fast_info
    price = float(info.get("lastPrice", 0) or info.get("previousClose", 0))
    prev_close = float(info.get("previousClose", price))
    change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0
    return {
        "price": price,
        "change_pct": round(change_pct, 2),
        "volume": int(info.get("lastVolume", 0) or 0),
        "market_status": "open",
    }


def fetch_mock_quote(ticker: str) -> dict:
    base_price = MOCK_PRICES.get(ticker, 100.0)
    jitter = random.uniform(-0.02, 0.02)
    price = round(base_price * (1 + jitter), 2)
    change_pct = round(jitter * 100, 2)
    return {
        "price": price,
        "change_pct": change_pct,
        "volume": random.randint(100000, 10000000),
        "market_status": "open",
    }


class MarketDataService:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def get_quote(self, ticker: str) -> QuoteOut:
        cache_key = f"quote:{ticker}"
        cached = await self.redis.get(cache_key)
        if cached:
            raw = cached.decode() if isinstance(cached, bytes) else cached
            data = json.loads(raw)
            return QuoteOut(ticker=ticker, **data)

        try:
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, fetch_yfinance_quote, ticker)
        except Exception as e:
            logger.warning("yfinance failed for %s: %s, using mock data", ticker, e)
            data = fetch_mock_quote(ticker)

        await self.redis.setex(cache_key, CACHE_TTL, json.dumps(data))
        return QuoteOut(ticker=ticker, **data)
