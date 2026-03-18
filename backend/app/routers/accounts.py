from __future__ import annotations

from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_account
from app.database import get_db
from app.models import Account, Position, Trade
from app.schemas import AccountOut, PortfolioOut, PositionOut, TradeOut
from app.services.market_data import MarketDataService

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("/{account_id}", response_model=AccountOut)
async def get_account(
    account_id: str,
    account: Account = Depends(get_current_account),
):
    if account.id != account_id:
        raise HTTPException(403, detail="无权访问此账户")
    return AccountOut(
        id=account.id,
        agent_id=account.agent_id,
        market=account.market,
        currency=account.currency,
        initial_cash=account.initial_cash,
        cash=account.cash,
    )


@router.get("/{account_id}/portfolio", response_model=PortfolioOut)
async def get_portfolio(
    account_id: str,
    request: Request,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    if account.id != account_id:
        raise HTTPException(403, detail="无权访问此账户")

    result = await db.execute(
        select(Position).where(Position.account_id == account_id)
    )
    positions = result.scalars().all()

    redis = request.app.state.redis
    market_svc = MarketDataService(redis)

    pos_out: list[PositionOut] = []
    for pos in positions:
        current_price: Optional[Decimal] = None
        pnl: Optional[Decimal] = None
        try:
            quote = await market_svc.get_quote(pos.ticker)
            current_price = quote.price
            pnl = (current_price - pos.avg_cost) * pos.shares
        except Exception:
            pass

        pos_out.append(
            PositionOut(
                ticker=pos.ticker,
                shares=pos.shares,
                avg_cost=pos.avg_cost,
                current_price=current_price,
                pnl=pnl,
            )
        )

    return PortfolioOut(cash=account.cash, positions=pos_out)


@router.get("/{account_id}/trades")
async def get_trades(
    account_id: str,
    limit: int = 50,
    offset: int = 0,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    if account.id != account_id:
        raise HTTPException(403, detail="无权访问此账户")

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
            "reasoning": t.reasoning,
            "created_at": t.created_at,
        }
        for t in trades
    ]
