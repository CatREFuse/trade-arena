from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.schemas import (
    IndexQuoteOut,
    MarketBoardItemOut,
    MarketBoardSnapshotOut,
    MarketOverviewOut,
    QuoteOut,
    StockHistoryPointOut,
    StockIntradayPointOut,
)
from app.services import market_data as md
from app.services.market_providers import AkshareProvider, QuoteData


class RaisingProvider:
    async def get_quote(self, ticker: str):
        raise RuntimeError(f"provider failure for {ticker}")

    async def get_index(self, symbol: str):
        raise RuntimeError(f"provider failure for {symbol}")


class CountingFailProvider:
    def __init__(self):
        self.calls = 0

    async def get_quote(self, ticker: str):
        self.calls += 1
        raise RuntimeError(f"forced provider error for {ticker}")

    async def get_quotes_batch(self, tickers: list[str]):
        self.calls += 1
        raise RuntimeError(f"forced provider error for batch {tickers}")


class CountingSuccessProvider:
    def __init__(self):
        self.calls = 0

    async def get_quote(self, ticker: str):
        self.calls += 1
        return QuoteData(
            ticker=ticker,
            price=100.0,
            change_pct=1.0,
            volume=1000,
            market_status="open",
            previous_close=99.0,
        )

    async def get_quotes_batch(self, tickers: list[str]):
        self.calls += 1
        return {
            ticker: QuoteData(
                ticker=ticker,
                price=100.0,
                change_pct=1.0,
                volume=1000,
                market_status="open",
                previous_close=99.0,
            )
            for ticker in tickers
        }


def test_market_board_catalog_is_substantially_larger():
    assert len(md.MARKET_BOARD["us"]) >= 40
    assert len(md.MARKET_BOARD["cn"]) >= 30
    assert len(md.MARKET_BOARD["hk"]) >= 10


def test_provider_chain_prioritizes_akshare_for_cn_and_hk(fake_redis):
    service = md.MarketDataService(fake_redis)
    cn_chain = service._quote_providers("600519.SH")
    hk_chain = service._quote_providers("0700.HK")

    assert cn_chain
    assert hk_chain
    assert isinstance(cn_chain[0], AkshareProvider)
    assert isinstance(hk_chain[0], AkshareProvider)


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
    service = md.MarketDataService(fake_redis, enable_mock_fallback=True)
    monkeypatch.setattr(service, "_quote_providers", lambda _ticker: [RaisingProvider()])
    monkeypatch.setattr(service.market_calendar, "status", lambda _market: "open")

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
async def test_get_market_board_uses_calendar_status_over_provider_status(fake_redis, monkeypatch):
    service = md.MarketDataService(fake_redis, enable_mock_fallback=False)
    monkeypatch.setattr(service.market_calendar, "status", lambda _market: "closed")

    async def fake_batch_quotes(tickers: list[str], *, status_cache=None):
        return {
            ticker: QuoteData(
                ticker=ticker,
                price=100.0,
                change_pct=0.5,
                volume=1000,
                market_status="open",
                name=f"Name {ticker}",
                previous_close=99.5,
            )
            for ticker in tickers
        }

    monkeypatch.setattr(service, "_get_quotes_batch", fake_batch_quotes)

    board = await service.get_market_board("cn", refresh=True)
    assert board.items
    assert all(item.market_status == "closed" for item in board.items)


@pytest.mark.asyncio
async def test_get_index_falls_back_to_mock_and_caches_result(fake_redis, monkeypatch):
    service = md.MarketDataService(fake_redis, enable_mock_fallback=True)

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
    service = md.MarketDataService(fake_redis, enable_mock_fallback=True)
    monkeypatch.setattr(md, "BOARD_FETCH_CHUNK_SIZE", 4)

    batch_calls: list[tuple[str, ...]] = []
    fallback_calls: list[str] = []

    async def fake_batch_quotes(tickers: list[str], *, status_cache=None):
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

    assert len(board.items) == len(md.MARKET_BOARD["us"])
    assert isinstance(board.items[0], MarketBoardItemOut)
    assert board.items[0].ticker == "AAPL"
    assert board.items[0].name == "Fallback AAPL"
    assert board.items[1].ticker == "MSFT"
    assert batch_calls
    assert len(batch_calls) == (len(md.MARKET_BOARD["us"]) + 3) // 4
    assert len(fallback_calls) == len(batch_calls)
    written_keys = [call[0] for call in fake_redis.set_calls]
    assert "market:board:v3:us" in written_keys
    assert "market:board:last-good:v3:us" in written_keys
    assert board.items[0].price == Decimal("88.8")
    assert board.updated_at is not None


