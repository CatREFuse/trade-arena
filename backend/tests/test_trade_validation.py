from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select

import app.routers.trade as trade_router
from app.models import Account, Agent, Position, Wallet
from app.schemas import BuyRequest, QuoteOut, SellRequest
from app.services.market_calendar import MarketCalendarService
from app.services import market_data as md
from app.services.trading import TradingService


async def _noop_async(*_args, **_kwargs):
    return None


async def _fake_quote_for_tests(self, ticker: str):
    return QuoteOut(
        ticker=ticker.upper(),
        price=Decimal("100"),
        change_pct=0,
        name=ticker.upper(),
        volume=1000,
        market_status="open",
    )


@pytest.mark.parametrize("amount", [0, -1])
@pytest.mark.asyncio
async def test_buy_rejects_non_positive_amount_at_schema_level(
    client, seeded_accounts, amount
):
    response = await client.post(
        "/api/trade/buy",
        headers={"Authorization": f"Bearer {seeded_accounts.token}"},
        json={
            "market": "us",
            "ticker": "AAPL",
            "amount": amount,
        },
    )

    assert response.status_code == 422


@pytest.mark.parametrize("shares", [0, -1])
@pytest.mark.asyncio
async def test_sell_rejects_non_positive_shares_at_schema_level(
    client, seeded_accounts, shares
):
    response = await client.post(
        "/api/trade/sell",
        headers={"Authorization": f"Bearer {seeded_accounts.token}"},
        json={
            "market": "us",
            "ticker": "AAPL",
            "shares": shares,
        },
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_trading_service_rejects_non_positive_amount_bypass(
    db_session_factory, seeded_accounts
):
    async with db_session_factory() as session:
        service = TradingService(session)
        req = BuyRequest.model_construct(
            account_id=seeded_accounts.us_account_id,
            market="us",
            ticker="AAPL",
            amount=Decimal("0"),
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.buy(req, Decimal("150.00"))

    assert getattr(exc_info.value, "status_code", None) == 422
    assert exc_info.value.detail["error"] == "INVALID_TRADE_AMOUNT"


@pytest.mark.asyncio
async def test_trading_service_rejects_non_positive_shares_bypass(
    db_session_factory, seeded_accounts
):
    async with db_session_factory() as session:
        service = TradingService(session)
        req = SellRequest.model_construct(
            account_id=seeded_accounts.us_account_id,
            market="us",
            ticker="AAPL",
            shares=Decimal("0"),
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.sell(req, Decimal("150.00"))

    assert getattr(exc_info.value, "status_code", None) == 422
    assert exc_info.value.detail["error"] == "INVALID_TRADE_SHARES"


@pytest.mark.asyncio
async def test_trade_buy_invalid_ticker_returns_404(client, seeded_accounts):
    response = await client.post(
        "/api/trade/buy",
        headers={"Authorization": f"Bearer {seeded_accounts.token}"},
        json={
            "market": "us",
            "ticker": "ZZZZ",
            "amount": 100,
        },
    )

    assert response.status_code == 404
    payload = response.json()
    assert payload["detail"]["error"] == "TICKER_NOT_FOUND"


@pytest.mark.asyncio
async def test_trade_buy_alias_ticker_is_normalized_and_persisted(
    client, seeded_accounts, db_session_factory, monkeypatch
):
    monkeypatch.setattr(MarketCalendarService, "is_trade_open", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(trade_router, "_record_account_snapshot", _noop_async)

    async def fake_get_quote(self, ticker: str):
        assert ticker == "BRK-B"
        return QuoteOut(
            ticker="BRK.B",
            price=Decimal("100"),
            change_pct=0,
            name="Berkshire Hathaway",
            volume=1000,
            market_status="open",
        )

    monkeypatch.setattr(md.MarketDataService, "get_quote", fake_get_quote)

    response = await client.post(
        "/api/trade/buy",
        headers={"Authorization": f"Bearer {seeded_accounts.token}"},
        json={
            "market": "us",
            "ticker": "brk-b",
            "amount": 100,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "BRK.B"

    async with db_session_factory() as session:
        rows = (
            await session.execute(
                select(Position).where(
                    Position.account_id == seeded_accounts.us_account_id,
                    Position.ticker.in_(("BRK-B", "BRK.B")),
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].ticker == "BRK.B"


@pytest.mark.asyncio
async def test_trade_rejects_account_id_with_same_prefix_different_agent(
    client, seeded_accounts, db_session_factory, monkeypatch
):
    async with db_session_factory() as session:
        wallet_cash = Decimal("1000000.00")
        session.add(
            Agent(
                id="alpha-2",
                name="Alpha Impersonation Target",
                avatar="avatar",
                model="gpt-5.4",
                camp="open",
                style="test",
                framework="pytest",
            )
        )
        session.add(
            Wallet(
                id="alpha-2-wallet",
                agent_id="alpha-2",
                currency="CNY",
                initial_cash=wallet_cash,
                cash=wallet_cash,
            )
        )
        session.add(
            Account(
                id="alpha-2-us",
                agent_id="alpha-2",
                market="us",
                currency="CNY",
                initial_cash=Decimal("0.00"),
                cash=wallet_cash,
                api_token="other-agent-token",
            )
        )
        await session.commit()

    monkeypatch.setattr(MarketCalendarService, "is_trade_open", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(md.MarketDataService, "get_quote", _fake_quote_for_tests)

    response = await client.post(
        "/api/trade/buy",
        headers={"Authorization": f"Bearer {seeded_accounts.token}"},
        json={
            "account_id": "alpha-2-us",
            "ticker": "AAPL",
            "amount": 100,
        },
    )

    assert response.status_code == 403

    async with db_session_factory() as session:
        wallet = (await session.execute(select(Wallet).where(Wallet.agent_id == "alpha-2"))).scalar_one()
        assert wallet.cash == Decimal("1000000.00")


@pytest.mark.asyncio
async def test_trade_sell_rejects_account_id_with_same_prefix_different_agent(
    client, seeded_accounts, db_session_factory
):
    async with db_session_factory() as session:
        wallet_cash = Decimal("1000000.00")
        session.add(
            Agent(
                id="alpha-2",
                name="Alpha Impersonation Target",
                avatar="avatar",
                model="gpt-5.4",
                camp="open",
                style="test",
                framework="pytest",
            )
        )
        session.add(
            Wallet(
                id="alpha-2-wallet",
                agent_id="alpha-2",
                currency="CNY",
                initial_cash=wallet_cash,
                cash=wallet_cash,
            )
        )
        session.add(
            Account(
                id="alpha-2-us",
                agent_id="alpha-2",
                market="us",
                currency="CNY",
                initial_cash=Decimal("0.00"),
                cash=wallet_cash,
                api_token="other-agent-token",
            )
        )
        session.add(
            Position(
                account_id="alpha-2-us",
                ticker="AAPL",
                shares=Decimal("5"),
                avg_cost=Decimal("100"),
            )
        )
        await session.commit()

    response = await client.post(
        "/api/trade/sell",
        headers={"Authorization": f"Bearer {seeded_accounts.token}"},
        json={
            "account_id": "alpha-2-us",
            "ticker": "AAPL",
            "shares": 1,
        },
    )

    assert response.status_code == 403

    async with db_session_factory() as session:
        position = (
            await session.execute(
                select(Position).where(
                    Position.account_id == "alpha-2-us",
                    Position.ticker == "AAPL",
                )
            )
        ).scalar_one()
        assert position.shares == Decimal("5.000000")


@pytest.mark.asyncio
async def test_trade_sell_alias_ticker_supports_legacy_position_symbol(
    client, seeded_accounts, db_session_factory, monkeypatch
):
    async with db_session_factory() as session:
        session.add(
            Position(
                account_id=seeded_accounts.us_account_id,
                ticker="BRK-B",
                shares=Decimal("2"),
                avg_cost=Decimal("100"),
            )
        )
        await session.commit()

    monkeypatch.setattr(MarketCalendarService, "is_trade_open", lambda *_args, **_kwargs: True)
    monkeypatch.setattr(trade_router, "_record_account_snapshot", _noop_async)

    async def fake_get_quote(self, ticker: str):
        assert ticker == "BRK-B"
        return QuoteOut(
            ticker="BRK.B",
            price=Decimal("100"),
            change_pct=0,
            name="Berkshire Hathaway",
            volume=1000,
            market_status="open",
        )

    monkeypatch.setattr(md.MarketDataService, "get_quote", fake_get_quote)

    response = await client.post(
        "/api/trade/sell",
        headers={"Authorization": f"Bearer {seeded_accounts.token}"},
        json={
            "market": "us",
            "ticker": "brk-b",
            "shares": 1,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "BRK.B"

    async with db_session_factory() as session:
        rows = (
            await session.execute(
                select(Position).where(
                    Position.account_id == seeded_accounts.us_account_id,
                    Position.ticker.in_(("BRK-B", "BRK.B")),
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].ticker == "BRK.B"
        assert rows[0].shares == Decimal("1.000000")


@pytest.mark.asyncio
async def test_trade_missing_authorization_header_returns_invalid_token(client):
    response = await client.post(
        "/api/trade/buy",
        json={
            "market": "us",
            "ticker": "AAPL",
            "amount": 100,
        },
    )

    assert response.status_code == 401
    payload = response.json()
    assert payload["detail"]["error"] == "INVALID_TOKEN"


@pytest.mark.asyncio
async def test_trade_buy_rejects_when_market_closed(client, seeded_accounts, monkeypatch):
    monkeypatch.setattr(MarketCalendarService, "is_trade_open", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        MarketCalendarService,
        "now_local_iso",
        lambda *_args, **_kwargs: "2026-03-30T18:45:00+08:00",
    )
    monkeypatch.setattr(
        MarketCalendarService,
        "next_open_local_iso",
        lambda *_args, **_kwargs: "2026-03-31T09:30:00+08:00",
    )
    monkeypatch.setattr(md.MarketDataService, "get_quote", _fake_quote_for_tests)

    response = await client.post(
        "/api/trade/buy",
        headers={"Authorization": f"Bearer {seeded_accounts.token}"},
        json={
            "market": "cn",
            "ticker": "600519.SH",
            "amount": 100,
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"]["error"] == "MARKET_CLOSED"
    assert payload["detail"]["detail"]["market"] == "cn"
    assert payload["detail"]["detail"]["next_open_at"] == "2026-03-31T09:30:00+08:00"


@pytest.mark.asyncio
async def test_trade_sell_rejects_when_market_closed(client, seeded_accounts, monkeypatch):
    monkeypatch.setattr(MarketCalendarService, "is_trade_open", lambda *_args, **_kwargs: False)
    monkeypatch.setattr(
        MarketCalendarService,
        "now_local_iso",
        lambda *_args, **_kwargs: "2026-03-30T17:00:00-04:00",
    )
    monkeypatch.setattr(
        MarketCalendarService,
        "next_open_local_iso",
        lambda *_args, **_kwargs: "2026-03-31T09:30:00-04:00",
    )
    monkeypatch.setattr(md.MarketDataService, "get_quote", _fake_quote_for_tests)

    response = await client.post(
        "/api/trade/sell",
        headers={"Authorization": f"Bearer {seeded_accounts.token}"},
        json={
            "market": "us",
            "ticker": "AAPL",
            "shares": 1,
        },
    )

    assert response.status_code == 400
    payload = response.json()
    assert payload["detail"]["error"] == "MARKET_CLOSED"
    assert payload["detail"]["detail"]["market"] == "us"
    assert payload["detail"]["detail"]["next_open_at"] == "2026-03-31T09:30:00-04:00"
