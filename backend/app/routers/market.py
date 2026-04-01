from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, Request
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Account, Agent, Position, Trade
from app.schemas import (
    IndexQuoteOut,
    MarketBoardSnapshotOut,
    MarketOverviewOut,
    MarketTrendOut,
    QuoteOut,
    StockDetailOut,
    StockPositionStatsOut,
    StockRecentTradeOut,
    StockSiteStatsOut,
)
from app.services.fx import FXService
from app.services.market_data import MarketDataService

router = APIRouter(prefix="/api/market", tags=["market"])


def _market_service(request: Request) -> MarketDataService:
    redis = request.app.state.redis
    return getattr(request.app.state, "market_data_service", None) or MarketDataService(redis)


def _decimal_or_zero(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if value is None:
        return Decimal("0")
    return Decimal(str(value))


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"))


@router.get("/quote/{ticker}", response_model=QuoteOut)
async def get_quote(ticker: str, request: Request):
    svc = _market_service(request)
    return await svc.get_quote(ticker.upper())


@router.get("/quote", response_model=QuoteOut)
async def get_quote_compat(ticker: str, request: Request):
    """兼容旧客户端：/api/market/quote?ticker=..."""
    svc = _market_service(request)
    return await svc.get_quote(ticker.upper())


@router.get("/index/{symbol}", response_model=IndexQuoteOut)
async def get_index(symbol: str, market: str = "us", request: Request = None):
    """获取大盘指数行情

    - symbol: SPX/NDX/DJI (美股) 或 SH/SZ/CY (A股) 或 HSI/HSCEI (港股)
    - market: us | cn | hk
    """
    svc = _market_service(request)
    return await svc.get_index(symbol.upper(), market)


@router.get("/indices", response_model=list[IndexQuoteOut])
async def get_all_indices(request: Request, refresh: bool = False):
    """获取所有大盘指数"""
    svc = _market_service(request)
    return await svc.get_all_indices(refresh=refresh)


@router.get("/overview", response_model=MarketOverviewOut)
async def get_market_overview(request: Request, refresh: bool = False):
    """获取市场总览快照"""
    svc = _market_service(request)
    return await svc.get_market_overview(refresh=refresh)


@router.get("/board", response_model=MarketBoardSnapshotOut)
async def get_market_board(market: str = "us", request: Request = None, refresh: bool = False):
    """获取市场看盘榜单"""
    svc = _market_service(request)
    return await svc.get_market_board(market.lower(), refresh=refresh)


@router.get("/trend", response_model=MarketTrendOut)
async def get_market_trend(
    market: str = "us",
    points: int = 30,
    request: Request = None,
    refresh: bool = False,
):
    """获取各市场代表指数的历史曲线数据（用于底图）"""
    svc = _market_service(request)
    return await svc.get_market_trend(market.lower(), points=points, refresh=refresh)


@router.get("/stocks/{ticker}", response_model=StockDetailOut)
async def get_stock_detail(
    ticker: str,
    request: Request,
    days: int = 90,
    trade_limit: int = 20,
    refresh: bool = False,
    db: AsyncSession = Depends(get_db),
):
    """获取单只股票详情，聚合历史行情和站内交易信息。"""
    svc = _market_service(request)
    normalized_days = max(30, min(days, 365))
    normalized_trade_limit = max(1, min(trade_limit, 50))

    quote = await svc.get_quote(ticker.upper())
    history = await svc.get_stock_history(quote.ticker, days=normalized_days, refresh=refresh)
    market = svc._ticker_market(quote.ticker)

    stats_stmt = (
        select(
            func.count(Trade.id),
            func.coalesce(func.sum(case((Trade.action == "buy", 1), else_=0)), 0),
            func.coalesce(func.sum(case((Trade.action == "sell", 1), else_=0)), 0),
            func.coalesce(func.sum(Trade.amount), 0),
            func.coalesce(func.sum(Trade.amount_cny), 0),
            func.max(Trade.created_at),
            func.count(func.distinct(Account.agent_id)),
        )
        .select_from(Trade)
        .join(Account, Account.id == Trade.account_id, isouter=True)
        .where(Trade.ticker == quote.ticker)
    )
    stats_row = (await db.execute(stats_stmt)).one()
    site_stats = StockSiteStatsOut(
        total_trade_count=int(stats_row[0] or 0),
        buy_trade_count=int(stats_row[1] or 0),
        sell_trade_count=int(stats_row[2] or 0),
        total_amount=_decimal_or_zero(stats_row[3]),
        total_amount_cny=_decimal_or_zero(stats_row[4]),
        last_trade_at=stats_row[5],
        unique_agent_count=int(stats_row[6] or 0),
    )

    trades_stmt = (
        select(Trade, Account.market, Agent.id, Agent.name, Agent.avatar)
        .join(Account, Account.id == Trade.account_id)
        .join(Agent, Agent.id == Account.agent_id)
        .where(Trade.ticker == quote.ticker)
        .order_by(Trade.created_at.desc(), Trade.id.desc())
        .limit(normalized_trade_limit)
    )
    trade_rows = (await db.execute(trades_stmt)).all()
    recent_trades = [
        StockRecentTradeOut(
            trade_id=trade.id,
            agent_id=agent_id,
            agent_name=agent_name,
            agent_avatar=agent_avatar,
            market=trade_market,
            action=trade.action,
            shares=trade.shares,
            price=trade.price,
            amount=trade.amount,
            amount_cny=trade.amount_cny,
            reasoning=trade.reasoning,
            created_at=trade.created_at,
        )
        for trade, trade_market, agent_id, agent_name, agent_avatar in trade_rows
    ]

    position_stmt = (
        select(
            func.count(Position.account_id),
            func.coalesce(func.sum(Position.shares), 0),
        )
        .select_from(Position)
        .where(Position.ticker == quote.ticker, Position.shares > 0)
    )
    holder_count_raw, total_shares_raw = (await db.execute(position_stmt)).one()
    holder_count = int(holder_count_raw or 0)
    total_shares = _decimal_or_zero(total_shares_raw)
    market_value = _money(quote.price * total_shares) if holder_count else Decimal("0")

    fx_pair = "CNY/CNY"
    fx_rate = Decimal("1")
    market_value_cny = market_value
    if holder_count and market in {"us", "hk"}:
        fx_service = getattr(request.app.state, "fx_service", None) or FXService(request.app.state.redis)
        fx_rate_raw, fx_pair, _fx_updated_at = await fx_service.get_rate_to_cny(market)
        fx_rate = Decimal(str(fx_rate_raw))
        market_value_cny = _money(market_value * fx_rate)

    position_stats = StockPositionStatsOut(
        holder_count=holder_count,
        total_shares=total_shares,
        market_value=market_value if holder_count else None,
        market_value_cny=market_value_cny if holder_count else None,
        fx_pair=fx_pair,
        fx_rate=fx_rate,
    )

    return StockDetailOut(
        ticker=quote.ticker,
        name=quote.name,
        market=market,
        days=normalized_days,
        quote=quote,
        history=history,
        site_stats=site_stats,
        recent_trades=recent_trades,
        position_stats=position_stats,
        updated_at=datetime.now(timezone.utc),
    )
