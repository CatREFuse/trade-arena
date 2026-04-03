from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Account, Position, Trade, Wallet
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
from app.services.fx import FXService
from app.services.market_calendar import MarketCalendarService

MONEY_QUANT = Decimal("0.01")
SHARES_QUANT = Decimal("0.000001")


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY_QUANT)


class TradingService:
    def __init__(
        self,
        db: AsyncSession,
        market_calendar: MarketCalendarService | None = None,
        fx_service: FXService | None = None,
    ):
        self.db = db
        self.market_calendar = market_calendar or MarketCalendarService()
        self.fx_service = fx_service

    async def _resolve_wallet(self, account: Account) -> Wallet:
        db = self.db
        wallet_result = await db.execute(
            select(Wallet)
            .where(Wallet.agent_id == account.agent_id)
            .order_by(Wallet.updated_at.desc(), Wallet.created_at.desc())
            .limit(1)
            .with_for_update()
        )
        wallet = wallet_result.scalar_one_or_none()
        if wallet is not None:
            return wallet

        initial_cash = _money(Decimal(str(settings.total_starting_capital_cny)))
        wallet = Wallet(
            id=f"{account.agent_id}-wallet",
            agent_id=account.agent_id,
            currency="CNY",
            initial_cash=initial_cash,
            cash=initial_cash,
        )
        db.add(wallet)
        await db.flush()
        return wallet

    async def _resolve_rate(self, market: str) -> tuple[Decimal, str, datetime | None]:
        market_normalized = market.lower()
        if market_normalized == "cn":
            return Decimal("1"), "CNY/CNY", None

        if self.fx_service is not None:
            rate, pair, updated_at = await self.fx_service.get_rate_to_cny(market_normalized)
            return Decimal(str(rate)), pair, updated_at

        if market_normalized == "us":
            return Decimal(str(settings.exchange_rate)), "USD/CNY", None
        if market_normalized == "hk":
            fallback_hkd = Decimal(str(getattr(settings, "exchange_rate_hkd_to_cny", 0.92)))
            return fallback_hkd, "HKD/CNY", None

        return Decimal("1"), "CNY/CNY", None

    @staticmethod
    def _canonical_trade_ticker(request_ticker: str, normalized_ticker: str | None = None) -> str:
        if normalized_ticker:
            normalized = normalized_ticker.strip().upper()
            if normalized:
                return normalized
        return request_ticker.strip().upper()

    async def _load_position_for_trade(
        self,
        *,
        account_id: str,
        request_ticker: str,
        canonical_ticker: str,
        for_update: bool = False,
    ) -> Position | None:
        candidates = {canonical_ticker}
        raw_ticker = request_ticker.strip().upper()
        if raw_ticker:
            candidates.add(raw_ticker)

        stmt = select(Position).where(
            Position.account_id == account_id,
            Position.ticker.in_(sorted(candidates)),
        )
        if for_update:
            stmt = stmt.with_for_update()
        rows = (await self.db.execute(stmt)).scalars().all()
        if not rows:
            return None

        canonical_row = next((row for row in rows if row.ticker == canonical_ticker), rows[0])
        if len(rows) > 1:
            total_shares = sum((row.shares for row in rows), Decimal("0"))
            total_cost = sum((row.shares * row.avg_cost for row in rows), Decimal("0"))
            canonical_row.shares = total_shares
            canonical_row.avg_cost = (total_cost / total_shares) if total_shares > 0 else Decimal("0")
            canonical_row.updated_at = datetime.utcnow()
            for row in rows:
                if row is canonical_row:
                    continue
                await self.db.delete(row)

        if canonical_row.ticker != canonical_ticker:
            canonical_row.ticker = canonical_ticker
            canonical_row.updated_at = datetime.utcnow()
        return canonical_row

    async def buy(self, req: BuyRequest, price: Decimal, normalized_ticker: str | None = None) -> TradeOut:
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
        wallet = await self._resolve_wallet(account)
        now_utc = datetime.now(timezone.utc)
        if not self.market_calendar.is_trade_open(account.market, now_utc=now_utc):
            raise MarketClosed(
                market=account.market,
                now_local=self.market_calendar.now_local_iso(account.market, now_utc=now_utc),
                next_open_at=self.market_calendar.next_open_local_iso(account.market, now_utc=now_utc),
            )

        fx_rate, fx_pair, _fx_updated_at = await self._resolve_rate(account.market)
        fee = _money(req.amount * Decimal(str(settings.trade_fee_rate)))
        total_cost = req.amount + fee
        total_cost_cny = _money(total_cost * fx_rate)
        canonical_ticker = self._canonical_trade_ticker(req.ticker, normalized_ticker)

        if wallet.cash < total_cost_cny:
            raise InsufficientFunds(float(wallet.cash), float(total_cost_cny))

        shares_to_buy = (req.amount / price).quantize(SHARES_QUANT)

        position = await self._load_position_for_trade(
            account_id=req.account_id,
            request_ticker=req.ticker,
            canonical_ticker=canonical_ticker,
        )

        existing_value = Decimal("0")
        if position:
            existing_value = position.shares * price * fx_rate

        new_total_value = existing_value + (req.amount * fx_rate)
        position_limit = wallet.initial_cash * Decimal(str(settings.max_position_ratio))

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
                ticker=canonical_ticker,
                shares=shares_to_buy,
                avg_cost=price,
            )
            db.add(position)

        wallet.cash = _money(wallet.cash - total_cost_cny)
        account.cash = wallet.cash
        account.initial_cash = wallet.initial_cash
        account.currency = "CNY"

        trade = Trade(
            account_id=req.account_id,
            ticker=canonical_ticker,
            action="buy",
            shares=shares_to_buy,
            price=price,
            amount=req.amount,
            fee=fee,
            reasoning=req.reasoning,
            reasoning_full=req.reasoning_full,
            idempotency_key=req.idempotency_key,
            fx_rate=fx_rate,
            fx_pair=fx_pair,
            amount_cny=_money(req.amount * fx_rate),
            fee_cny=_money(fee * fx_rate),
            cash_after_cny=wallet.cash,
        )
        db.add(trade)

        await db.flush()

        return TradeOut(
            trade_id=trade.id,
            ticker=canonical_ticker,
            action="buy",
            shares=shares_to_buy,
            price=price,
            amount=req.amount,
            fee=fee,
            cash_after=wallet.cash,
            fx_pair=fx_pair,
            fx_rate=fx_rate,
            amount_cny=trade.amount_cny,
            fee_cny=trade.fee_cny,
            cash_after_cny=wallet.cash,
            created_at=trade.created_at,
        )

    async def sell(self, req: SellRequest, price: Decimal, normalized_ticker: str | None = None) -> TradeOut:
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
        wallet = await self._resolve_wallet(account)
        now_utc = datetime.now(timezone.utc)
        if not self.market_calendar.is_trade_open(account.market, now_utc=now_utc):
            raise MarketClosed(
                market=account.market,
                now_local=self.market_calendar.now_local_iso(account.market, now_utc=now_utc),
                next_open_at=self.market_calendar.next_open_local_iso(account.market, now_utc=now_utc),
            )
        fx_rate, fx_pair, _fx_updated_at = await self._resolve_rate(account.market)
        canonical_ticker = self._canonical_trade_ticker(req.ticker, normalized_ticker)

        position = await self._load_position_for_trade(
            account_id=req.account_id,
            request_ticker=req.ticker,
            canonical_ticker=canonical_ticker,
            for_update=True,
        )

        # --- 持仓数量检查（禁止卖空）---
        if position is None or position.shares < req.shares:
            raise InsufficientShares()

        amount = _money(req.shares * price)
        fee = _money(amount * Decimal(str(settings.trade_fee_rate)))
        net_proceeds = amount - fee
        net_proceeds_cny = _money(net_proceeds * fx_rate)

        position.shares = position.shares - req.shares
        if position.shares <= Decimal("0"):
            await db.delete(position)
        else:
            position.updated_at = datetime.utcnow()

        wallet.cash = _money(wallet.cash + net_proceeds_cny)
        account.cash = wallet.cash
        account.initial_cash = wallet.initial_cash
        account.currency = "CNY"

        trade = Trade(
            account_id=req.account_id,
            ticker=canonical_ticker,
            action="sell",
            shares=req.shares,
            price=price,
            amount=amount,
            fee=fee,
            reasoning=req.reasoning,
            reasoning_full=req.reasoning_full,
            idempotency_key=req.idempotency_key,
            fx_rate=fx_rate,
            fx_pair=fx_pair,
            amount_cny=_money(amount * fx_rate),
            fee_cny=_money(fee * fx_rate),
            cash_after_cny=wallet.cash,
        )
        db.add(trade)

        await db.flush()

        return TradeOut(
            trade_id=trade.id,
            ticker=canonical_ticker,
            action="sell",
            shares=req.shares,
            price=price,
            amount=amount,
            fee=fee,
            cash_after=wallet.cash,
            fx_pair=fx_pair,
            fx_rate=fx_rate,
            amount_cny=trade.amount_cny,
            fee_cny=trade.fee_cny,
            cash_after_cny=wallet.cash,
            created_at=trade.created_at,
        )
