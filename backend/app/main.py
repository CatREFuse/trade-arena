from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import (
    health,
    accounts,
    trade,
    market,
    leaderboard,
    sse,
    agents,
    dev,
    files,
    admin,
)
from app.services.market_data import MarketDataService
from app.services.market_providers import close_shared_http_clients

logger = logging.getLogger(__name__)


async def _warm_market_cache(app: FastAPI) -> None:
    try:
        service = app.state.market_data_service
        await service.get_market_overview()
        logger.info("Market cache warmed")
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.warning(f"Market cache warm-up failed: {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: 创建 Redis 连接
    app.state.redis = aioredis.from_url(
        settings.redis_url, decode_responses=False
    )
    app.state.market_data_service = MarketDataService(app.state.redis)
    app.state.market_cache_warm_task = asyncio.create_task(_warm_market_cache(app))
    yield
    warm_task = getattr(app.state, "market_cache_warm_task", None)
    if warm_task:
        warm_task.cancel()
        try:
            await warm_task
        except asyncio.CancelledError:
            pass
        except Exception:
            pass
    await close_shared_http_clients()
    # Shutdown: 关闭 Redis 连接
    await app.state.redis.aclose()


app = FastAPI(title="Trade Arena API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(accounts.router)
app.include_router(trade.router)
app.include_router(market.router)
app.include_router(leaderboard.router)
app.include_router(sse.router)
app.include_router(agents.router)
app.include_router(dev.router)
app.include_router(files.router)
app.include_router(admin.router)