@pytest.mark.asyncio
async def test_get_market_board_uses_last_good_snapshot_when_upstream_returns_empty(fake_redis, monkeypatch):
    service = md.MarketDataService(fake_redis, enable_mock_fallback=False)
    market = "us"
    cache_key = f"market:board:{md.MARKET_CACHE_VERSION}:{market}"
    last_good_key = f"market:board:last-good:{md.MARKET_CACHE_VERSION}:{market}"
    last_good_snapshot = md.MarketBoardSnapshotOut(
        items=[
            md.MarketBoardItemOut(
                ticker="AAPL",
                name="Apple",
                market=market,
                price=Decimal("199.10"),
                change_pct=1.11,
                volume=12345,
                market_status="open",
            )
        ],
        updated_at=datetime.now(timezone.utc),
    )
    fake_redis.store[last_good_key] = json.dumps(last_good_snapshot.model_dump(mode="json")).encode("utf-8")

    async def empty_batch_quotes(_tickers: list[str], *, status_cache=None):
        return {}

    monkeypatch.setattr(service, "_get_quotes_batch", empty_batch_quotes)

    board = await service.get_market_board(market, refresh=True)

    assert len(board.items) == 1
    assert board.items[0].ticker == "AAPL"
    assert board.items[0].price == Decimal("199.10")
    assert any(call[0] == cache_key for call in fake_redis.set_calls)


