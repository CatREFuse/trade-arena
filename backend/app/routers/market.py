from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Account, Agent, Position, Trade
from app.schemas import (
    FXHistoryPointOut,
    FXPairSnapshotOut,
    IndexQuoteOut,
    MarketFXOverviewOut,
    MarketBoardSnapshotOut,
    MarketOverviewOut,
    MarketTrendOut,
    QuoteOut,
    StockDetailOut,
    StockIntradayOut,
    StockHistoryPointOut,
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


def _build_fallback_history(days: int, price: Decimal) -> list[StockHistoryPointOut]:
    today = datetime.now(timezone.utc).date()
    close = float(price)
    history: list[StockHistoryPointOut] = []
    for offset in range(days):
        day = today - timedelta(days=days - offset - 1)
        ts = int(datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000)
        history.append(
            StockHistoryPointOut(
                ts=ts,
                date=day.isoformat(),
                open=close,
                high=close,
                low=close,
                close=close,
                volume=0,
            )
        )
    return history


@router.get("/quote/{ticker}", response_model=QuoteOut)
async def get_quote(ticker: str, request: Request):
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


@router.get("/fx", response_model=MarketFXOverviewOut)
async def get_market_fx(
    request: Request,
    hours: int = 24,
    points: int = 120,
):
    redis = request.app.state.redis
    fx_service = getattr(request.app.state, "fx_service", None) or FXService(redis)
    now = datetime.now(timezone.utc)
    snapshots: list[FXPairSnapshotOut] = []
    latest_updated_at: datetime | None = None

    pair_config = (
        ("us", "USD", "CNY"),
        ("hk", "HKD", "CNY"),
    )

    for market, base, quote in pair_config:
        rate, pair, fetched_at, source = await fx_service.get_rate_snapshot(market)
        history_rows, history_source = await fx_service.get_rate_history_with_source(pair, hours=hours, max_points=points)
        history_points = [
            FXHistoryPointOut(
                ts=int(row["fetched_at"].timestamp() * 1000),
                rate=float(row["rate"]),
            )
            for row in history_rows
        ]
        base_rate = history_points[0].rate if history_points else float(rate)
        if base_rate == 0:
            change_pct = 0.0
        else:
            change_pct = round(((float(rate) - base_rate) / base_rate) * 100, 4)
        snapshot_updated_at = fetched_at
        if snapshot_updated_at is None and history_rows:
            snapshot_updated_at = history_rows[-1]["fetched_at"]
        if snapshot_updated_at is not None:
            if latest_updated_at is None or snapshot_updated_at > latest_updated_at:
                latest_updated_at = snapshot_updated_at
        snapshots.append(
            FXPairSnapshotOut(
                pair=pair,
                base=base,
                quote=quote,
                rate=float(rate),
                change_pct_24h=change_pct,
                points=history_points,
                source=source,
                history_source=history_source,
                updated_at=snapshot_updated_at,
            )
        )

    return MarketFXOverviewOut(
        pairs=snapshots,
        updated_at=latest_updated_at or now,
    )


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

    normalized_ticker = ticker.upper()
    try:
        quote = await svc.get_quote(normalized_ticker)
    except HTTPException as exc:
        if exc.status_code != 503:
            raise
        intraday_seed = await svc.get_stock_intraday(
            ticker=normalized_ticker,
            span="1d",
            interval="5m",
            refresh=refresh,
        )
        if not intraday_seed.points:
            raise
        first_close = float(intraday_seed.points[0].close)
        last_close = float(intraday_seed.points[-1].close)
        change_pct = ((last_close - first_close) / first_close * 100) if first_close else 0.0
        quote = QuoteOut(
            ticker=normalized_ticker,
            price=Decimal(str(round(last_close, 4))),
            change_pct=round(change_pct, 4),
            name=normalized_ticker,
            volume=0,
            market_status=svc._market_status(svc._ticker_market(normalized_ticker)),
        )

    try:
        history, history_source = await svc.get_stock_history_with_source(
            quote.ticker,
            days=normalized_days,
            refresh=refresh,
        )
    except HTTPException as exc:
        if exc.status_code != 503:
            raise
        history = _build_fallback_history(normalized_days, quote.price)
        history_source = "route_fallback"
    listed_at = await svc.get_stock_listing_date(quote.ticker, refresh=refresh)
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
        listed_at=listed_at,
        quote=quote,
        history=history,
        history_source=history_source,
        site_stats=site_stats,
        recent_trades=recent_trades,
        position_stats=position_stats,
        updated_at=datetime.now(timezone.utc),
    )


@router.get("/stocks/{ticker}/intraday", response_model=StockIntradayOut)
async def get_stock_intraday(
    ticker: str,
    request: Request,
    span: str = "1d",
    interval: str = "5m",
    refresh: bool = False,
):
    """获取个股分时数据（默认 5 分钟）。"""
    svc = _market_service(request)
    return await svc.get_stock_intraday(
        ticker=ticker.upper(),
        span=span,
        interval=interval,
        refresh=refresh,
    )
