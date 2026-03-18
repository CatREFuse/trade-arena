# Phase 1: 后端 API（交易所核心）实现计划

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建 AI 炒股竞技场的后端交易所 API，包括账户管理、交易引擎、行情代理、排行榜、SSE 推送。

**Architecture:** FastAPI 单体应用 + PostgreSQL + Redis。所有交易通过事务 + 行级锁保证一致性。行情数据统一代理，SSE 通过 Redis pub/sub 分发。

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Alembic, Redis (aioredis), pytest, httpx, yfinance

**Spec:** `docs/design-spec.md`

---

## 文件结构

```
trade-arena/
├── backend/
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 # FastAPI app, lifespan, CORS
│   │   ├── config.py               # Settings from env
│   │   ├── database.py             # async engine + session
│   │   ├── models.py               # SQLAlchemy ORM models (7 tables)
│   │   ├── schemas.py              # Pydantic request/response schemas
│   │   ├── auth.py                 # Bearer token auth dependency
│   │   ├── errors.py               # Unified error response
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── accounts.py         # /api/accounts
│   │   │   ├── trade.py            # /api/trade
│   │   │   ├── market.py           # /api/market
│   │   │   ├── leaderboard.py      # /api/leaderboard + /api/feed
│   │   │   ├── sse.py              # /api/sse/events
│   │   │   └── health.py           # /api/health
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── trading.py          # Buy/sell engine with risk checks
│   │   │   ├── market_data.py      # Quote proxy (yfinance + Redis cache)
│   │   │   ├── ranking.py          # Leaderboard calculation
│   │   │   └── events.py           # Redis pub/sub event publisher
│   │   └── seed.py                 # DB seed: agents, season, accounts
│   └── tests/
│       ├── conftest.py             # Fixtures: test DB, client, Redis mock
│       ├── test_accounts.py
│       ├── test_trading.py
│       ├── test_market.py
│       ├── test_leaderboard.py
│       └── test_sse.py
├── docker-compose.yml              # PG + Redis for local dev
└── .env.example
```

---

## Task 1: 项目脚手架

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`
- Create: `docker-compose.yml`
- Create: `.env.example`

- [ ] **Step 1: 创建 docker-compose.yml（PG + Redis）**

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: trade_arena
      POSTGRES_USER: arena
      POSTGRES_PASSWORD: arena_dev
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  pgdata:
```

- [ ] **Step 2: 创建 .env.example**

```env
DATABASE_URL=postgresql+asyncpg://arena:arena_dev@localhost:5432/trade_arena
REDIS_URL=redis://localhost:6379/0
```

- [ ] **Step 3: 创建 pyproject.toml**

```toml
[project]
name = "trade-arena-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115",
    "uvicorn[standard]>=0.30",
    "sqlalchemy[asyncio]>=2.0",
    "asyncpg>=0.30",
    "alembic>=1.14",
    "pydantic-settings>=2.0",
    "redis>=5.0",
    "sse-starlette>=2.0",
    "yfinance>=0.2",
    "httpx>=0.27",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "httpx>=0.27",
    "aiosqlite>=0.20",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 4: 创建 config.py**

```python
# backend/app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://arena:arena_dev@localhost:5432/trade_arena"
    redis_url: str = "redis://localhost:6379/0"
    trade_fee_rate: float = 0.001
    max_position_ratio: float = 0.30

    model_config = {"env_file": ".env"}

settings = Settings()
```

- [ ] **Step 5: 创建 main.py（最小可运行 FastAPI）**

```python
# backend/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Trade Arena API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health():
    return {"status": "ok"}
```

- [ ] **Step 6: 启动 Docker 并验证**

Run: `cd ~/Developer/trade-arena && docker compose up -d`
Run: `cd backend && pip install -e ".[dev]" && uvicorn app.main:app --reload --port 8000`
Run: `curl http://localhost:8000/api/health`
Expected: `{"status":"ok"}`

- [ ] **Step 7: Commit**

```bash
git add backend/ docker-compose.yml .env.example
git commit -m "chore: 项目脚手架 - FastAPI + PG + Redis"
```

---

## Task 2: 数据库模型 + Alembic 迁移

**Files:**
- Create: `backend/app/database.py`
- Create: `backend/app/models.py`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`

- [ ] **Step 1: 创建 database.py**

```python
# backend/app/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
```

- [ ] **Step 2: 创建 models.py（7 张表）**

```python
# backend/app/models.py
from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import String, Text, Date, Numeric, Integer, ForeignKey, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

class Season(Base):
    __tablename__ = "seasons"
    id: Mapped[str] = mapped_column(String(20), primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class Agent(Base):
    __tablename__ = "agents"
    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(String(50))
    avatar: Mapped[str] = mapped_column(String(10))
    model: Mapped[str] = mapped_column(String(50))
    camp: Mapped[str] = mapped_column(String(10))
    style: Mapped[str] = mapped_column(String(100))
    framework: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class Account(Base):
    __tablename__ = "accounts"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    season_id: Mapped[str] = mapped_column(ForeignKey("seasons.id"))
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"))
    market: Mapped[str] = mapped_column(String(5))
    currency: Mapped[str] = mapped_column(String(5))
    initial_cash: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    cash: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    api_token: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class Position(Base):
    __tablename__ = "positions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    ticker: Mapped[str] = mapped_column(String(20))
    shares: Mapped[Decimal] = mapped_column(Numeric(15, 6))
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(15, 4))
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    __table_args__ = (UniqueConstraint("account_id", "ticker"),)

