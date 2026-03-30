from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Account, Position, Trade
from app.schemas import BuyRequest, SellRequest, TradeOut
from app.errors import (
    InsufficientFunds,
    InvalidTradeAmount,
    InvalidTradeShares,
    PositionLimitExceeded,
    InsufficientShares,
    DuplicateTrade,
    MarketClosed,
)
from app.config import settings
from app.services.market_calendar import MarketCalendarService


class TradingService:
    def __init__(self, db: AsyncSession, market_calendar: MarketCalendarService | None = None):
        self.db = db
        self.market_calendar = market_calendar or MarketCalendarService()

    async def buy(self, req: BuyRequest, price: Decimal) -> TradeOut:
        db = self.db

        if req.amount <= 0:
            raise InvalidTradeAmount()

        # --- 幂等性检查 ---
        if req.idempotency_key:
            existing = await db.execute(
                select(Trade).where(Trade.idempotency_key == req.idempotency_key)
            )
            dup = existing.scalar_one_or_none()
            if dup:
                raise DuplicateTrade()

        # --- 锁定账户行 ---
        result = await db.execute(
            select(Account)
            .where(Account.id == req.account_id)
            .with_for_update()
        )
        account = result.scalar_one_or_none()
        if account is None:
            raise InsufficientFunds(0, float(req.amount))
        now_utc = datetime.now(timezone.utc)
        if not self.market_calendar.is_trade_open(account.market, now_utc=now_utc):
            raise MarketClosed(
                market=account.market,
                now_local=self.market_calendar.now_local_iso(account.market, now_utc=now_utc),
                next_open_at=self.market_calendar.next_open_local_iso(account.market, now_utc=now_utc),
            )

        fee = req.amount * Decimal(str(settings.trade_fee_rate))
        total_cost = req.amount + fee

        # --- 余额检查 ---
        if account.cash < total_cost:
            raise InsufficientFunds(float(account.cash), float(total_cost))

        # --- 仓位 30% 上限检查（基于 initial_cash）---
        shares_to_buy = req.amount / price

        # 查询已有持仓
        pos_result = await db.execute(
            select(Position).where(
                Position.account_id == req.account_id,
                Position.ticker == req.ticker,
            )
        )
        position = pos_result.scalar_one_or_none()

        existing_value = Decimal("0")
        if position:
            existing_value = position.shares * price

        new_total_value = existing_value + req.amount
        position_limit = account.initial_cash * Decimal(str(settings.max_position_ratio))

        if new_total_value > position_limit:
            raise PositionLimitExceeded()

        # --- 更新持仓 ---
        if position:
            old_total = position.shares * position.avg_cost
            new_total = old_total + req.amount
            position.shares = position.shares + shares_to_buy
            position.avg_cost = new_total / position.shares if position.shares else Decimal("0")
            position.updated_at = datetime.utcnow()
        else:
            position = Position(
                account_id=req.account_id,
                ticker=req.ticker,
                shares=shares_to_buy,
                avg_cost=price,
            )
            db.add(position)

        # --- 扣除现金 ---
        account.cash = account.cash - total_cost

        # --- 记录交易 ---
        trade = Trade(
            account_id=req.account_id,
            ticker=req.ticker,
            action="buy",
            shares=shares_to_buy,
            price=price,
            amount=req.amount,
            fee=fee,
            reasoning=req.reasoning,
            reasoning_full=req.reasoning_full,
            idempotency_key=req.idempotency_key,
        )
        db.add(trade)

        await db.flush()

        return TradeOut(
            trade_id=trade.id,
            ticker=req.ticker,
            action="buy",
            shares=shares_to_buy,
            price=price,
            amount=req.amount,
            fee=fee,
            cash_after=account.cash,
            created_at=trade.created_at,
        )

    async def sell(self, req: SellRequest, price: Decimal) -> TradeOut:
        db = self.db

        if req.shares <= 0:
            raise InvalidTradeShares()

        # --- 幂等性检查 ---
        if req.idempotency_key:
            existing = await db.execute(
                select(Trade).where(Trade.idempotency_key == req.idempotency_key)
            )
            dup = existing.scalar_one_or_none()
            if dup:
                raise DuplicateTrade()

        # --- 锁定账户行 ---
        result = await db.execute(
            select(Account)
            .where(Account.id == req.account_id)
            .with_for_update()
        )
        account = result.scalar_one_or_none()
        if account is None:
            raise InsufficientFunds(0, 0)
        now_utc = datetime.now(timezone.utc)
        if not self.market_calendar.is_trade_open(account.market, now_utc=now_utc):
            raise MarketClosed(
                market=account.market,
                now_local=self.market_calendar.now_local_iso(account.market, now_utc=now_utc),
                next_open_at=self.market_calendar.next_open_local_iso(account.market, now_utc=now_utc),
            )

        # --- 查询持仓 ---
        pos_result = await db.execute(
            select(Position)
            .where(
                Position.account_id == req.account_id,
                Position.ticker == req.ticker,
            )
            .with_for_update()
        )
        position = pos_result.scalar_one_or_none()

        # --- 持仓数量检查（禁止卖空）---
        if position is None or position.shares < req.shares:
            raise InsufficientShares()

        amount = req.shares * price
        fee = amount * Decimal(str(settings.trade_fee_rate))
        net_proceeds = amount - fee

        # --- 更新持仓 ---
        position.shares = position.shares - req.shares
        if position.shares <= Decimal("0"):
            await db.delete(position)
        else:
            position.updated_at = datetime.utcnow()

        # --- 增加现金 ---
        account.cash = account.cash + net_proceeds

        # --- 记录交易 ---
        trade = Trade(
            account_id=req.account_id,
            ticker=req.ticker,
            action="sell",
            shares=req.shares,
            price=price,
            amount=amount,
            fee=fee,
            reasoning=req.reasoning,
            reasoning_full=req.reasoning_full,
            idempotency_key=req.idempotency_key,
        )
        db.add(trade)

        await db.flush()

        return TradeOut(
            trade_id=trade.id,
            ticker=req.ticker,
            action="sell",
            shares=req.shares,
            price=price,
            amount=amount,
            fee=fee,
            cash_after=account.cash,
            created_at=trade.created_at,
        )
