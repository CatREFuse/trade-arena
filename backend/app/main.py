from __future__ import annotations

from contextlib import asynccontextmanager

import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import health, accounts, trade, market, leaderboard, sse


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: 创建 Redis 连接
    app.state.redis = aioredis.from_url(
        settings.redis_url, decode_responses=False
    )
    yield
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
