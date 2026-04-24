from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.schemas import QuoteOut, StockHistoryPointOut, StockIntradayOut, StockIntradayPointOut
from app.models import Agent
from app.services import fx as fx_module
from app.services import market_data as md


@pytest.mark.asyncio
async def test_stock_detail_route_returns_history_and_site_stats(
    client,
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_get_quote(self, ticker: str):
        assert ticker == "AAPL"
        return QuoteOut(
            ticker="AAPL",
            price=Decimal("198.50"),
            change_pct=1.25,
            name="Apple",
            volume=1000,
            market_status="open",
        )

    async def fake_get_stock_history_with_source(
        self,
        ticker: str,
        *,
        days: int = 90,
        refresh: bool = False,
    ):
        assert ticker == "AAPL"
        assert days == 90
        assert refresh is False
        return (
            [
                StockHistoryPointOut(
                    ts=1774915200000,
                    date="2026-03-30",
                    open=195.0,
                    high=199.0,
                    low=194.0,
                    close=198.5,
                    volume=1200,
                )
            ],
            "yahoo_chart",
        )

    async def fake_get_rate_to_cny(self, market: str):
        assert market == "us"
        return Decimal("7.20"), "USD/CNY", None

    async def fake_get_stock_listing_date(self, ticker: str, *, refresh: bool = False):
        assert ticker == "AAPL"
        assert refresh is False
        return "1980-12-12"

    monkeypatch.setattr(md.MarketDataService, "get_quote", fake_get_quote)
    monkeypatch.setattr(md.MarketDataService, "get_stock_history_with_source", fake_get_stock_history_with_source)
    monkeypatch.setattr(md.MarketDataService, "get_stock_listing_date", fake_get_stock_listing_date)
    monkeypatch.setattr(fx_module.FXService, "get_rate_to_cny", fake_get_rate_to_cny)

    response = await client.get("/api/market/stocks/aapl?days=90&trade_limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "AAPL"
    assert payload["name"] == "Apple"
    assert payload["market"] == "us"
    assert payload["days"] == 90
    assert payload["listed_at"] == "1980-12-12"
    assert payload["history_source"] == "yahoo_chart"
    assert payload["quote"]["price"] == "198.50"
    assert payload["history"][0]["date"] == "2026-03-30"
    assert payload["site_stats"]["total_trade_count"] == 1
    assert payload["site_stats"]["buy_trade_count"] == 1
    assert payload["site_stats"]["sell_trade_count"] == 0
    assert payload["site_stats"]["unique_agent_count"] == 1
    assert payload["recent_trades"][0]["agent_id"] == "alpha"
    assert payload["recent_trades"][0]["agent_name"] == "Alpha Trader"
    assert payload["recent_trades"][0]["market"] == "us"
    assert payload["position_stats"]["holder_count"] == 1
    assert payload["position_stats"]["total_shares"] == "2.000000"
    assert payload["position_stats"]["market_value"] == "397.00"
    assert payload["position_stats"]["market_value_cny"] == "2858.40"
    assert payload["position_stats"]["fx_pair"] == "USD/CNY"
    assert payload["position_stats"]["fx_rate"] == "7.20"


@pytest.mark.asyncio
async def test_stock_detail_route_hides_deleted_agent_stats(
    client,
    db_session_factory,
    monkeypatch: pytest.MonkeyPatch,
):
    async with db_session_factory() as session:
        agent = (await session.execute(select(Agent).where(Agent.id == "alpha"))).scalar_one()
        agent.is_deleted = True
        await session.commit()

    async def fake_get_quote(self, ticker: str):
        return QuoteOut(
            ticker="AAPL",
            price=Decimal("198.50"),
            change_pct=1.25,
            name="Apple",
            volume=1000,
            market_status="open",
        )

    async def fake_get_stock_history_with_source(self, ticker: str, *, days: int = 90, refresh: bool = False):
        return [], "yahoo_chart"

    async def fake_get_stock_listing_date(self, ticker: str, *, refresh: bool = False):
        return "1980-12-12"

    monkeypatch.setattr(md.MarketDataService, "get_quote", fake_get_quote)
    monkeypatch.setattr(md.MarketDataService, "get_stock_history_with_source", fake_get_stock_history_with_source)
    monkeypatch.setattr(md.MarketDataService, "get_stock_listing_date", fake_get_stock_listing_date)

    response = await client.get("/api/market/stocks/aapl?days=90&trade_limit=5")

    assert response.status_code == 200
    payload = response.json()
    assert payload["site_stats"]["total_trade_count"] == 0
    assert payload["site_stats"]["unique_agent_count"] == 0
    assert payload["recent_trades"] == []
    assert payload["position_stats"]["holder_count"] == 0
    assert payload["position_stats"]["total_shares"] == "0.000000"


@pytest.mark.asyncio
async def test_stock_detail_route_returns_404_for_unknown_ticker(client):
    response = await client.get("/api/market/stocks/INVALID999")

    assert response.status_code == 404
    payload = response.json()
    assert payload["detail"]["error"] == "TICKER_NOT_FOUND"


@pytest.mark.asyncio
async def test_market_fx_route_returns_realtime_and_history(
    client,
    monkeypatch: pytest.MonkeyPatch,
):
    now = datetime.now(timezone.utc).replace(microsecond=0)

    async def fake_get_rate_snapshot(self, market: str):
        if market == "us":
            return 7.25, "USD/CNY", now, "stooq_svg"
        if market == "hk":
            return 0.93, "HKD/CNY", now - timedelta(minutes=1), "frankfurter"
        raise AssertionError(market)

    async def fake_get_rate_history_with_source(self, pair: str, *, hours: int = 24, max_points: int = 120):
        assert hours == 24
        assert max_points == 120
        if pair == "USD/CNY":
            return [
                {"pair": pair, "rate": 7.10, "fetched_at": now - timedelta(hours=24)},
                {"pair": pair, "rate": 7.25, "fetched_at": now},
            ], "stooq_svg"
        if pair == "HKD/CNY":
            return [
                {"pair": pair, "rate": 0.92, "fetched_at": now - timedelta(hours=24)},
                {"pair": pair, "rate": 0.93, "fetched_at": now - timedelta(minutes=1)},
            ], "frankfurter"
        return [], "redis_history"

    monkeypatch.setattr(fx_module.FXService, "get_rate_snapshot", fake_get_rate_snapshot)
    monkeypatch.setattr(fx_module.FXService, "get_rate_history_with_source", fake_get_rate_history_with_source)

    response = await client.get("/api/market/fx")
    assert response.status_code == 200

    payload = response.json()
    assert len(payload["pairs"]) == 2

    usd = next(item for item in payload["pairs"] if item["pair"] == "USD/CNY")
    assert usd["rate"] == 7.25
    assert usd["change_pct_24h"] > 2.0
    assert usd["source"] == "stooq_svg"
    assert usd["history_source"] == "stooq_svg"
    assert len(usd["points"]) == 2
    assert usd["points"][0]["rate"] == 7.1

    hkd = next(item for item in payload["pairs"] if item["pair"] == "HKD/CNY")
    assert hkd["rate"] == 0.93
    assert hkd["change_pct_24h"] > 1.0
    assert hkd["source"] == "frankfurter"
    assert hkd["history_source"] == "frankfurter"
    assert len(hkd["points"]) == 2


@pytest.mark.asyncio
async def test_stock_intraday_route_returns_points(
    client,
    monkeypatch: pytest.MonkeyPatch,
):
    async def fake_get_stock_intraday(
        self,
        ticker: str,
        *,
        span: str = "1d",
        interval: str = "5m",
        refresh: bool = False,
    ):
        assert ticker == "AAPL"
        assert span == "1d"
        assert interval == "5m"
        assert refresh is False
        return StockIntradayOut(
            ticker="AAPL",
            interval="5m",
            span="1d",
            source="yahoo_chart",
            points=[
                StockIntradayPointOut(
                    ts=1774915200000,
                    time="2026-03-30T00:00:00+00:00",
                    open=195.0,
                    high=199.0,
                    low=194.0,
                    close=198.5,
                    volume=1200,
                )
            ],
            updated_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(md.MarketDataService, "get_stock_intraday", fake_get_stock_intraday)

    response = await client.get("/api/market/stocks/aapl/intraday?span=1d&interval=5m")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "AAPL"
    assert payload["interval"] == "5m"
    assert payload["span"] == "1d"
    assert payload["source"] == "yahoo_chart"
    assert len(payload["points"]) == 1
    assert payload["points"][0]["close"] == 198.5