@pytest.mark.asyncio
async def test_get_market_overview_caches_aggregate_snapshot(fake_redis, monkeypatch):
    service = md.MarketDataService(fake_redis)
    calls = {"indices": 0, "boards": []}

    async def fake_get_all_indices(refresh: bool = False):
        calls["indices"] += 1
        return [
            IndexQuoteOut(symbol="SPX", name="S&P 500", price=6000.0, change_pct=1.25, market="us"),
            IndexQuoteOut(symbol="SH", name="上证指数", price=3200.0, change_pct=-0.35, market="cn"),
            IndexQuoteOut(symbol="HSI", name="恒生指数", price=20000.0, change_pct=0.28, market="hk"),
        ]

    async def fake_get_market_board(market: str, refresh: bool = False):
        calls["boards"].append((market, refresh))
        return MarketBoardSnapshotOut(
            items=[
                MarketBoardItemOut(
                    ticker="AAPL" if market == "us" else ("600519.SH" if market == "cn" else "0700.HK"),
                    name="Sample",
                    market=market,
                    price=Decimal("200"),
                    change_pct=2.5 if market == "us" else (-1.1 if market == "cn" else 1.6),
                    volume=1000,
                    market_status="open",
                )
            ],
            updated_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(service, "get_all_indices", fake_get_all_indices)
    monkeypatch.setattr(service, "get_market_board", fake_get_market_board)

    overview = await service.get_market_overview()
    assert overview.markets[0].stock_count == 1
    assert overview.markets[0].market_status == "open"
    assert overview.markets[0].timezone == "America/New_York"
    assert overview.markets[0].session_windows == ["09:30-16:00"]
    assert overview.markets[0].leader is not None
    assert overview.boards["us"][0].ticker == "AAPL"
    assert fake_redis.set_calls[-1][0] == "market:overview:v3"

    second = await service.get_market_overview()
    assert second.markets[1].market == "cn"
    assert calls["indices"] == 1
    assert calls["boards"] == [("us", False), ("cn", False), ("hk", False)]

    refreshed = await service.get_market_overview(refresh=True)
    assert refreshed.updated_at is not None
    assert calls["indices"] == 2
    assert calls["boards"][-3:] == [("us", True), ("cn", True), ("hk", True)]


@pytest.mark.asyncio
async def test_refresh_requests_share_singleflight_build(fake_redis, monkeypatch):
    service = md.MarketDataService(fake_redis)
    build_calls = 0

    async def fake_build_and_store(cache_key: str, *, refresh: bool):
        nonlocal build_calls
        build_calls += 1
        await asyncio.sleep(0.05)
        overview = MarketOverviewOut(
            indices=[],
            boards={"us": [], "cn": [], "hk": []},
            markets=[],
            updated_at=datetime.now(timezone.utc),
        )
        await service._store_market_overview(cache_key, overview)
        return overview

    monkeypatch.setattr(service, "_build_and_store_market_overview", fake_build_and_store)

    first, second = await asyncio.gather(
        service.get_market_overview(refresh=True),
        service.get_market_overview(refresh=True),
    )

    assert build_calls == 1
    assert first.updated_at == second.updated_at


@pytest.mark.asyncio
async def test_get_quote_raises_when_mock_disabled_and_upstream_fails(fake_redis, monkeypatch):
    service = md.MarketDataService(fake_redis, enable_mock_fallback=False)
    monkeypatch.setattr(service, "_get_provider", lambda _ticker: RaisingProvider())
    monkeypatch.setattr(service, "_quote_providers", lambda _ticker: [RaisingProvider()])

    with pytest.raises(HTTPException) as exc_info:
        await service.get_quote("AAPL")

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail["error"] == "MARKET_DATA_UNAVAILABLE"


@pytest.mark.asyncio
async def test_get_quote_returns_404_for_unsupported_ticker(fake_redis):
    service = md.MarketDataService(fake_redis, enable_mock_fallback=False)

    with pytest.raises(HTTPException) as exc_info:
        await service.get_quote("ZZZZ")

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["error"] == "TICKER_NOT_FOUND"


@pytest.mark.asyncio
async def test_provider_circuit_breaker_skips_failing_provider_temporarily(fake_redis, monkeypatch):
    service = md.MarketDataService(fake_redis, enable_mock_fallback=False)
    service.provider_failure_threshold = 2
    service.provider_cooldown_seconds = 120

    failing = CountingFailProvider()
    succeeding = CountingSuccessProvider()
    monkeypatch.setattr(service, "_quote_providers", lambda _ticker: [failing, succeeding])

    await service.get_quote("AAPL")
    await service.get_quote("MSFT")
    await service.get_quote("NVDA")

    assert failing.calls == 2
    assert succeeding.calls == 3


class FailingRedis:
    """模拟 Redis 连接失败的场景"""

    async def get(self, key: str) -> bytes | None:
        from redis.exceptions import RedisError
        raise RedisError("Connection refused")

    async def setex(self, key: str, ttl: int, value: str) -> None:
        from redis.exceptions import RedisError
        raise RedisError("Connection refused")


@pytest.mark.asyncio
async def test_redis_failure_does_not_block_quote_fetch(monkeypatch):
    """测试 Redis 异常时不阻塞行情获取（fail-open）"""
    failing_redis = FailingRedis()
    service = md.MarketDataService(failing_redis, enable_mock_fallback=True)
    monkeypatch.setattr(service, "_quote_providers", lambda _ticker: [])

    async def mock_get_quote(ticker: str):
        return QuoteData(
            ticker=ticker,
            price=150.0,
            change_pct=2.5,
            volume=10000,
            market_status="open",
            previous_close=146.34,
        )

    monkeypatch.setattr(service.mock, "get_quote", mock_get_quote)

    # Redis 失败不应该阻塞行情获取
    quote = await service.get_quote("AAPL")

    assert isinstance(quote, QuoteOut)
    assert quote.ticker == "AAPL"
    assert quote.price == Decimal("150.0")
    assert quote.change_pct == 2.5


@pytest.mark.asyncio
async def test_redis_failure_does_not_block_index_fetch(monkeypatch):
    """测试 Redis 异常时不阻塞指数行情获取"""
    failing_redis = FailingRedis()
    service = md.MarketDataService(failing_redis, enable_mock_fallback=True)
    monkeypatch.setattr(service, "_index_providers", lambda _market: [])

    async def mock_get_index(symbol: str):
        return QuoteData(
            ticker=symbol,
            price=4200.0,
            change_pct=1.2,
            volume=0,
            market_status="open",
            name="S&P 500",
        )

    monkeypatch.setattr(service.mock, "get_index", mock_get_index)

    index = await service.get_index("SPX", "us")

    assert isinstance(index, IndexQuoteOut)
    assert index.symbol == "SPX"
    assert index.price == 4200.0


@pytest.mark.asyncio
async def test_redis_safe_wrapper_handles_exceptions():
    """测试 Redis 安全封装函数正确处理异常"""
    from app.services.market_data import _redis_get_safe, _redis_setex_safe

    failing_redis = FailingRedis()

    # get 应该返回 None 而不是抛出
    result = await _redis_get_safe(failing_redis, "test:key")
    assert result is None

    # setex 应该返回 False 而不是抛出
    result = await _redis_setex_safe(failing_redis, "test:key", 60, "value")
    assert result is False

    # None redis 应该安全处理
    result = await _redis_get_safe(None, "test:key")
    assert result is None

    result = await _redis_setex_safe(None, "test:key", 60, "value")
    assert result is False


@pytest.mark.asyncio
async def test_get_stock_history_fetches_and_caches_series(fake_redis, monkeypatch):
    service = md.MarketDataService(fake_redis, enable_mock_fallback=False)
    monkeypatch.setattr(service, "_build_stock_history_from_yahoo", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "_is_stock_history_usable", lambda history, _days: len(history) > 0)

    async def fake_fetch_payload(ticker: str, days: int):
        assert ticker == "0700.HK"
        assert days == 90
        return (
            {
                "data": {
                    "hk00700": {
                        "day": [
                            ["2026-03-28", "100", "101", "102", "99", "1000"],
                            ["2026-03-31", "101", "103", "104", "100", "1500"],
                        ]
                    }
                }
            },
            "hk00700",
        )

    monkeypatch.setattr(service, "_fetch_tencent_stock_history_payload", fake_fetch_payload)

    history = await service.get_stock_history("0700.HK", days=90)

    assert len(history) == 2
    assert history[0].date == "2026-03-28"
    assert history[-1].close == 103.0
    assert history[-1].volume == 1500
    assert ("stock:history:v4:v3:0700.HK:90", 300, fake_redis.store["stock:history:v4:v3:0700.HK:90"].decode("utf-8")) in fake_redis.set_calls
    assert ("stock:history:v4:v3:0700.HK:90:source", 300, "tencent_kline") in fake_redis.set_calls

    async def fail_if_called(_ticker: str, _days: int):
        raise AssertionError("history provider should not be called on cache hit")

    monkeypatch.setattr(service, "_fetch_tencent_stock_history_payload", fail_if_called)
    cached_history = await service.get_stock_history("0700.HK", days=90)
    assert len(cached_history) == 2
    assert cached_history[-1].close == 103.0


def test_is_stock_history_usable_rejects_sparse_multi_year_two_points():
    history = [
        StockHistoryPointOut(
            ts=1306972800000,
            date="2011-06-02",
            open=346.22,
            high=347.84,
            low=344.53,
            close=346.22,
            volume=16780815,
        ),
        StockHistoryPointOut(
            ts=1775088000000,
            date="2026-04-02",
            open=254.2,
            high=256.13,
            low=250.65,
            close=255.92,
            volume=31289369,
        ),
    ]
    assert md.MarketDataService._is_stock_history_usable(history, 180) is False


def test_is_stock_history_usable_accepts_recent_dense_points():
    history: list[StockHistoryPointOut] = []
    base_ts = 1770000000000
    for idx in range(15):
        ts = base_ts + idx * 86_400_000
        history.append(
            StockHistoryPointOut(
                ts=ts,
                date=f"2026-02-{idx + 1:02d}",
                open=100 + idx,
                high=101 + idx,
                low=99 + idx,
                close=100.5 + idx,
                volume=1000 + idx,
            )
        )
    assert md.MarketDataService._is_stock_history_usable(history, 90) is True


@pytest.mark.asyncio
async def test_get_stock_history_rejects_unknown_ticker(fake_redis):
    service = md.MarketDataService(fake_redis, enable_mock_fallback=False)

    with pytest.raises(HTTPException) as exc_info:
        await service.get_stock_history("INVALID999", days=30)

    assert exc_info.value.status_code == 404
    assert exc_info.value.detail["error"] == "TICKER_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_stock_intraday_fallback_builds_flat_series_when_upstream_unavailable(
    fake_redis,
    monkeypatch: pytest.MonkeyPatch,
):
    service = md.MarketDataService(fake_redis, enable_mock_fallback=False)
    monkeypatch.setattr(service.market_calendar, "status", lambda _market: "open")

    async def fake_yahoo_payload(*, symbol: str, interval: str, range_: str):
        raise RuntimeError("429")

    async def fake_get_quote(ticker: str):
        return QuoteOut(
            ticker=ticker,
            price=Decimal("123.45"),
            change_pct=0,
            volume=100,
            market_status="closed",
        )

    monkeypatch.setattr(service, "_fetch_yahoo_chart_payload", fake_yahoo_payload)
    monkeypatch.setattr(service, "_build_intraday_points_from_nasdaq", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "get_quote", fake_get_quote)

    intraday = await service.get_stock_intraday("AAPL", span="1d", interval="5m", refresh=True)

    assert intraday.ticker == "AAPL"
    assert intraday.span == "1d"
    assert intraday.interval == "5m"
    assert len(intraday.points) >= 200
    assert all(point.close == 123.45 for point in intraday.points[:10])
    assert intraday.points[-1].ts > intraday.points[0].ts


