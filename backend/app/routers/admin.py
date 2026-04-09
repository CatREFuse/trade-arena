from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from time import perf_counter

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models import Account, Agent, Position, Trade, Wallet
from app.services.fx import FXService
from app.services.market_data import MARKET_CACHE_VERSION, MarketDataService
from app.services.traffic_analytics import TrafficAnalyticsService
from app.utils.datetime import ensure_utc_datetime, normalize_iso_datetime

router = APIRouter(prefix="/api/admin", tags=["admin"])


def _as_float(value: Decimal | float | int | None) -> float:
    if value is None:
        return 0.0
    if isinstance(value, Decimal):
        return float(value)
    return float(value)


async def _probe_source(name: str, fetcher):
    started = perf_counter()
    try:
        result = await fetcher()
        latency_ms = int((perf_counter() - started) * 1000)
        return {
            "name": name,
            "ok": bool(result),
            "latency_ms": latency_ms,
            "detail": "" if result else "empty",
        }
    except Exception as exc:
        latency_ms = int((perf_counter() - started) * 1000)
        return {
            "name": name,
            "ok": False,
            "latency_ms": latency_ms,
            "detail": str(exc),
        }


async def _collect_users(
    db: AsyncSession,
    limit: int,
    offset: int,
    redis=None,
) -> dict:
    total = (
        await db.execute(
            select(func.count()).select_from(Agent).where(Agent.is_deleted.is_(False))
        )
    ).scalar() or 0
    agent_rows = await db.execute(
        select(Agent)
        .where(Agent.is_deleted.is_(False))
        .order_by(Agent.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    agents = agent_rows.scalars().all()
    if not agents:
        return {"total": int(total), "limit": int(limit), "offset": int(offset), "items": []}

    agent_ids = [agent.id for agent in agents]
    account_rows = await db.execute(
        select(Account).where(Account.agent_id.in_(agent_ids))
    )
    accounts = account_rows.scalars().all()
    account_by_id = {account.id: account for account in accounts}
    account_by_agent: dict[str, list[Account]] = {}
    for account in accounts:
        account_by_agent.setdefault(account.agent_id, []).append(account)

    wallet_rows = await db.execute(select(Wallet).where(Wallet.agent_id.in_(agent_ids)))
    wallet_by_agent = {wallet.agent_id: wallet for wallet in wallet_rows.scalars().all()}

    account_ids = [account.id for account in accounts]
    trade_by_account: dict[str, int] = {}
    if account_ids:
        trade_rows = await db.execute(
            select(Trade.account_id, func.count(Trade.id))
            .where(Trade.account_id.in_(account_ids))
            .group_by(Trade.account_id)
        )
        for account_id, count in trade_rows:
            trade_by_account[account_id] = int(count or 0)

    position_rows = await db.execute(select(Position).where(Position.account_id.in_(account_ids)))
    positions = position_rows.scalars().all()
    positions_by_account: dict[str, list[Position]] = {}
    for position in positions:
        positions_by_account.setdefault(position.account_id, []).append(position)

    quote_map: dict[str, object | None] = {}
    if positions and redis is not None:
        market_service = MarketDataService(redis)
        quote_map = await market_service.get_quotes_batch(list({position.ticker for position in positions}))

    usd_to_cny = Decimal(str(settings.exchange_rate))
    hkd_to_cny = Decimal(str(getattr(settings, "exchange_rate_hkd_to_cny", 0.92)))
    if redis is not None:
        fx_service = FXService(redis)
        usd_rate, _, _ = await fx_service.get_rate_to_cny("us")
        hkd_rate, _, _ = await fx_service.get_rate_to_cny("hk")
        usd_to_cny = Decimal(str(usd_rate))
        hkd_to_cny = Decimal(str(hkd_rate))

    market_rate = {
        "cn": Decimal("1"),
        "us": usd_to_cny,
        "hk": hkd_to_cny,
    }

    items: list[dict] = []
    for agent in agents:
        owned_accounts = account_by_agent.get(agent.id, [])
        total_position_cny = Decimal("0")
        for owned_account in owned_accounts:
            position_list = positions_by_account.get(owned_account.id, [])
            fx = market_rate.get(owned_account.market, Decimal("1"))
            for position in position_list:
                quote = quote_map.get(position.ticker)
                local_value = position.shares * (quote.price if quote is not None else position.avg_cost)
                total_position_cny += local_value * fx

        wallet = wallet_by_agent.get(agent.id)
        if wallet is not None:
            wallet_cash = wallet.cash
        else:
            wallet_cash = sum(
                owned_account.cash * market_rate.get(owned_account.market, Decimal("1"))
                for owned_account in owned_accounts
            )
        total_asset_cny = wallet_cash + total_position_cny
        trade_count = sum(trade_by_account.get(account.id, 0) for account in owned_accounts)
        items.append(
            {
                "id": agent.id,
                "name": agent.name,
                "email": agent.email or "",
                "avatar": agent.avatar,
                "model": agent.model,
                "style": agent.style,
                "created_at": ensure_utc_datetime(agent.created_at),
                "account_count": len(owned_accounts),
                "trade_count": trade_count,
                "asset_cny": round(float(total_asset_cny), 2),
            }
        )

    return {"total": int(total), "limit": int(limit), "offset": int(offset), "items": items}


async def _collect_logs(db: AsyncSession, limit: int, offset: int) -> dict:
    total = (await db.execute(select(func.count()).select_from(Trade))).scalar() or 0
    buy_total = (
        await db.execute(select(func.count()).select_from(Trade).where(Trade.action == "buy"))
    ).scalar() or 0
    sell_total = (
        await db.execute(select(func.count()).select_from(Trade).where(Trade.action == "sell"))
    ).scalar() or 0

    trade_rows = await db.execute(
        select(Trade).order_by(Trade.created_at.desc()).limit(limit).offset(offset)
    )
    trades = trade_rows.scalars().all()
    if not trades:
        return {
            "total": int(total),
            "buy_total": int(buy_total),
            "sell_total": int(sell_total),
            "limit": int(limit),
            "offset": int(offset),
            "items": [],
        }

    account_ids = list({trade.account_id for trade in trades})
    account_rows = await db.execute(select(Account).where(Account.id.in_(account_ids)))
    accounts = {account.id: account for account in account_rows.scalars().all()}
    agent_ids = list({account.agent_id for account in accounts.values()})
    agent_rows = await db.execute(
        select(Agent).where(Agent.id.in_(agent_ids), Agent.is_deleted.is_(False))
    )
    agents = {agent.id: agent for agent in agent_rows.scalars().all()}

    items: list[dict] = []
    for trade in trades:
        account = accounts.get(trade.account_id)
        agent = agents.get(account.agent_id) if account else None
        items.append(
            {
                "id": trade.id,
                "created_at": ensure_utc_datetime(trade.created_at),
                "action": trade.action,
                "ticker": trade.ticker,
                "shares": _as_float(trade.shares),
                "price": _as_float(trade.price),
                "amount": _as_float(trade.amount),
                "fee": _as_float(trade.fee),
                "reasoning": trade.reasoning or "",
                "account_id": trade.account_id,
                "market": account.market if account else "",
                "agent_id": agent.id if agent else "",
                "agent_name": agent.name if agent else "",
                "agent_avatar": agent.avatar if agent else "",
            }
        )
    return {
        "total": int(total),
        "buy_total": int(buy_total),
        "sell_total": int(sell_total),
        "limit": int(limit),
        "offset": int(offset),
        "items": items,
    }


async def _collect_traffic(redis, days: int = 7, top: int = 15) -> dict:
    service = TrafficAnalyticsService(redis)
    return await service.get_report(days=days, top=top)


async def _collect_data_sources(request: Request, db: AsyncSession) -> dict:
    db_ok = True
    redis_ok = True
    redis_error = ""
    db_error = ""

    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        db_ok = False
        db_error = str(exc)

    redis = request.app.state.redis
    try:
        if hasattr(redis, "ping"):
            await redis.ping()
    except Exception as exc:
        redis_ok = False
        redis_error = str(exc)

    service = MarketDataService(redis)
    probes = []
    provider_circuits = service.provider_health_snapshot()
    provider_chains = service.provider_chain_snapshot()
    cache_status = await _collect_cache_status(redis)

    return {
        "db": {"ok": db_ok, "detail": db_error},
        "redis": {"ok": redis_ok, "detail": redis_error},
        "probes": probes,
        "provider_chains": provider_chains,
        "provider_circuits": provider_circuits,
        "cache": cache_status,
    }


async def _probe_sources(service: MarketDataService) -> list[dict]:
    checks = [
        _probe_source("US Quote (AAPL)", lambda: service.get_quote("AAPL")),
        _probe_source("CN Quote (600519.SH)", lambda: service.get_quote("600519.SH")),
        _probe_source("US Index (SPX)", lambda: service.get_index("SPX", market="us")),
        _probe_source("CN Index (SH)", lambda: service.get_index("SH", market="cn")),
    ]
    return await asyncio.gather(*checks)


async def _collect_cache_status(redis) -> dict:
    cache_keys = {
        "market_overview": f"market:overview:{MARKET_CACHE_VERSION}",
        "board_us": f"market:board:{MARKET_CACHE_VERSION}:us",
        "board_cn": f"market:board:{MARKET_CACHE_VERSION}:cn",
        "board_hk": f"market:board:{MARKET_CACHE_VERSION}:hk",
    }
    result: dict[str, dict] = {}
    for label, key in cache_keys.items():
        raw = await redis.get(key)
        if not raw:
            result[label] = {"present": False, "updated_at": ""}
            continue
        decoded = raw.decode() if isinstance(raw, bytes) else raw
        updated_at = ""
        try:
            payload = json.loads(decoded)
            if isinstance(payload, dict):
                updated_at = normalize_iso_datetime(payload.get("updated_at", "") or "")
        except Exception:
            updated_at = ""
        result[label] = {"present": True, "updated_at": updated_at}
    return result


async def _load_cache_json(redis, key: str) -> dict | None:
    raw = await redis.get(key)
    if not raw:
        return None
    decoded = raw.decode() if isinstance(raw, bytes) else raw
    try:
        payload = json.loads(decoded)
        if isinstance(payload, dict):
            return payload
    except Exception:
        return None
    return None


def _empty_market_snapshot() -> dict:
    return {
        "updated_at": "",
        "indices": [],
        "market_summary": [],
        "boards": {"us": [], "cn": [], "hk": []},
    }


async def _collect_market_snapshot(request: Request, live: bool = False) -> dict:
    redis = request.app.state.redis
    if not live:
        overview = await _load_cache_json(redis, f"market:overview:{MARKET_CACHE_VERSION}")
        if not overview:
            return _empty_market_snapshot()
        us_board = await _load_cache_json(redis, f"market:board:{MARKET_CACHE_VERSION}:us")
        cn_board = await _load_cache_json(redis, f"market:board:{MARKET_CACHE_VERSION}:cn")
        hk_board = await _load_cache_json(redis, f"market:board:{MARKET_CACHE_VERSION}:hk")
        return {
            "updated_at": normalize_iso_datetime(overview.get("updated_at", "")),
            "indices": overview.get("indices", []),
            "market_summary": overview.get("markets", []),
            "boards": {
                "us": (us_board or {}).get("items", [])[:10],
                "cn": (cn_board or {}).get("items", [])[:10],
                "hk": (hk_board or {}).get("items", [])[:10],
            },
        }

    service = MarketDataService(request.app.state.redis)
    overview = await service.get_market_overview(refresh=False)
    us_board = await service.get_market_board("us", refresh=False)
    cn_board = await service.get_market_board("cn", refresh=False)
    hk_board = await service.get_market_board("hk", refresh=False)
    return {
        "updated_at": ensure_utc_datetime(overview.updated_at),
        "indices": [item.model_dump(mode="json") for item in overview.indices],
        "market_summary": [item.model_dump(mode="json") for item in overview.markets],
        "boards": {
            "us": [item.model_dump(mode="json") for item in us_board.items[:10]],
            "cn": [item.model_dump(mode="json") for item in cn_board.items[:10]],
            "hk": [item.model_dump(mode="json") for item in hk_board.items[:10]],
        },
    }


async def _collect_trade_stats(db: AsyncSession, days: int) -> dict:
    # trades.created_at is stored as a naive timestamp in the current schema,
    # so comparisons here must use naive UTC datetimes as well.
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    window_start = now - timedelta(days=max(days - 1, 0))
    last_24h = now - timedelta(hours=24)

    total_trades = (await db.execute(select(func.count()).select_from(Trade))).scalar() or 0
    total_amount = (await db.execute(select(func.sum(Trade.amount)))).scalar() or Decimal("0")
    buy_count = (
        await db.execute(select(func.count()).select_from(Trade).where(Trade.action == "buy"))
    ).scalar() or 0
    sell_count = (
        await db.execute(select(func.count()).select_from(Trade).where(Trade.action == "sell"))
    ).scalar() or 0
    recent_24h = (
        await db.execute(select(func.count()).select_from(Trade).where(Trade.created_at >= last_24h))
    ).scalar() or 0

    market_rows = await db.execute(
        select(Account.market, func.count(Trade.id), func.sum(Trade.amount))
        .join(Trade, Trade.account_id == Account.id)
        .group_by(Account.market)
    )
    by_market = {}
    for market, count, amount in market_rows:
        by_market[market] = {"count": int(count or 0), "amount": round(_as_float(amount), 2)}

    daily_rows = await db.execute(
        select(Trade.created_at, Trade.amount, Trade.action).where(Trade.created_at >= window_start)
    )
    daily_bucket: dict[str, dict] = {}
    for created_at, amount, action in daily_rows:
        day_key = created_at.date().isoformat()
        bucket = daily_bucket.setdefault(
            day_key,
            {"date": day_key, "count": 0, "amount": 0.0, "buy_count": 0, "sell_count": 0},
        )
        bucket["count"] += 1
        bucket["amount"] += _as_float(amount)
        if action == "buy":
            bucket["buy_count"] += 1
        elif action == "sell":
            bucket["sell_count"] += 1

    top_ticker_rows = await db.execute(
        select(Trade.ticker, func.count(Trade.id), func.sum(Trade.amount))
        .group_by(Trade.ticker)
        .order_by(func.count(Trade.id).desc())
        .limit(10)
    )
    top_tickers = [
        {"ticker": ticker, "count": int(count or 0), "amount": round(_as_float(amount), 2)}
        for ticker, count, amount in top_ticker_rows
    ]

    return {
        "totals": {
            "trade_count": int(total_trades),
            "trade_amount": round(_as_float(total_amount), 2),
            "buy_count": int(buy_count),
            "sell_count": int(sell_count),
            "recent_24h_count": int(recent_24h),
        },
        "by_market": by_market,
        "daily": [daily_bucket[key] for key in sorted(daily_bucket.keys())],
        "top_tickers": top_tickers,
    }


@router.get("/users")
async def admin_users(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await _collect_users(db, limit=limit, offset=offset, redis=request.app.state.redis)


@router.get("/logs")
async def admin_logs(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    return await _collect_logs(db, limit=limit, offset=offset)


@router.get("/data-sources")
async def admin_data_sources(
    request: Request,
    probe: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    payload = await _collect_data_sources(request, db)
    if probe:
        service = MarketDataService(request.app.state.redis)
        payload["probes"] = await _probe_sources(service)
    return payload


@router.get("/market")
async def admin_market_snapshot(request: Request, live: bool = Query(default=False)):
    return await _collect_market_snapshot(request, live=live)


@router.get("/trade-stats")
async def admin_trade_stats(
    days: int = Query(default=7, ge=1, le=30),
    db: AsyncSession = Depends(get_db),
):
    return await _collect_trade_stats(db, days=days)


@router.get("/traffic")
async def admin_traffic(
    request: Request,
    days: int = Query(default=7, ge=1, le=30),
    top: int = Query(default=15, ge=1, le=100),
):
    return await _collect_traffic(request.app.state.redis, days=days, top=top)


@router.get("/dashboard")
async def admin_dashboard(
    request: Request,
    live_market: bool = Query(default=False),
    traffic_days: int = Query(default=7, ge=1, le=30),
    traffic_top: int = Query(default=15, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    users = await _collect_users(db, limit=20, offset=0, redis=request.app.state.redis)
    logs = await _collect_logs(db, limit=20, offset=0)
    data_sources = await _collect_data_sources(request, db)
    market = await _collect_market_snapshot(request, live=live_market)
    trade_stats = await _collect_trade_stats(db, days=7)
    traffic = await _collect_traffic(request.app.state.redis, days=traffic_days, top=traffic_top)
    return {
        "generated_at": datetime.now(timezone.utc),
        "users": users,
        "logs": logs,
        "data_sources": data_sources,
        "market": market,
        "trade_stats": trade_stats,
        "traffic": traffic,
    }
