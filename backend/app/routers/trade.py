from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_account
from app.database import get_db
from app.models import Account
from app.schemas import BuyRequest, SellRequest, TradeOut
from app.services.market_data import MarketDataService
from app.services.trading import TradingService
from app.services.events import EventService

router = APIRouter(prefix="/api/trade", tags=["trade"])


@router.post("/buy", response_model=TradeOut)
async def buy(
    req: BuyRequest,
    request: Request,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    # 获取实时行情
    redis = request.app.state.redis
    market_svc = MarketDataService(redis)
    quote = await market_svc.get_quote(req.ticker.upper())

    req.ticker = req.ticker.upper()

    trading_svc = TradingService(db)
    result = await trading_svc.buy(req, quote.price)
    await db.commit()

    # 发布事件
    event_svc = EventService(redis)
    await event_svc.publish(
        {
            "type": "trade",
            "agent_id": account.agent_id,
            "action": "buy",
            "ticker": req.ticker,
            "shares": str(result.shares),
            "price": str(result.price),
            "amount": str(result.amount),
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
    # 获取实时行情
    redis = request.app.state.redis
    market_svc = MarketDataService(redis)
    quote = await market_svc.get_quote(req.ticker.upper())

    req.ticker = req.ticker.upper()

    trading_svc = TradingService(db)
    result = await trading_svc.sell(req, quote.price)
    await db.commit()

    # 发布事件
    event_svc = EventService(redis)
    await event_svc.publish(
        {
            "type": "trade",
            "agent_id": account.agent_id,
            "action": "sell",
            "ticker": req.ticker,
            "shares": str(result.shares),
            "price": str(result.price),
            "amount": str(result.amount),
            "reasoning": req.reasoning,
        }
    )

    return result