@pytest.mark.asyncio
async def test_get_stock_intraday_uses_history_records_when_market_closed_and_no_last_good(
    fake_redis,
    monkeypatch: pytest.MonkeyPatch,
):
    service = md.MarketDataService(fake_redis, enable_mock_fallback=False)
    monkeypatch.setattr(service.market_calendar, "status", lambda _market: "closed")

    async def fake_yahoo_payload(*, symbol: str, interval: str, range_: str):
        raise RuntimeError("429")

    async def fake_get_stock_history(
        ticker: str,
        *,
        days: int = 30,
        refresh: bool = False,
    ):
        assert ticker == "AAPL"
        return [
            StockHistoryPointOut(
                ts=1775088000000,
                date="2026-04-02",
                open=254.2,
                high=256.13,
                low=250.65,
                close=255.92,
                volume=31289369,
            ),
            StockHistoryPointOut(
                ts=1775174400000,
                date="2026-04-03",
                open=255.0,
                high=257.0,
                low=254.5,
                close=256.4,
                volume=30100000,
            ),
        ]

    monkeypatch.setattr(service, "_fetch_yahoo_chart_payload", fake_yahoo_payload)
    monkeypatch.setattr(service, "_build_intraday_points_from_nasdaq", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "get_stock_history", fake_get_stock_history)

    intraday = await service.get_stock_intraday("AAPL", span="1d", interval="5m", refresh=True)
    assert len(intraday.points) >= 200
    close_values = {point.close for point in intraday.points}
    assert len(close_values) >= 2


