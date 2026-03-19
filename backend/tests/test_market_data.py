from __future__ import annotations

import json
from decimal import Decimal

import pytest

from app.schemas import IndexQuoteOut, MarketBoardItemOut, QuoteOut
from app.services import market_data as md
from app.services.market_providers import QuoteData


class RaisingProvider:
    async def get_quote(self, ticker: str):
        raise RuntimeError(f"provider failure for {ticker}")

    async def get_index(self, symbol: str):
        raise RuntimeError(f"provider failure for {symbol}")


def test_market_board_catalog_is_substantially_larger():
    assert len(md.MARKET_BOARD["us"]) >= 40
    assert len(md.MARKET_BOARD["cn"]) >= 30


@pytest.mark.asyncio
async def test_get_quote_uses_cache_without_provider_call(fake_redis, monkeypatch):
    fake_redis.store["quote:AAPL"] = json.dumps(
        {
            "price": "198.50",
            "change_pct": 1.25,
            "volume": 1000,
            "market_status": "open",
        }
    ).encode("utf-8")

    def _fail_if_called(_ticker: str):
        raise AssertionError("provider should not be called on cache hit")

    service = md.MarketDataService(fake_redis)
    monkeypatch.setattr(service, "_get_provider", _fail_if_called)
    quote = await service.get_quote("aapl")

    assert isinstance(quote, QuoteOut)
    assert quote.ticker == "AAPL"
    assert quote.price == Decimal("198.50")
    assert quote.change_pct == 1.25
    assert fake_redis.set_calls == []


@pytest.mark.asyncio
async def test_get_quote_falls_back_to_mock_and_caches_result(fake_redis, monkeypatch):
    service = md.MarketDataService(fake_redis)
    monkeypatch.setattr(service, "_get_provider", lambda _ticker: RaisingProvider())

    async def mock_get_quote(ticker: str):
        return QuoteData(
            ticker=ticker,
            price=123.45,
            change_pct=-2.34,
            volume=54321,
            market_status="open",
            previous_close=126.42,
        )

    monkeypatch.setattr(service.mock, "get_quote", mock_get_quote)

    quote = await service.get_quote("AAPL")

    assert isinstance(quote, QuoteOut)
    assert quote.ticker == "AAPL"
    assert quote.price == Decimal("123.45")
    assert quote.change_pct == -2.34
    assert fake_redis.set_calls == [("quote:AAPL", 60, fake_redis.store["quote:AAPL"].decode("utf-8"))]

    cached = json.loads(fake_redis.store["quote:AAPL"].decode("utf-8"))
    assert cached["price"] == 123.45
    assert cached["change_pct"] == -2.34
    assert cached["volume"] == 54321
    assert cached["market_status"] == "open"


@pytest.mark.asyncio
async def test_get_index_falls_back_to_mock_and_caches_result(fake_redis, monkeypatch):
    service = md.MarketDataService(fake_redis)

    async def provider_returns_none(symbol: str):
        return None

    async def mock_get_index(symbol: str):
        return QuoteData(
            ticker=symbol,
            price=5892.0,
            change_pct=0.85,
            volume=0,
            market_status="open",
            name="S&P 500",
        )

    monkeypatch.setattr(service.yahoo, "get_index", provider_returns_none)
    monkeypatch.setattr(service.mock, "get_index", mock_get_index)

    index = await service.get_index("SPX", "us")

    assert isinstance(index, IndexQuoteOut)
    assert index.symbol == "SPX"
    assert index.name == "S&P 500"
    assert index.price == 5892.0
    assert index.change_pct == 0.85
    assert fake_redis.set_calls == [("index:us:SPX", 300, fake_redis.store["index:us:SPX"].decode("utf-8"))]

    cached = json.loads(fake_redis.store["index:us:SPX"].decode("utf-8"))
    assert cached["symbol"] == "SPX"
    assert cached["name"] == "S&P 500"
    assert cached["price"] == 5892.0
    assert cached["change_pct"] == 0.85


@pytest.mark.asyncio
async def test_get_market_board_batches_large_universe_and_falls_back(fake_redis, monkeypatch):
    service = md.MarketDataService(fake_redis)
    monkeypatch.setattr(md, "BOARD_FETCH_CHUNK_SIZE", 4)

    batch_calls: list[tuple[str, ...]] = []
    fallback_calls: list[str] = []

    async def fake_batch_quotes(tickers: list[str]):
        batch_calls.append(tuple(tickers))
        quotes = {}
        for index, ticker in enumerate(tickers):
            if index == 0:
                continue
            quotes[ticker] = QuoteData(
                ticker=ticker,
                price=200 + len(batch_calls) + index,
                change_pct=5 - index,
                volume=1000 + index,
                market_status="open",
                name=f"Name {ticker}",
                previous_close=190 + index,
            )
        return quotes

    async def fake_mock_quote(ticker: str):
        fallback_calls.append(ticker)
        return QuoteData(
            ticker=ticker,
            price=88.8,
            change_pct=-0.8,
            volume=888,
            market_status="closed",
            name=f"Fallback {ticker}",
            previous_close=89.5,
        )

    monkeypatch.setattr(service.yahoo, "get_quotes_batch", fake_batch_quotes)
    monkeypatch.setattr(service.mock, "get_quote", fake_mock_quote)

    board = await service.get_market_board("us")

    assert len(board) == len(md.MARKET_BOARD["us"])
    assert isinstance(board[0], MarketBoardItemOut)
    assert board[0].ticker == "AAPL"
    assert board[0].name == "Fallback AAPL"
    assert board[1].ticker == "MSFT"
    assert batch_calls
    assert len(batch_calls) == (len(md.MARKET_BOARD["us"]) + 3) // 4
    assert len(fallback_calls) == len(batch_calls)
    assert fake_redis.set_calls[-1][0] == "market:board:v2:us"
    assert board[0].price == Decimal("88.8")


@pytest.mark.asyncio
async def test_get_market_overview_caches_aggregate_snapshot(fake_redis, monkeypatch):
    service = md.MarketDataService(fake_redis)
    calls = {"indices": 0, "boards": []}

    async def fake_get_all_indices(refresh: bool = False):
        calls["indices"] += 1
        return [
            IndexQuoteOut(symbol="SPX", name="S&P 500", price=6000.0, change_pct=1.25, market="us"),
            IndexQuoteOut(symbol="SH", name="上证指数", price=3200.0, change_pct=-0.35, market="cn"),
        ]

    async def fake_get_market_board(market: str, refresh: bool = False):
        calls["boards"].append((market, refresh))
        return [
            MarketBoardItemOut(
                ticker="AAPL" if market == "us" else "600519.SH",
                name="Sample",
                market=market,
                price=Decimal("200"),
                change_pct=2.5 if market == "us" else -1.1,
                volume=1000,
                market_status="open",
            )
        ]

    monkeypatch.setattr(service, "get_all_indices", fake_get_all_indices)
    monkeypatch.setattr(service, "get_market_board", fake_get_market_board)

    overview = await service.get_market_overview()
    assert overview.markets[0].stock_count == 1
    assert overview.markets[0].leader is not None
    assert overview.boards["us"][0].ticker == "AAPL"
    assert fake_redis.set_calls[-1][0] == "market:overview:v2"

    second = await service.get_market_overview()
    assert second.markets[1].market == "cn"
    assert calls["indices"] == 1
    assert calls["boards"] == [("us", False), ("cn", False)]

    refreshed = await service.get_market_overview(refresh=True)
    assert refreshed.updated_at is not None
    assert calls["indices"] == 2
    assert calls["boards"][-2:] == [("us", True), ("cn", True)]
