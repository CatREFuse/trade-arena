from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.schemas import BuyRequest, SellRequest
from app.services.trading import TradingService


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
