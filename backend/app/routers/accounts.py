from __future__ import annotations

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_accessible_account
from app.database import get_db
from app.models import Account, Position, Trade, Wallet
from app.schemas import AccountOut, PortfolioOut, PositionOut, TradeOut
from app.services.fx import FXService
from app.services.market_data import MarketDataService

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("/{account_id}", response_model=AccountOut)
async def get_account(
    account_id: str,
    account: Account = Depends(get_accessible_account),
    db: AsyncSession = Depends(get_db),
):
    wallet_result = await db.execute(
        select(Wallet).where(Wallet.agent_id == account.agent_id, Wallet.season_id == account.season_id)
    )
    wallet = wallet_result.scalar_one_or_none()
    available_cash_cny = wallet.cash if wallet is not None else Decimal("0")
    initial_cash_cny = wallet.initial_cash if wallet is not None else Decimal("0")
    return AccountOut(
        id=account.id,
        agent_id=account.agent_id,
        market=account.market,
        currency="CNY",
        initial_cash=initial_cash_cny,
        cash=available_cash_cny,
        available_cash_cny=available_cash_cny,
    )


@router.get("/{account_id}/portfolio", response_model=PortfolioOut)
async def get_portfolio(
    account_id: str,
    request: Request,
    account: Account = Depends(get_accessible_account),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Position).where(Position.account_id == account_id)
    )
    positions = result.scalars().all()

    redis = request.app.state.redis
    fx_service = getattr(request.app.state, "fx_service", None) or FXService(redis)
    market_svc = getattr(request.app.state, "market_data_service", None) or MarketDataService(redis)
    quote_map = await market_svc.get_quotes_batch([pos.ticker for pos in positions])
    wallet_result = await db.execute(
        select(Wallet).where(Wallet.agent_id == account.agent_id, Wallet.season_id == account.season_id)
    )
    wallet = wallet_result.scalar_one_or_none()

    fx_pair: Optional[str] = None
    fx_rate: Optional[Decimal] = None
    fx_updated_at = None
    if account.market in {"us", "hk"}:
        rate, pair, updated_at = await fx_service.get_rate_to_cny(account.market)
        fx_rate = Decimal(str(rate))
        fx_pair = pair
        fx_updated_at = updated_at
    else:
        fx_pair = "CNY/CNY"
        fx_rate = Decimal("1")

    pos_out: list[PositionOut] = []
    for pos in positions:
        current_price: Optional[Decimal] = None
        display_avg_cost = pos.avg_cost
        pnl: Optional[Decimal] = None
        pnl_cny: Optional[Decimal] = None
        try:
            quote = quote_map.get(pos.ticker)
            if quote is None:
                raise LookupError(pos.ticker)
            local_current_price = quote.price
            current_price = local_current_price
            if fx_rate is not None:
                display_avg_cost = pos.avg_cost * fx_rate
                current_price = local_current_price * fx_rate
            pnl = (local_current_price - pos.avg_cost) * pos.shares
            if fx_rate is not None:
                pnl_cny = pnl * fx_rate
        except Exception:
            pass

        pos_out.append(
            PositionOut(
                ticker=pos.ticker,
                shares=pos.shares,
                avg_cost=display_avg_cost,
                current_price=current_price,
                pnl=pnl,
                pnl_cny=pnl_cny,
            )
        )

    return PortfolioOut(
        cash=(wallet.cash if wallet is not None else Decimal("0")),
        cash_currency="CNY",
        fx_pair=fx_pair,
        fx_rate=fx_rate,
        fx_updated_at=fx_updated_at,
        positions=pos_out,
    )


@router.get("/{account_id}/trades")
async def get_trades(
    account_id: str,
    limit: int = 50,
    offset: int = 0,
    account: Account = Depends(get_accessible_account),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Trade)
        .where(Trade.account_id == account_id)
        .order_by(Trade.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    trades = result.scalars().all()

    return [
        {
            "trade_id": t.id,
            "ticker": t.ticker,
            "action": t.action,
            "shares": t.shares,
            "price": t.price,
            "amount": t.amount,
            "fee": t.fee,
            "fx_pair": t.fx_pair,
            "fx_rate": t.fx_rate,
            "amount_cny": t.amount_cny,
            "fee_cny": t.fee_cny,
            "cash_after_cny": t.cash_after_cny,
            "reasoning": t.reasoning,
            "created_at": t.created_at,
        }
        for t in trades
    ]