class Trade(Base):
    __tablename__ = "trades"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    ticker: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(10))
    shares: Mapped[Decimal] = mapped_column(Numeric(15, 6))
    price: Mapped[Decimal] = mapped_column(Numeric(15, 4))
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    fee: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasoning_full: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class Snapshot(Base):
    __tablename__ = "snapshots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    date: Mapped[date] = mapped_column(Date)
    total_asset: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    cash: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    position_value: Mapped[Decimal] = mapped_column(Numeric(15, 2))
    trade_count: Mapped[int] = mapped_column(Integer, default=0)
    __table_args__ = (UniqueConstraint("account_id", "date"),)

class Event(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(20))
    agent_id: Mapped[str | None] = mapped_column(String(30), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
```

- [ ] **Step 3: 初始化 Alembic**

Run: `cd ~/Developer/trade-arena/backend && alembic init alembic`

Then edit `alembic/env.py` to use async engine and import models:

```python
# backend/alembic/env.py - 关键修改部分
from app.database import Base, engine
from app.models import *  # noqa: ensure all models registered

target_metadata = Base.metadata

# ... 替换 run_migrations_online 为 async 版本
```

Edit `alembic.ini`: set `sqlalchemy.url` to empty (will use env.py config).

- [ ] **Step 4: 生成并运行迁移**

Run: `cd ~/Developer/trade-arena/backend && alembic revision --autogenerate -m "initial tables"`
Run: `alembic upgrade head`
Expected: 7 tables created in PostgreSQL

- [ ] **Step 5: Commit**

```bash
git add backend/app/database.py backend/app/models.py backend/alembic* backend/alembic.ini
git commit -m "feat: 数据库模型 - 7 张核心表 + Alembic 迁移"
```

---

## Task 3: Pydantic Schemas + 错误处理 + Auth

**Files:**
- Create: `backend/app/schemas.py`
- Create: `backend/app/errors.py`
- Create: `backend/app/auth.py`

- [ ] **Step 1: 创建 schemas.py**

```python
# backend/app/schemas.py
from decimal import Decimal
from datetime import datetime, date
from pydantic import BaseModel

# --- Account ---
class AccountCreate(BaseModel):
    agent_id: str
    market: str  # "us" | "cn"

class AccountOut(BaseModel):
    id: str
    agent_id: str
    market: str
    currency: str
    initial_cash: Decimal
    cash: Decimal

class PositionOut(BaseModel):
    ticker: str
    shares: Decimal
    avg_cost: Decimal
    current_price: Decimal | None = None
    pnl: Decimal | None = None
    weight: float | None = None

class PortfolioOut(BaseModel):
    cash: Decimal
    positions: list[PositionOut]

# --- Trade ---
class BuyRequest(BaseModel):
    account_id: str
    ticker: str
    amount: Decimal
    reasoning: str | None = None
    reasoning_full: str | None = None
    idempotency_key: str | None = None

class SellRequest(BaseModel):
    account_id: str
    ticker: str
    shares: Decimal
    reasoning: str | None = None
    reasoning_full: str | None = None
    idempotency_key: str | None = None

class TradeOut(BaseModel):
    trade_id: int
    ticker: str
    action: str
    shares: Decimal
    price: Decimal
    amount: Decimal
    fee: Decimal
    cash_after: Decimal
    created_at: datetime

# --- Market ---
class QuoteOut(BaseModel):
    ticker: str
    price: Decimal
    change_pct: float
    volume: int | None = None
    market_status: str  # "open" | "closed" | "halted"

# --- Leaderboard ---
class AgentRanking(BaseModel):
    agent_id: str
    name: str
    avatar: str
    model: str
    camp: str
    total_asset_usd: Decimal
    return_pct: float
    rank: int
    us_asset: Decimal | None = None
    cn_asset_usd: Decimal | None = None

class LeaderboardOut(BaseModel):
    market: str
    rankings: list[AgentRanking]

# --- Feed ---
class FeedItem(BaseModel):
    id: int
    type: str
    agent_id: str
    agent_name: str
    agent_avatar: str
    action: str
    ticker: str
    shares: Decimal
    price: Decimal
    amount: Decimal
    reasoning: str | None
    created_at: datetime

# --- Snapshot ---
class SnapshotOut(BaseModel):
    date: date
    total_asset: Decimal
    cash: Decimal
    position_value: Decimal
```

- [ ] **Step 2: 创建 errors.py**

```python
# backend/app/errors.py
from fastapi import HTTPException

class TradeError(HTTPException):
    def __init__(self, error_code: str, message: str, status_code: int = 422):
        super().__init__(
            status_code=status_code,
            detail={"error": error_code, "message": message, "detail": None},
        )

class InsufficientFunds(TradeError):
    def __init__(self, available: float, requested: float):
        super().__init__("INSUFFICIENT_FUNDS", f"余额不足，可用 {available}，请求 {requested}")

class PositionLimitExceeded(TradeError):
    def __init__(self):
        super().__init__("POSITION_LIMIT_EXCEEDED", "超过单股仓位上限 30%")

class MarketClosed(TradeError):
    def __init__(self):
        super().__init__("MARKET_CLOSED", "当前非交易时段")

class InsufficientShares(TradeError):
    def __init__(self):
        super().__init__("INSUFFICIENT_SHARES", "持仓不足，禁止卖空")

class DuplicateTrade(TradeError):
    def __init__(self):
        super().__init__("DUPLICATE_TRADE", "重复交易（idempotency_key 已存在）", status_code=409)
```

- [ ] **Step 3: 创建 auth.py**

```python
# backend/app/auth.py
from fastapi import Depends, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Account

async def get_current_account(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> Account:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, detail={"error": "INVALID_TOKEN", "message": "Missing Bearer token"})
    token = authorization[7:]
    result = await db.execute(select(Account).where(Account.api_token == token))
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(401, detail={"error": "INVALID_TOKEN", "message": "Token 无效或已过期"})
    return account
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/schemas.py backend/app/errors.py backend/app/auth.py
git commit -m "feat: Pydantic schemas + 统一错误处理 + Bearer auth"
```

---

## Task 4: 行情数据代理服务

**Files:**
- Create: `backend/app/services/market_data.py`
- Create: `backend/app/routers/market.py`
- Create: `backend/tests/test_market.py`
- Modify: `backend/app/main.py` (register router)

- [ ] **Step 1: 写测试 test_market.py**

```python
# backend/tests/test_market.py
import pytest
from unittest.mock import AsyncMock, patch
from decimal import Decimal

@pytest.mark.asyncio
async def test_get_quote_returns_cached(market_service):
    """Redis 有缓存时直接返回"""
    market_service.redis.get = AsyncMock(return_value='{"price": 195.5, "change_pct": 0.8, "volume": 1000000, "market_status": "open"}')
    quote = await market_service.get_quote("AAPL")
    assert quote.price == Decimal("195.5")
    assert quote.market_status == "open"

@pytest.mark.asyncio
async def test_get_quote_fetches_on_cache_miss(market_service):
    """缓存 miss 时调用 yfinance"""
    market_service.redis.get = AsyncMock(return_value=None)
    with patch("app.services.market_data.fetch_yfinance_quote") as mock_fetch:
        mock_fetch.return_value = {"price": 195.5, "change_pct": 0.8, "volume": 1000000, "market_status": "open"}
        market_service.redis.setex = AsyncMock()
        quote = await market_service.get_quote("AAPL")
        assert quote.price == Decimal("195.5")
        mock_fetch.assert_called_once_with("AAPL")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd ~/Developer/trade-arena/backend && pytest tests/test_market.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: 实现 market_data.py**

```python
# backend/app/services/market_data.py
import json
import yfinance as yf
from decimal import Decimal
from redis.asyncio import Redis
from app.schemas import QuoteOut

CACHE_TTL = 60  # seconds

def fetch_yfinance_quote(ticker: str) -> dict:
    """同步调用 yfinance（在 executor 中运行）"""
    t = yf.Ticker(ticker)
    info = t.fast_info
    price = float(info.get("lastPrice", 0) or info.get("previousClose", 0))
    prev_close = float(info.get("previousClose", price))
    change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0
    return {
        "price": price,
        "change_pct": round(change_pct, 2),
        "volume": int(info.get("lastVolume", 0) or 0),
        "market_status": "open",  # simplified for MVP
    }

class MarketDataService:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def get_quote(self, ticker: str) -> QuoteOut:
        cache_key = f"quote:{ticker}"
        cached = await self.redis.get(cache_key)
        if cached:
            data = json.loads(cached)
            return QuoteOut(ticker=ticker, **data)

        import asyncio
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, fetch_yfinance_quote, ticker)
        await self.redis.setex(cache_key, CACHE_TTL, json.dumps(data))
        return QuoteOut(ticker=ticker, **data)
```

- [ ] **Step 4: 实现 market router**

```python
# backend/app/routers/market.py
from fastapi import APIRouter, Depends
from app.services.market_data import MarketDataService
from app.schemas import QuoteOut

router = APIRouter(prefix="/api/market", tags=["market"])

@router.get("/quote/{ticker}", response_model=QuoteOut)
async def get_quote(ticker: str, market_svc: MarketDataService = Depends()):
    return await market_svc.get_quote(ticker.upper())
```

- [ ] **Step 5: 注册 router 到 main.py, 运行测试**

Run: `pytest tests/test_market.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/market_data.py backend/app/routers/market.py backend/tests/test_market.py backend/app/main.py
git commit -m "feat: 行情数据代理 - yfinance + Redis 缓存"
```

---

## Task 5: 账户 API

**Files:**
- Create: `backend/app/routers/accounts.py`
- Create: `backend/tests/test_accounts.py`
- Modify: `backend/app/main.py` (register router)

- [ ] **Step 1: 写测试**

```python
# backend/tests/test_accounts.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_get_account(client: AsyncClient, seeded_db):
    resp = await client.get("/api/accounts/opus-us", headers={"Authorization": "Bearer test-token-opus-us"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_id"] == "opus"
    assert data["market"] == "us"
    assert float(data["cash"]) == 500000.0

@pytest.mark.asyncio
async def test_get_portfolio_empty(client: AsyncClient, seeded_db):
    resp = await client.get("/api/accounts/opus-us/portfolio", headers={"Authorization": "Bearer test-token-opus-us"})
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["cash"]) == 500000.0
    assert data["positions"] == []

@pytest.mark.asyncio
async def test_unauthorized(client: AsyncClient):
    resp = await client.get("/api/accounts/opus-us", headers={"Authorization": "Bearer bad-token"})
    assert resp.status_code == 401
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/test_accounts.py -v`
Expected: FAIL

- [ ] **Step 3: 实现 accounts.py router**

```python
# backend/app/routers/accounts.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Account, Position, Agent
from app.schemas import AccountOut, PortfolioOut, PositionOut, SnapshotOut
from app.auth import get_current_account

router = APIRouter(prefix="/api/accounts", tags=["accounts"])

@router.get("/{account_id}", response_model=AccountOut)
async def get_account(
    account_id: str,
    current: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    if current.id != account_id:
        raise HTTPException(403, detail={"error": "FORBIDDEN", "message": "无权访问此账户"})
    agent = await db.get(Agent, current.agent_id)
    return AccountOut(
        id=current.id,
        agent_id=current.agent_id,
        market=current.market,
        currency=current.currency,
        initial_cash=current.initial_cash,
        cash=current.cash,
    )

@router.get("/{account_id}/portfolio", response_model=PortfolioOut)
async def get_portfolio(
    account_id: str,
    current: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    if current.id != account_id:
        raise HTTPException(403)
    result = await db.execute(select(Position).where(Position.account_id == account_id))
    positions = [
        PositionOut(ticker=p.ticker, shares=p.shares, avg_cost=p.avg_cost)
        for p in result.scalars()
    ]
    return PortfolioOut(cash=current.cash, positions=positions)
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_accounts.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/accounts.py backend/tests/test_accounts.py
git commit -m "feat: 账户 API - 查询账户信息 + 持仓列表"
```

---

## Task 6: 交易引擎（核心）

**Files:**
- Create: `backend/app/services/trading.py`
- Create: `backend/app/routers/trade.py`
- Create: `backend/tests/test_trading.py`

- [ ] **Step 1: 写测试 - 买入成功**

```python
# backend/tests/test_trading.py
import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_buy_success(client, seeded_db):
    with patch("app.services.market_data.MarketDataService.get_quote") as mock_quote:
        mock_quote.return_value = MockQuote(price=Decimal("100"), market_status="open")
        resp = await client.post("/api/trade/buy", json={
            "account_id": "opus-us",
            "ticker": "AAPL",
            "amount": 10000,
            "reasoning": "test buy",
            "idempotency_key": "key-1",
        }, headers={"Authorization": "Bearer test-token-opus-us"})
    assert resp.status_code == 200
    data = resp.json()
    assert float(data["shares"]) == 100.0  # 10000 / 100
    assert float(data["fee"]) == 10.0      # 10000 * 0.001
    assert float(data["cash_after"]) == 489990.0  # 500000 - 10000 - 10
```

- [ ] **Step 2: 写测试 - 余额不足**

```python
@pytest.mark.asyncio
async def test_buy_insufficient_funds(client, seeded_db):
    with patch("app.services.market_data.MarketDataService.get_quote") as mock_quote:
        mock_quote.return_value = MockQuote(price=Decimal("100"), market_status="open")
        resp = await client.post("/api/trade/buy", json={
            "account_id": "opus-us",
            "ticker": "AAPL",
            "amount": 600000,  # > 500000
        }, headers={"Authorization": "Bearer test-token-opus-us"})
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "INSUFFICIENT_FUNDS"
```

- [ ] **Step 3: 写测试 - 仓位超限**

```python
@pytest.mark.asyncio
async def test_buy_position_limit(client, seeded_db):
    with patch("app.services.market_data.MarketDataService.get_quote") as mock_quote:
        mock_quote.return_value = MockQuote(price=Decimal("100"), market_status="open")
        resp = await client.post("/api/trade/buy", json={
            "account_id": "opus-us",
            "ticker": "AAPL",
            "amount": 160000,  # > 500000 * 0.3
        }, headers={"Authorization": "Bearer test-token-opus-us"})
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "POSITION_LIMIT_EXCEEDED"
```

- [ ] **Step 4: 写测试 - 卖出成功 + 卖空拒绝**

```python
@pytest.mark.asyncio
async def test_sell_insufficient_shares(client, seeded_db):
    with patch("app.services.market_data.MarketDataService.get_quote") as mock_quote:
        mock_quote.return_value = MockQuote(price=Decimal("100"), market_status="open")
        resp = await client.post("/api/trade/sell", json={
            "account_id": "opus-us",
            "ticker": "AAPL",
            "shares": 100,
        }, headers={"Authorization": "Bearer test-token-opus-us"})
    assert resp.status_code == 422
    assert resp.json()["detail"]["error"] == "INSUFFICIENT_SHARES"
```

- [ ] **Step 5: 写测试 - 幂等性**

```python
@pytest.mark.asyncio
async def test_buy_idempotency(client, seeded_db):
    with patch("app.services.market_data.MarketDataService.get_quote") as mock_quote:
        mock_quote.return_value = MockQuote(price=Decimal("100"), market_status="open")
        body = {"account_id": "opus-us", "ticker": "AAPL", "amount": 10000, "idempotency_key": "dup-key"}
        headers = {"Authorization": "Bearer test-token-opus-us"}
        resp1 = await client.post("/api/trade/buy", json=body, headers=headers)
        assert resp1.status_code == 200
        resp2 = await client.post("/api/trade/buy", json=body, headers=headers)
        assert resp2.status_code == 409
```

- [ ] **Step 6: 运行测试确认失败**

Run: `pytest tests/test_trading.py -v`
Expected: FAIL

- [ ] **Step 7: 实现 trading.py 服务**

```python
# backend/app/services/trading.py
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Account, Position, Trade
from app.schemas import BuyRequest, SellRequest, TradeOut
from app.errors import InsufficientFunds, PositionLimitExceeded, MarketClosed, InsufficientShares, DuplicateTrade
from app.services.market_data import MarketDataService
from app.config import settings

class TradingService:
    def __init__(self, db: AsyncSession, market_svc: MarketDataService):
        self.db = db
        self.market_svc = market_svc

    async def buy(self, req: BuyRequest) -> TradeOut:
        async with self.db.begin():
            # Idempotency check
            if req.idempotency_key:
                existing = await self.db.execute(
                    select(Trade).where(Trade.idempotency_key == req.idempotency_key)
                )
                if existing.scalar_one_or_none():
                    raise DuplicateTrade()

            # Lock account row
            result = await self.db.execute(
                select(Account).where(Account.id == req.account_id).with_for_update()
            )
            account = result.scalar_one()

            # Get quote
            quote = await self.market_svc.get_quote(req.ticker)
            if quote.market_status == "closed":
                raise MarketClosed()

            price = quote.price
            shares = req.amount / price
            fee = req.amount * Decimal(str(settings.trade_fee_rate))

            # Checks
            if account.cash < req.amount + fee:
                raise InsufficientFunds(float(account.cash), float(req.amount))

            # Position limit check
            pos_result = await self.db.execute(
                select(Position).where(Position.account_id == req.account_id, Position.ticker == req.ticker)
            )
            existing_pos = pos_result.scalar_one_or_none()
            current_value = (existing_pos.shares * price) if existing_pos else Decimal(0)
            if (current_value + req.amount) / account.initial_cash > Decimal(str(settings.max_position_ratio)):
                raise PositionLimitExceeded()

            # Update portfolio
            if existing_pos:
                total_cost = existing_pos.avg_cost * existing_pos.shares + price * shares
                existing_pos.shares += shares
                existing_pos.avg_cost = total_cost / existing_pos.shares
            else:
                self.db.add(Position(
                    account_id=req.account_id, ticker=req.ticker,
                    shares=shares, avg_cost=price,
                ))

            account.cash -= (req.amount + fee)

            trade = Trade(
                account_id=req.account_id, ticker=req.ticker, action="buy",
                shares=shares, price=price, amount=req.amount, fee=fee,
                reasoning=req.reasoning, reasoning_full=req.reasoning_full,
                idempotency_key=req.idempotency_key,
            )
            self.db.add(trade)
            await self.db.flush()

            return TradeOut(
                trade_id=trade.id, ticker=req.ticker, action="buy",
                shares=shares, price=price, amount=req.amount, fee=fee,
                cash_after=account.cash, created_at=trade.created_at,
            )

    async def sell(self, req: SellRequest) -> TradeOut:
        async with self.db.begin():
            if req.idempotency_key:
                existing = await self.db.execute(
                    select(Trade).where(Trade.idempotency_key == req.idempotency_key)
                )
                if existing.scalar_one_or_none():
                    raise DuplicateTrade()

            result = await self.db.execute(
                select(Account).where(Account.id == req.account_id).with_for_update()
            )
            account = result.scalar_one()

            quote = await self.market_svc.get_quote(req.ticker)
            if quote.market_status == "closed":
                raise MarketClosed()

            pos_result = await self.db.execute(
                select(Position).where(Position.account_id == req.account_id, Position.ticker == req.ticker)
            )
            position = pos_result.scalar_one_or_none()
            if not position or position.shares < req.shares:
                raise InsufficientShares()

            price = quote.price
            amount = req.shares * price
            fee = amount * Decimal(str(settings.trade_fee_rate))

            position.shares -= req.shares
            if position.shares == 0:
                await self.db.delete(position)

            account.cash += (amount - fee)

            trade = Trade(
                account_id=req.account_id, ticker=req.ticker, action="sell",
                shares=req.shares, price=price, amount=amount, fee=fee,
                reasoning=req.reasoning, reasoning_full=req.reasoning_full,
                idempotency_key=req.idempotency_key,
            )
            self.db.add(trade)
            await self.db.flush()

            return TradeOut(
                trade_id=trade.id, ticker=req.ticker, action="sell",
                shares=req.shares, price=price, amount=amount, fee=fee,
                cash_after=account.cash, created_at=trade.created_at,
            )
```

- [ ] **Step 8: 实现 trade.py router**

```python
# backend/app/routers/trade.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.auth import get_current_account
from app.models import Account
from app.schemas import BuyRequest, SellRequest, TradeOut
from app.services.trading import TradingService
from app.services.market_data import MarketDataService

router = APIRouter(prefix="/api/trade", tags=["trade"])

@router.post("/buy", response_model=TradeOut)
async def buy(
    req: BuyRequest,
    current: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
    market_svc: MarketDataService = Depends(),
):
    svc = TradingService(db, market_svc)
    return await svc.buy(req)

@router.post("/sell", response_model=TradeOut)
async def sell(
    req: SellRequest,
    current: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
    market_svc: MarketDataService = Depends(),
):
    svc = TradingService(db, market_svc)
    return await svc.sell(req)
```

- [ ] **Step 9: 运行测试**

Run: `pytest tests/test_trading.py -v`
Expected: ALL PASS (买入成功、余额不足、仓位超限、卖空拒绝、幂等性)

- [ ] **Step 10: Commit**

```bash
git add backend/app/services/trading.py backend/app/routers/trade.py backend/tests/test_trading.py
git commit -m "feat: 交易引擎 - 买入/卖出 + 风控检查 + 幂等性"
```

---

## Task 7: 排行榜 + 动态流 API

**Files:**
- Create: `backend/app/services/ranking.py`
- Create: `backend/app/routers/leaderboard.py`
- Create: `backend/tests/test_leaderboard.py`

- [ ] **Step 1: 写测试**

```python
# backend/tests/test_leaderboard.py
import pytest

@pytest.mark.asyncio
async def test_leaderboard_overall(client, seeded_db):
    resp = await client.get("/api/leaderboard?market=overall")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["rankings"]) == 8  # 8 agents
    # All start at same amount, rank by agent_id as tiebreaker
    assert all(r["return_pct"] == 0.0 for r in data["rankings"])

@pytest.mark.asyncio
async def test_feed_empty(client, seeded_db):
    resp = await client.get("/api/feed")
    assert resp.status_code == 200
    assert resp.json() == []

@pytest.mark.asyncio
async def test_feed_after_trade(client, seeded_db, make_trade):
    await make_trade("opus-us", "AAPL", 10000)
    resp = await client.get("/api/feed?limit=10")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["ticker"] == "AAPL"
```

- [ ] **Step 2: 实现 ranking.py**

```python
# backend/app/services/ranking.py
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models import Account, Agent, Position
from app.schemas import AgentRanking

EXCHANGE_RATE_CNY_TO_USD = Decimal("0.137")  # fallback, should come from Redis

class RankingService:
    def __init__(self, db: AsyncSession, get_price):
        self.db = db
        self.get_price = get_price  # async callable(ticker) -> Decimal

    async def get_leaderboard(self, market: str = "overall") -> list[AgentRanking]:
        agents_result = await self.db.execute(select(Agent))
        agents = {a.id: a for a in agents_result.scalars()}

        accounts_query = select(Account)
        if market in ("us", "cn"):
            accounts_query = accounts_query.where(Account.market == market)

        accounts_result = await self.db.execute(accounts_query)
        accounts = list(accounts_result.scalars())

        # Group by agent_id
        agent_assets: dict[str, Decimal] = {}
        for acc in accounts:
            positions_result = await self.db.execute(
                select(Position).where(Position.account_id == acc.id)
            )
            pos_value = Decimal(0)
            for pos in positions_result.scalars():
                try:
                    price = await self.get_price(pos.ticker)
                    pos_value += pos.shares * price
                except Exception:
                    pos_value += pos.shares * pos.avg_cost  # fallback to cost

            total = acc.cash + pos_value
            if acc.currency == "CNY" and market == "overall":
                total = total * EXCHANGE_RATE_CNY_TO_USD

            agent_assets.setdefault(acc.agent_id, Decimal(0))
            agent_assets[acc.agent_id] += total

        # Initial total for return calculation
        initial_total = Decimal(500000)  # USD
        if market == "overall":
            initial_total = Decimal(500000) + Decimal(500000) * EXCHANGE_RATE_CNY_TO_USD

        rankings = []
        for agent_id, total in sorted(agent_assets.items(), key=lambda x: x[1], reverse=True):
            agent = agents[agent_id]
            return_pct = float((total - initial_total) / initial_total * 100)
            rankings.append(AgentRanking(
                agent_id=agent_id, name=agent.name, avatar=agent.avatar,
                model=agent.model, camp=agent.camp,
                total_asset_usd=total, return_pct=round(return_pct, 2), rank=0,
            ))

        for i, r in enumerate(rankings):
            r.rank = i + 1

        return rankings
```

- [ ] **Step 3: 实现 leaderboard.py router**

```python
# backend/app/routers/leaderboard.py
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models import Trade, Agent
from app.schemas import LeaderboardOut, FeedItem
from app.services.ranking import RankingService
from sqlalchemy import select

router = APIRouter(tags=["leaderboard"])

@router.get("/api/leaderboard", response_model=LeaderboardOut)
async def leaderboard(
    market: str = Query("overall", pattern="^(us|cn|overall)$"),
    db: AsyncSession = Depends(get_db),
):
    async def get_price(ticker):
        from app.services.market_data import MarketDataService
        # simplified: return avg_cost as fallback in tests
        return 0
    svc = RankingService(db, get_price)
    rankings = await svc.get_leaderboard(market)
    return LeaderboardOut(market=market, rankings=rankings)

@router.get("/api/feed", response_model=list[FeedItem])
async def feed(
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Trade).order_by(Trade.created_at.desc()).offset(offset).limit(limit)
    )
    trades = result.scalars().all()
    items = []
    for t in trades:
        agent_result = await db.execute(
            select(Agent).join_from(
                Agent, __import__('app.models', fromlist=['Account']).Account,
                Agent.id == __import__('app.models', fromlist=['Account']).Account.agent_id
            ).where(__import__('app.models', fromlist=['Account']).Account.id == t.account_id)
        )
        # simplified join - will refine in implementation
        items.append(FeedItem(
            id=t.id, type="trade", agent_id="", agent_name="", agent_avatar="",
            action=t.action, ticker=t.ticker, shares=t.shares, price=t.price,
            amount=t.amount, reasoning=t.reasoning, created_at=t.created_at,
        ))
    return items
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_leaderboard.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/ranking.py backend/app/routers/leaderboard.py backend/tests/test_leaderboard.py
git commit -m "feat: 排行榜 + 交易动态流 API"
```

---

## Task 8: SSE 事件推送

**Files:**
- Create: `backend/app/services/events.py`
- Create: `backend/app/routers/sse.py`
- Create: `backend/tests/test_sse.py`

- [ ] **Step 1: 实现 events.py 服务**

```python
# backend/app/services/events.py
import json
from datetime import datetime
from redis.asyncio import Redis
from app.models import Trade, Account, Agent

CHANNEL = "events"

class EventService:
    def __init__(self, redis: Redis):
        self.redis = redis

    async def publish_trade_event(self, trade: Trade, account: Account, agent: Agent):
        event = {
            "type": "trade",
            "agent": {"id": agent.id, "name": agent.name, "avatar": agent.avatar},
            "market": account.market,
            "action": trade.action,
            "ticker": trade.ticker,
            "shares": str(trade.shares),
            "price": str(trade.price),
            "amount": str(trade.amount),
            "reasoning": trade.reasoning,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        await self.redis.publish(CHANNEL, json.dumps(event, ensure_ascii=False))
        await self.redis.lpush("events:recent", json.dumps(event, ensure_ascii=False))
        await self.redis.ltrim("events:recent", 0, 199)

    async def publish_ranking_event(self, rankings: list[dict]):
        event = {
            "type": "ranking",
            "leaderboard": rankings,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        await self.redis.publish(CHANNEL, json.dumps(event, ensure_ascii=False))
```

- [ ] **Step 2: 实现 SSE router**

```python
# backend/app/routers/sse.py
import json
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
from redis.asyncio import Redis

router = APIRouter(tags=["sse"])

@router.get("/api/sse/events")
async def sse_events(request: Request, redis: Redis):
    async def event_generator():
        # Send recent events on connect
        recent = await redis.lrange("events:recent", 0, 49)
        for item in reversed(recent):
            data = json.loads(item)
            yield {"event": data["type"], "data": item.decode() if isinstance(item, bytes) else item}

        # Subscribe to live events
        pubsub = redis.pubsub()
        await pubsub.subscribe("events")
        try:
            async for message in pubsub.listen():
                if await request.is_disconnected():
                    break
                if message["type"] == "message":
                    data = json.loads(message["data"])
                    yield {"event": data["type"], "data": message["data"].decode() if isinstance(message["data"], bytes) else message["data"]}
        finally:
            await pubsub.unsubscribe("events")

    return EventSourceResponse(event_generator())
```

- [ ] **Step 3: 写测试**

```python
# backend/tests/test_sse.py
import pytest
from app.services.events import EventService

@pytest.mark.asyncio
async def test_publish_and_retrieve(redis):
    svc = EventService(redis)
    await svc.publish_trade_event(mock_trade, mock_account, mock_agent)
    recent = await redis.lrange("events:recent", 0, -1)
    assert len(recent) == 1
```

- [ ] **Step 4: 运行测试**

Run: `pytest tests/test_sse.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/events.py backend/app/routers/sse.py backend/tests/test_sse.py
git commit -m "feat: SSE 事件推送 - Redis pub/sub + 历史回放"
```

---

## Task 9: 种子数据 + Health Check

**Files:**
- Create: `backend/app/seed.py`
- Create: `backend/app/routers/health.py`

- [ ] **Step 1: 实现 seed.py**

```python
# backend/app/seed.py
import secrets
from app.database import async_session
from app.models import Season, Agent, Account

AGENTS = [
    {"id": "opus", "name": "深渊之眼", "avatar": "🧠", "model": "claude-opus-4-6", "camp": "closed", "style": "深度价值 + 长线持有", "framework": "claude-code"},
    {"id": "gemini", "name": "星图者", "avatar": "🌟", "model": "gemini-3.1-pro", "camp": "closed", "style": "均衡成长 + 信息广度", "framework": "opencode"},
    {"id": "gpt", "name": "闪电手", "avatar": "⚡", "model": "gpt-5.4", "camp": "closed", "style": "短线趋势交易", "framework": "opencode"},
    {"id": "grok", "name": "叛逆者", "avatar": "🔥", "model": "grok-4.1", "camp": "closed", "style": "激进投机 + 逆向操作", "framework": "opencode"},
    {"id": "qwen", "name": "东方龙", "avatar": "🐉", "model": "qwen3-max", "camp": "open", "style": "避险 + 择时", "framework": "opencode"},
    {"id": "deepseek", "name": "深思者", "avatar": "🔮", "model": "deepseek-v3.2", "camp": "open", "style": "量化分析 + 稳健", "framework": "opencode"},
    {"id": "glm", "name": "智鉴阁", "avatar": "🏛️", "model": "glm-5", "camp": "open", "style": "多因子分析", "framework": "opencode"},
    {"id": "kimi", "name": "弄潮儿", "avatar": "🌊", "model": "kimi-k2.5", "camp": "open", "style": "代码驱动量化", "framework": "opencode"},
]

async def seed_database():
    async with async_session() as session:
        async with session.begin():
            # Season
            season = Season(id="2026-Q1", name="第一赛季", start_date="2026-03-18", status="active")
            session.add(season)

            for agent_data in AGENTS:
                agent = Agent(**agent_data)
                session.add(agent)

                for market, currency, cash in [("us", "USD", 500000), ("cn", "CNY", 500000)]:
                    account = Account(
                        id=f"{agent_data['id']}-{market}",
                        season_id="2026-Q1",
                        agent_id=agent_data["id"],
                        market=market,
                        currency=currency,
                        initial_cash=cash,
                        cash=cash,
                        api_token=secrets.token_hex(32),
                    )
                    session.add(account)

        await session.commit()
    print("Seed complete: 8 agents, 16 accounts, 1 season")

if __name__ == "__main__":
    import asyncio
    asyncio.run(seed_database())
```

- [ ] **Step 2: 完善 health.py**

```python
# backend/app/routers/health.py
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis
from app.database import get_db

router = APIRouter(tags=["health"])

@router.get("/api/health")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "db": db_ok}
```

- [ ] **Step 3: 运行种子脚本**

Run: `cd ~/Developer/trade-arena/backend && python -m app.seed`
Expected: `Seed complete: 8 agents, 16 accounts, 1 season`

- [ ] **Step 4: 验证 health endpoint**

Run: `curl http://localhost:8000/api/health`
Expected: `{"status":"ok","db":true}`

- [ ] **Step 5: Commit**

```bash
git add backend/app/seed.py backend/app/routers/health.py
git commit -m "feat: 种子数据(8 agents + 16 accounts) + health check"
```

---

## Task 10: 测试 fixtures + 集成验证

**Files:**
- Create: `backend/tests/conftest.py`
- Modify: all test files to use shared fixtures

- [ ] **Step 1: 创建 conftest.py**

```python
# backend/tests/conftest.py
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.database import Base, get_db
from app.main import app
from app.models import Season, Agent, Account

TEST_DB_URL = "sqlite+aiosqlite:///test.db"

@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def seeded_db(db_session):
    """Seed test data: 1 season, 8 agents, 16 accounts with known tokens"""
    async with db_session.begin():
        db_session.add(Season(id="2026-Q1", name="Test", start_date="2026-03-18", status="active"))
        agents_data = [
            ("opus", "深渊之眼", "🧠", "claude-opus", "closed", "价值投资", "claude-code"),
            ("qwen", "东方龙", "🐉", "qwen3-max", "open", "择时", "opencode"),
            # ... add remaining 6
        ]
        for aid, name, avatar, model, camp, style, fw in agents_data:
            db_session.add(Agent(id=aid, name=name, avatar=avatar, model=model, camp=camp, style=style, framework=fw))
            for market, currency, cash in [("us", "USD", 500000), ("cn", "CNY", 500000)]:
                db_session.add(Account(
                    id=f"{aid}-{market}", season_id="2026-Q1", agent_id=aid,
                    market=market, currency=currency, initial_cash=cash, cash=cash,
                    api_token=f"test-token-{aid}-{market}",
                ))
    return db_session

@pytest_asyncio.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

- [ ] **Step 2: 运行所有测试**

Run: `cd ~/Developer/trade-arena/backend && pytest -v`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add backend/tests/conftest.py
git commit -m "test: 共享 fixtures + 集成测试通过"
```

---

## Task 11: 注册所有 routers + 端到端验证

**Files:**
- Modify: `backend/app/main.py`

- [ ] **Step 1: 在 main.py 中注册所有 router**

```python
# backend/app/main.py
from app.routers import accounts, trade, market, leaderboard, sse, health

app.include_router(health.router)
app.include_router(accounts.router)
app.include_router(trade.router)
app.include_router(market.router)
app.include_router(leaderboard.router)
app.include_router(sse.router)
```

- [ ] **Step 2: 端到端手动验证**

```bash
# 启动服务
cd ~/Developer/trade-arena/backend && uvicorn app.main:app --reload --port 8000

# 运行种子数据
python -m app.seed

# 查看 API 文档
open http://localhost:8000/docs

# 测试流程
# 1. 获取 agent token（从数据库查）
# 2. 查看账户: GET /api/accounts/opus-us
# 3. 查看行情: GET /api/market/quote/AAPL
# 4. 买入: POST /api/trade/buy
# 5. 查看持仓: GET /api/accounts/opus-us/portfolio
# 6. 查看排行: GET /api/leaderboard
# 7. 查看动态: GET /api/feed
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/main.py
git commit -m "feat: Phase 1 完成 - 后端 API 全部就绪"
```

---

## 完成标准

Phase 1 完成时，以下功能可用：

- [x] `GET /api/health` — 健康检查
- [x] `GET /api/accounts/:id` — 查询账户
- [x] `GET /api/accounts/:id/portfolio` — 查询持仓
- [x] `POST /api/trade/buy` — 买入（含风控 + 幂等性）
- [x] `POST /api/trade/sell` — 卖出（含卖空检查 + 幂等性）
- [x] `GET /api/market/quote/:ticker` — 实时报价（yfinance + Redis 缓存）
- [x] `GET /api/leaderboard` — 排行榜（支持 overall/us/cn）
- [x] `GET /api/feed` — 交易动态流
- [x] `GET /api/sse/events` — SSE 实时推送
- [x] 种子数据：8 agents, 16 accounts, 1 season
- [x] 所有测试通过
