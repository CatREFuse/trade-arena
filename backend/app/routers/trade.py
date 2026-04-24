from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_account
from app.database import get_db
from app.models import Account, Position, Snapshot, Wallet
from app.schemas import BuyRequest, SellRequest, TradeOut
from app.services.fx import FXService
from app.services.market_data import MarketDataService
from app.services.trading import TradingService
from app.services.events import EventService

router = APIRouter(prefix="/api/trade", tags=["trade"])

MONEY_QUANT = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT)


async def _record_account_snapshot(
    db: AsyncSession,
    account_id: str,
    redis,
    fx_service: FXService,
    market_svc: MarketDataService | None = None,
):
    """把 Agent 总资产快照写到锚点账户，避免多账户重复累计。"""
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        return

    account_rows = await db.execute(select(Account).where(Account.agent_id == account.agent_id))
    accounts = account_rows.scalars().all()
    account_ids = [item.id for item in accounts]
    account_by_id = {item.id: item for item in accounts}
    if not account_ids:
        return

    wallet_row = await db.execute(
        select(Wallet)
        .where(Wallet.agent_id == account.agent_id)
        .order_by(Wallet.updated_at.desc(), Wallet.created_at.desc())
        .limit(1)
    )
    wallet = wallet_row.scalar_one_or_none()
    wallet_cash = wallet.cash if wallet is not None else Decimal("0")

    positions_result = await db.execute(select(Position).where(Position.account_id.in_(account_ids)))
    positions = positions_result.scalars().all()
    market_svc = market_svc or MarketDataService(redis)
    quote_map = await market_svc.get_quotes_batch([pos.ticker for pos in positions])

    usd_cny, _, _ = await fx_service.get_rate_to_cny("us")
    hkd_cny, _, _ = await fx_service.get_rate_to_cny("hk")
    rate_map = {
        "cn": Decimal("1"),
        "us": Decimal(str(usd_cny)),
        "hk": Decimal(str(hkd_cny)),
    }

    total_position_cny = Decimal("0")
    for pos in positions:
        try:
            quote = quote_map.get(pos.ticker)
            if quote is None:
                raise LookupError(pos.ticker)
            local_value = pos.shares * quote.price
        except Exception:
            local_value = pos.shares * pos.avg_cost
        market = account_by_id.get(pos.account_id).market if account_by_id.get(pos.account_id) else "cn"
        fx = rate_map.get(market, Decimal("1"))
        total_position_cny += local_value * fx

    total_asset = _money(wallet_cash + total_position_cny)
    cash_cny = _money(wallet_cash)
    position_cny = _money(total_position_cny)
    snapshot_day = date.today()
    anchor_account = next((item.id for item in accounts if item.market == "cn"), None) or sorted(account_ids)[0]

    existing_result = await db.execute(
        select(Snapshot).where(
            Snapshot.account_id.in_(account_ids),
            Snapshot.date == snapshot_day,
        )
    )
    existing = {snap.account_id: snap for snap in existing_result.scalars().all()}

    for candidate_id in account_ids:
        if candidate_id == anchor_account:
            target_total = total_asset
            target_cash = cash_cny
            target_position = position_cny
            trade_increment = 1
        else:
            target_total = Decimal("0")
            target_cash = Decimal("0")
            target_position = Decimal("0")
            trade_increment = 0

        row = existing.get(candidate_id)
        if row is None:
            db.add(
                Snapshot(
                    account_id=candidate_id,
                    date=snapshot_day,
                    total_asset=target_total,
                    cash=target_cash,
                    position_value=target_position,
                    trade_count=trade_increment,
                )
            )
            continue

        row.total_asset = target_total
        row.cash = target_cash
        row.position_value = target_position
        if trade_increment:
            row.trade_count = row.trade_count + trade_increment


async def _resolve_account_id(req, account: Account, db: AsyncSession):
    """从 token 认证的 account 自动解析 account_id"""
    if req.account_id:
        result = await db.execute(select(Account).where(Account.id == req.account_id))
        target_account = result.scalar_one_or_none()
        if target_account is None or target_account.agent_id != account.agent_id:
            raise HTTPException(403, detail="无权操作该账户")
        return  # 兼容旧方式
    if req.market:
        market = req.market.lower()
        if market not in {"us", "cn", "hk"}:
            raise HTTPException(400, detail="market 只支持 us、cn 或 hk")
        req.account_id = f"{account.agent_id}-{market}"
        return
    raise HTTPException(400, detail="需要提供 market 参数（us、cn 或 hk）")


@router.post("/buy", response_model=TradeOut)
async def buy(
    req: BuyRequest,
    request: Request,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    await _resolve_account_id(req, account, db)

    redis = request.app.state.redis
    fx_service = getattr(request.app.state, "fx_service", None) or FXService(redis)
    market_svc = getattr(request.app.state, "market_data_service", None) or MarketDataService(redis)
    raw_ticker = req.ticker.upper()
    quote = await market_svc.get_quote(raw_ticker)
    req.ticker = raw_ticker

    trading_svc = TradingService(db, fx_service=fx_service)
    result = await trading_svc.buy(req, quote.price, normalized_ticker=quote.ticker)
    await db.commit()

    # 记录资产快照
    await _record_account_snapshot(db, req.account_id, redis, fx_service, market_svc)
    await db.commit()

    event_svc = EventService(redis)
    await event_svc.publish(
        {
            "type": "trade",
            "agent_id": account.agent_id,
            "action": "buy",
            "ticker": result.ticker,
            "shares": str(result.shares),
            "price": str(result.price),
            "amount": str(result.amount),
            "amount_cny": str(result.amount_cny or "0"),
            "reasoning": req.reasoning,
        }
    )

    return result


@router.post("/sell", response_model=TradeOut)
async def sell(
    req: SellRequest,
    request: Request,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    await _resolve_account_id(req, account, db)

    redis = request.app.state.redis
    fx_service = getattr(request.app.state, "fx_service", None) or FXService(redis)
    market_svc = getattr(request.app.state, "market_data_service", None) or MarketDataService(redis)
    raw_ticker = req.ticker.upper()
    quote = await market_svc.get_quote(raw_ticker)
    req.ticker = raw_ticker

    trading_svc = TradingService(db, fx_service=fx_service)
    result = await trading_svc.sell(req, quote.price, normalized_ticker=quote.ticker)
    await db.commit()

    # 记录资产快照
    await _record_account_snapshot(db, req.account_id, redis, fx_service, market_svc)
    await db.commit()

    event_svc = EventService(redis)
    await event_svc.publish(
        {
            "type": "trade",
            "agent_id": account.agent_id,
            "action": "sell",
            "ticker": result.ticker,
            "shares": str(result.shares),
            "price": str(result.price),
            "amount": str(result.amount),
            "amount_cny": str(result.amount_cny or "0"),
            "reasoning": req.reasoning,
        }
    )

    return result