@pytest.mark.asyncio
async def test_get_stock_history_uses_nasdaq_for_us_when_yahoo_unusable(
    fake_redis,
    monkeypatch: pytest.MonkeyPatch,
):
    service = md.MarketDataService(fake_redis, enable_mock_fallback=False)

    monkeypatch.setattr(service, "_build_stock_history_from_yahoo", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "_build_stock_history_from_stooq", AsyncMock(return_value=[]))

    nasdaq_series: list[StockHistoryPointOut] = []
    base_ts = 1770000000000
    for idx in range(30):
        ts = base_ts + idx * 86_400_000
        nasdaq_series.append(
            StockHistoryPointOut(
                ts=ts,
                date=f"2026-02-{idx + 1:02d}",
                open=200 + idx,
                high=201 + idx,
                low=199 + idx,
                close=200.5 + idx,
                volume=100000 + idx,
            )
        )
    monkeypatch.setattr(service, "_build_stock_history_from_nasdaq", AsyncMock(return_value=nasdaq_series))

    history, source = await service._build_stock_history("AAPL", 90)
    assert source == "nasdaq_historical"
    assert len(history) == len(nasdaq_series)
    assert history[-1].close == nasdaq_series[-1].close


@pytest.mark.asyncio
async def test_get_stock_intraday_uses_nasdaq_chart_when_yahoo_failed(
    fake_redis,
    monkeypatch: pytest.MonkeyPatch,
):
    service = md.MarketDataService(fake_redis, enable_mock_fallback=False)
    monkeypatch.setattr(service.market_calendar, "status", lambda _market: "open")

    async def fake_yahoo_payload(*, symbol: str, interval: str, range_: str):
        raise RuntimeError("429")

    now = 1775200000000
    nasdaq_points = [
        StockIntradayPointOut(
            ts=now + idx * 300000,
            time="",
            open=250 + idx * 0.1,
            high=250 + idx * 0.1,
            low=250 + idx * 0.1,
            close=250 + idx * 0.1,
            volume=None,
        )
        for idx in range(20)
    ]

    monkeypatch.setattr(service, "_fetch_yahoo_chart_payload", fake_yahoo_payload)
    monkeypatch.setattr(service, "_build_intraday_points_from_nasdaq", AsyncMock(return_value=nasdaq_points))

    intraday = await service.get_stock_intraday("AAPL", span="1d", interval="5m", refresh=True)
    assert intraday.source == "nasdaq_chart"
    assert len(intraday.points) == len(nasdaq_points)
    assert intraday.points[0].close != intraday.points[-1].close


