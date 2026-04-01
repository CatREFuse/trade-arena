from __future__ import annotations

from decimal import Decimal

import pytest

from app.services import fx as fx_module
from app.services import market_data as md
from app.schemas import QuoteOut


def _mock_quote_map(*tickers: str) -> dict[str, QuoteOut]:
    return {
        ticker: QuoteOut(
            ticker=ticker,
            price=Decimal("198.50"),
            change_pct=1.25,
            volume=1000,
            market_status="open",
        )
        for ticker in tickers
    }


@pytest.mark.asyncio
async def test_hk_leaderboard_keeps_agents_without_hk_positions(
    client,
    seeded_accounts,
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_get_quotes_batch(self, tickers: list[str]):
        return _mock_quote_map(*tickers)

    async def fake_get_rate_to_cny(self, market: str):
        if market == "us":
            return Decimal("7.20"), "USD/CNY", None
        if market == "hk":
            return Decimal("0.92"), "HKD/CNY", None
        return Decimal("1"), "CNY/CNY", None

    monkeypatch.setattr(md.MarketDataService, "get_quotes_batch", fake_get_quotes_batch)
    monkeypatch.setattr(fx_module.FXService, "get_rate_to_cny", fake_get_rate_to_cny)

    response = await client.get("/api/leaderboard?market=hk")

    assert response.status_code == 200
    payload = response.json()
    assert payload["market"] == "hk"
    assert len(payload["rankings"]) >= 1
    assert any(item["agent_id"] == seeded_accounts.agent_id for item in payload["rankings"])
