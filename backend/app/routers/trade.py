from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_account
from app.database import get_db
from app.models import Account, Position
from app.schemas import BuyRequest, SellRequest, TradeOut
from app.services.market_data import MarketDataService
from app.services.trading import TradingService
from app.services.events import EventService
from app.routers.agents import record_snapshot

router = APIRouter(prefix="/api/trade", tags=["trade"])


async def _record_account_snapshot(db: AsyncSession, account_id: str, redis):
    """记录账户资产快照"""
    from sqlalchemy import select
    from decimal import Decimal

    # 获取账户
    result = await db.execute(select(Account).where(Account.id == account_id))
    account = result.scalar_one_or_none()
    if not account:
        return

    # 获取持仓
    positions = await db.execute(select(Position).where(Position.account_id == account_id))
    positions = positions.scalars().all()

    # 计算持仓市值
    market_svc = MarketDataService(redis)
    position_value = Decimal("0")
    for pos in positions:
        try:
            quote = await market_svc.get_quote(pos.ticker)
            position_value += pos.shares * quote.price
        except Exception:
            # 如果行情获取失败，使用成本价
            position_value += pos.shares * pos.avg_cost

    total_asset = account.cash + position_value

    await record_snapshot(
        account_id=account_id,
        total_asset=total_asset,
        cash=account.cash,
        position_value=position_value,
        db=db
    )


def _resolve_account_id(req, account: Account):
    """从 token 认证的 account 自动解析 account_id"""
    if req.account_id:
        if not req.account_id.startswith(f"{account.agent_id}-"):
            raise HTTPException(403, detail="无权操作该账户")
        return  # 兼容旧方式
    if req.market:
        market = req.market.lower()
        if market not in {"us", "cn"}:
            raise HTTPException(400, detail="market 只支持 us 或 cn")
        req.account_id = f"{account.agent_id}-{market}"
        return
    raise HTTPException(400, detail="需要提供 market 参数（us 或 cn）")


@router.post("/buy", response_model=TradeOut)
async def buy(
    req: BuyRequest,
    request: Request,
    account: Account = Depends(get_current_account),
    db: AsyncSession = Depends(get_db),
):
    _resolve_account_id(req, account)

    redis = request.app.state.redis
    market_svc = MarketDataService(redis)
    quote = await market_svc.get_quote(req.ticker.upper())

    req.ticker = req.ticker.upper()

    trading_svc = TradingService(db)
    result = await trading_svc.buy(req, quote.price)
    await db.commit()

    # 记录资产快照
    await _record_account_snapshot(db, req.account_id, redis)
    await db.commit()

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
    _resolve_account_id(req, account)

    redis = request.app.state.redis
    market_svc = MarketDataService(redis)
    quote = await market_svc.get_quote(req.ticker.upper())

    req.ticker = req.ticker.upper()

    trading_svc = TradingService(db)
    result = await trading_svc.sell(req, quote.price)
    await db.commit()

    # 记录资产快照
    await _record_account_snapshot(db, req.account_id, redis)
    await db.commit()

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