@pytest.mark.asyncio
async def test_get_stock_listing_date_fallbacks_to_oldest_history_date(
    fake_redis,
    monkeypatch: pytest.MonkeyPatch,
):
    service = md.MarketDataService(fake_redis, enable_mock_fallback=False)

    async def fake_yahoo_payload(*, symbol: str, interval: str, range_: str):
        raise RuntimeError("listing upstream failed")

    async def fake_get_stock_history(
        ticker: str,
        *,
        days: int = 365,
        refresh: bool = False,
    ):
        assert ticker == "AAPL"
        assert days == 365
        return [
            StockHistoryPointOut(
                ts=1306972800000,
                date="2011-06-02",
                open=346.22,
                high=347.84,
                low=344.53,
                close=346.22,
                volume=16780815,
            ),
            StockHistoryPointOut(
                ts=1775088000000,
                date="2026-04-02",
                open=254.2,
                high=256.13,
                low=250.65,
                close=255.92,
                volume=31289369,
            ),
        ]

    monkeypatch.setattr(service, "_fetch_yahoo_chart_payload", fake_yahoo_payload)
    monkeypatch.setattr(service, "get_stock_history", fake_get_stock_history)

    listed_at = await service.get_stock_listing_date("AAPL", refresh=True)
    assert listed_at == "2011-06-02"


@pytest.mark.asyncio
async def test_get_stock_intraday_uses_last_good_when_market_closed(
    fake_redis,
    monkeypatch: pytest.MonkeyPatch,
):
    service = md.MarketDataService(fake_redis, enable_mock_fallback=False)
    monkeypatch.setattr(service.market_calendar, "status", lambda _market: "closed")

    last_good = {
        "ticker": "AAPL",
        "interval": "5m",
        "span": "1d",
        "points": [
            {
                "ts": 1775200800000,
                "time": "2026-04-03T07:20:00+00:00",
                "open": 255.1,
                "high": 256.0,
                "low": 254.9,
                "close": 255.92,
                "volume": 123456,
            },
            {
                "ts": 1775201100000,
                "time": "2026-04-03T07:25:00+00:00",
                "open": 255.92,
                "high": 256.05,
                "low": 255.8,
                "close": 255.88,
                "volume": 100000,
            },
            {
                "ts": 1775201400000,
                "time": "2026-04-03T07:30:00+00:00",
                "open": 255.88,
                "high": 255.95,
                "low": 255.7,
                "close": 255.8,
                "volume": 90000,
            },
            {
                "ts": 1775201700000,
                "time": "2026-04-03T07:35:00+00:00",
                "open": 255.8,
                "high": 255.9,
                "low": 255.75,
                "close": 255.82,
                "volume": 85000,
            },
        ],
        "updated_at": "2026-04-03T07:35:00+00:00",
    }
    last_good_key = (
        f"stock:intraday:last-good:{md.STOCK_INTRADAY_CACHE_VERSION}:{md.MARKET_CACHE_VERSION}:"
        "AAPL:1d:5m"
    )
    fake_redis.store[last_good_key] = json.dumps(last_good).encode("utf-8")

    async def fake_yahoo_payload(*, symbol: str, interval: str, range_: str):
        raise RuntimeError("429")

    monkeypatch.setattr(service, "_fetch_yahoo_chart_payload", fake_yahoo_payload)

    intraday = await service.get_stock_intraday("AAPL", span="1d", interval="5m", refresh=False)
    assert intraday.points[0].close == 255.92
    assert intraday.points[-1].close == 255.82
    assert len(intraday.points) == 4
