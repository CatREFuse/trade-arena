from __future__ import annotations

from decimal import Decimal

import pytest

from app.services import fx as fx_module
from app.services import market_data as md
from app.schemas import QuoteOut


def _mock_quote(ticker: str, price: str) -> QuoteOut:
    return QuoteOut(
        ticker=ticker,
        price=Decimal(price),
        change_pct=0.5,
        volume=1000,
        market_status="open",
    )


@pytest.mark.asyncio
async def test_public_agent_portfolio_summary_returns_market_holdings_without_token(
    client,
    seeded_accounts,
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_get_quotes_batch(self, tickers: list[str]):
        quotes = {"AAPL": _mock_quote("AAPL", "200.00")}
        return {ticker: quotes[ticker] for ticker in tickers if ticker in quotes}

    async def fake_get_rate_to_cny(self, market: str):
        if market == "us":
            return Decimal("7.20"), "USD/CNY", None
        if market == "hk":
            return Decimal("0.92"), "HKD/CNY", None
        return Decimal("1"), "CNY/CNY", None

    monkeypatch.setattr(md.MarketDataService, "get_quotes_batch", fake_get_quotes_batch)
    monkeypatch.setattr(fx_module.FXService, "get_rate_to_cny", fake_get_rate_to_cny)

    response = await client.get(f"/api/agents/{seeded_accounts.agent_id}/portfolio-summary")
    assert response.status_code == 200
    payload = response.json()

    assert payload["agent_id"] == seeded_accounts.agent_id
    assert Decimal(str(payload["wallet_cash_cny"])) == Decimal("1000000.00")
    assert Decimal(str(payload["total_asset_cny"])) == Decimal("1002880.00")

    markets = {item["market"]: item for item in payload["markets"]}
    assert set(markets.keys()) == {"us", "cn", "hk"}

    us_market = markets["us"]
    assert us_market["account_id"] == seeded_accounts.us_account_id
    assert us_market["holdings_count"] == 1
    assert Decimal(str(us_market["position_value_cny"])) == Decimal("2880.0000000000000000")
    assert len(us_market["positions"]) == 1
    us_position = us_market["positions"][0]
    assert us_position["ticker"] == "AAPL"
    assert Decimal(str(us_position["avg_cost_cny"])) == Decimal("1080.0000000000000000")
    assert Decimal(str(us_position["current_price_cny"])) == Decimal("1440.0000000000000000")
    assert Decimal(str(us_position["pnl_cny"])) == Decimal("720.0000000000000000")
    assert Decimal(str(us_position["market_value_cny"])) == Decimal("2880.0000000000000000")

    cn_market = markets["cn"]
    assert cn_market["account_id"] == seeded_accounts.cn_account_id
    assert cn_market["holdings_count"] == 0
    assert Decimal(str(cn_market["position_value_cny"])) == Decimal("0")

    hk_market = markets["hk"]
    assert hk_market["account_id"] == seeded_accounts.hk_account_id
    assert hk_market["holdings_count"] == 0
    assert Decimal(str(hk_market["position_value_cny"])) == Decimal("0")


@pytest.mark.asyncio
async def test_public_agent_portfolio_summary_returns_404_for_unknown_agent(client):
    response = await client.get("/api/agents/not-exists/portfolio-summary")
    assert response.status_code == 404
    payload = response.json()
    assert payload["detail"]["error"] == "AGENT_NOT_FOUND"
