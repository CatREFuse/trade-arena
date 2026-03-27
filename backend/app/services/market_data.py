from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Awaitable, Callable, Literal

from fastapi import HTTPException
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import settings
from app.schemas import (
    IndexQuoteOut,
    MarketBoardItemOut,
    MarketBoardSnapshotOut,
    MarketOverviewOut,
    MarketSummaryOut,
    QuoteOut,
)
from app.services.market_providers import AkshareProvider, MockProvider, SinaProvider, TencentProvider, YahooProvider

logger = logging.getLogger(__name__)


async def _redis_get_safe(redis: Redis | None, key: str) -> bytes | None:
    """安全地获取 Redis 值，失败时返回 None 并记录 warning"""
    if redis is None:
        return None
    try:
        return await redis.get(key)
    except RedisError as e:
        logger.warning(f"Redis get failed for key={key}: {e}")
        return None
    except Exception as e:
        logger.warning(f"Redis get unexpected error for key={key}: {e}")
        return None


async def _redis_setex_safe(
    redis: Redis | None, key: str, ttl: int, value: str | bytes
) -> bool:
    """安全地设置 Redis 值，失败时返回 False 并记录 warning"""
    if redis is None:
        return False
    try:
        await redis.setex(key, ttl, value)
        return True
    except RedisError as e:
        logger.warning(f"Redis setex failed for key={key}: {e}")
        return False
    except Exception as e:
        logger.warning(f"Redis setex unexpected error for key={key}: {e}")
        return False

CACHE_TTL = 60  # 个股行情缓存60秒
INDEX_CACHE_TTL = 300  # 大盘指数缓存5分钟
BOARD_CACHE_TTL = 120  # 市场看盘榜单缓存2分钟，兼顾新鲜度和负载
OVERVIEW_CACHE_TTL = 120  # 市场总览缓存2分钟，和看盘榜单保持一致
BOARD_FETCH_CHUNK_SIZE = 24  # 大榜单分批抓取，避免单次 upstream 请求过大
MARKET_CACHE_VERSION = "v3"

MARKET_BOARD = {
    "us": [
        {"ticker": "AAPL", "name": "Apple"},
        {"ticker": "MSFT", "name": "Microsoft"},
        {"ticker": "NVDA", "name": "NVIDIA"},
        {"ticker": "AMZN", "name": "Amazon"},
        {"ticker": "GOOGL", "name": "Alphabet"},
        {"ticker": "META", "name": "Meta"},
        {"ticker": "TSLA", "name": "Tesla"},
        {"ticker": "AMD", "name": "AMD"},
        {"ticker": "NFLX", "name": "Netflix"},
        {"ticker": "PLTR", "name": "Palantir"},
        {"ticker": "BRK.B", "name": "Berkshire Hathaway"},
        {"ticker": "JPM", "name": "JPMorgan"},
        {"ticker": "V", "name": "Visa"},
        {"ticker": "MA", "name": "Mastercard"},
        {"ticker": "XOM", "name": "Exxon Mobil"},
        {"ticker": "CVX", "name": "Chevron"},
        {"ticker": "LLY", "name": "Eli Lilly"},
        {"ticker": "UNH", "name": "UnitedHealth"},
        {"ticker": "PG", "name": "Procter & Gamble"},
        {"ticker": "KO", "name": "Coca-Cola"},
        {"ticker": "PEP", "name": "PepsiCo"},
        {"ticker": "CSCO", "name": "Cisco"},
        {"ticker": "ORCL", "name": "Oracle"},
        {"ticker": "CRM", "name": "Salesforce"},
        {"ticker": "ADBE", "name": "Adobe"},
        {"ticker": "INTU", "name": "Intuit"},
        {"ticker": "QCOM", "name": "Qualcomm"},
        {"ticker": "AVGO", "name": "Broadcom"},
        {"ticker": "MU", "name": "Micron"},
        {"ticker": "ASML", "name": "ASML"},
        {"ticker": "AMAT", "name": "Applied Materials"},
        {"ticker": "LRCX", "name": "Lam Research"},
        {"ticker": "TSM", "name": "Taiwan Semi"},
        {"ticker": "BABA", "name": "Alibaba"},
        {"ticker": "AMGN", "name": "Amgen"},
        {"ticker": "PFE", "name": "Pfizer"},
        {"ticker": "MRK", "name": "Merck"},
        {"ticker": "ABBV", "name": "AbbVie"},
        {"ticker": "TMO", "name": "Thermo Fisher"},
        {"ticker": "DHR", "name": "Danaher"},
        {"ticker": "COST", "name": "Costco"},
        {"ticker": "WMT", "name": "Walmart"},
        {"ticker": "HD", "name": "Home Depot"},
        {"ticker": "LOW", "name": "Lowe's"},
        {"ticker": "NKE", "name": "Nike"},
        {"ticker": "MCD", "name": "McDonald's"},
        {"ticker": "SBUX", "name": "Starbucks"},
        {"ticker": "BKNG", "name": "Booking"},
        {"ticker": "UBER", "name": "Uber"},
        {"ticker": "SHOP", "name": "Shopify"},
        {"ticker": "SNOW", "name": "Snowflake"},
        {"ticker": "PANW", "name": "Palo Alto"},
        {"ticker": "CRWD", "name": "CrowdStrike"},
        {"ticker": "NOW", "name": "ServiceNow"},
        {"ticker": "GE", "name": "GE Aerospace"},
        {"ticker": "CAT", "name": "Caterpillar"},
        {"ticker": "BA", "name": "Boeing"},
        {"ticker": "RTX", "name": "RTX"},
        {"ticker": "T", "name": "AT&T"},
        {"ticker": "VZ", "name": "Verizon"},
        {"ticker": "CMCSA", "name": "Comcast"},
        {"ticker": "DIS", "name": "Disney"},
    ],
    "cn": [
        {"ticker": "600519.SH", "name": "贵州茅台"},
        {"ticker": "000858.SZ", "name": "五粮液"},
        {"ticker": "601318.SH", "name": "中国平安"},
        {"ticker": "300750.SZ", "name": "宁德时代"},
        {"ticker": "002594.SZ", "name": "比亚迪"},
        {"ticker": "600036.SH", "name": "招商银行"},
        {"ticker": "000001.SZ", "name": "平安银行"},
        {"ticker": "601899.SH", "name": "紫金矿业"},
        {"ticker": "000333.SZ", "name": "美的集团"},
        {"ticker": "603288.SH", "name": "海天味业"},
        {"ticker": "601012.SH", "name": "隆基绿能"},
        {"ticker": "688981.SH", "name": "中芯国际"},
        {"ticker": "688041.SH", "name": "海光信息"},
        {"ticker": "601166.SH", "name": "兴业银行"},
        {"ticker": "600887.SH", "name": "伊利股份"},
        {"ticker": "600276.SH", "name": "恒瑞医药"},
        {"ticker": "000568.SZ", "name": "泸州老窖"},
        {"ticker": "000651.SZ", "name": "格力电器"},
        {"ticker": "601888.SH", "name": "中国中免"},
        {"ticker": "002475.SZ", "name": "立讯精密"},
        {"ticker": "002230.SZ", "name": "科大讯飞"},
        {"ticker": "002371.SZ", "name": "北方华创"},
        {"ticker": "300059.SZ", "name": "东方财富"},
        {"ticker": "300760.SZ", "name": "迈瑞医疗"},
        {"ticker": "300124.SZ", "name": "汇川技术"},
        {"ticker": "603259.SH", "name": "药明康德"},
        {"ticker": "688012.SH", "name": "中微公司"},
        {"ticker": "688111.SH", "name": "金山办公"},
        {"ticker": "601398.SH", "name": "工商银行"},
        {"ticker": "601939.SH", "name": "建设银行"},
        {"ticker": "600036.SH", "name": "招商银行"},
        {"ticker": "601288.SH", "name": "农业银行"},
        {"ticker": "601328.SH", "name": "交通银行"},
        {"ticker": "601601.SH", "name": "中国太保"},
        {"ticker": "601628.SH", "name": "中国人寿"},
        {"ticker": "601336.SH", "name": "新华保险"},
        {"ticker": "600809.SH", "name": "山西汾酒"},
        {"ticker": "000001.SZ", "name": "平安银行"},
        {"ticker": "000002.SZ", "name": "万科A"},
        {"ticker": "000725.SZ", "name": "京东方A"},
        {"ticker": "000963.SZ", "name": "华东医药"},
        {"ticker": "002594.SZ", "name": "比亚迪"},
        {"ticker": "002384.SZ", "name": "东山精密"},
        {"ticker": "002352.SZ", "name": "顺丰控股"},
        {"ticker": "002460.SZ", "name": "赣锋锂业"},
        {"ticker": "002415.SZ", "name": "海康威视"},
        {"ticker": "300750.SZ", "name": "宁德时代"},
        {"ticker": "300274.SZ", "name": "阳光电源"},
        {"ticker": "300308.SZ", "name": "中际旭创"},
        {"ticker": "300502.SZ", "name": "新易盛"},
    ],
    "hk": [
        {"ticker": "0700.HK", "name": "腾讯控股"},
        {"ticker": "9988.HK", "name": "阿里巴巴-SW"},
        {"ticker": "3690.HK", "name": "美团-W"},
        {"ticker": "1299.HK", "name": "友邦保险"},
        {"ticker": "1211.HK", "name": "比亚迪股份"},
        {"ticker": "1810.HK", "name": "小米集团-W"},
        {"ticker": "2318.HK", "name": "中国平安"},
        {"ticker": "0941.HK", "name": "中国移动"},
        {"ticker": "0388.HK", "name": "香港交易所"},
        {"ticker": "0005.HK", "name": "汇丰控股"},
        {"ticker": "9618.HK", "name": "京东集团-SW"},
        {"ticker": "9999.HK", "name": "网易-S"},
        {"ticker": "9888.HK", "name": "百度集团-SW"},
        {"ticker": "1024.HK", "name": "快手-W"},
    ],
}

SUPPORTED_TICKERS = {
    entry["ticker"]
    for market_entries in MARKET_BOARD.values()
    for entry in market_entries
}


ProviderDataType = Literal["quote", "index"]
ProviderMiddleware = Callable[["ProviderCallContext", Callable[[], Awaitable[object]]], Awaitable[object]]


@dataclass
class ProviderCallContext:
    data_type: ProviderDataType
    market: str
    key: str
    provider_name: str
    had_error: bool = False


@dataclass(frozen=True)
class ProviderEntry:
    name: str
    provider: object


class ProviderRegistry:
    """按市场和数据类型维护 provider 链，支持按优先级插拔。"""

    def __init__(self):
        self._chains: dict[tuple[ProviderDataType, str], list[ProviderEntry]] = {}

    def register(
        self,
        *,
        data_type: ProviderDataType,
        market: str,
        provider: object,
        name: str | None = None,
        priority: int | None = None,
    ) -> None:
        key = (data_type, market.lower())
        chain = self._chains.setdefault(key, [])
        entry_name = name or provider.__class__.__name__
        chain[:] = [entry for entry in chain if entry.name != entry_name]
        entry = ProviderEntry(name=entry_name, provider=provider)

        if priority is None or priority >= len(chain):
            chain.append(entry)
            return

        chain.insert(max(priority, 0), entry)

    def chain(self, data_type: ProviderDataType, market: str) -> list[ProviderEntry]:
        return list(self._chains.get((data_type, market.lower()), []))


class MarketDataService:
    def __init__(
        self,
        redis: Redis,
        akshare: AkshareProvider | None = None,
        yahoo: YahooProvider | None = None,
        tencent: TencentProvider | None = None,
        sina: SinaProvider | None = None,
        mock: MockProvider | None = None,
        enable_mock_fallback: bool | None = None,
    ):
        self.redis = redis
        self.akshare = akshare or AkshareProvider()
        self.tencent = tencent or TencentProvider()
        self.sina = sina or SinaProvider()
        self.yahoo = yahoo or YahooProvider()
        self.mock = mock or MockProvider()
        self.enable_mock_fallback = (
            settings.market_enable_mock_fallback
            if enable_mock_fallback is None
            else enable_mock_fallback
        )
        self.provider_failure_threshold = max(settings.market_provider_failure_threshold, 1)
        self.provider_cooldown_seconds = max(settings.market_provider_cooldown_seconds, 1)
        self.provider_registry = ProviderRegistry()
        self._provider_health: dict[tuple[ProviderDataType, str, str], dict[str, float | int]] = {}
        self._provider_middlewares: list[ProviderMiddleware] = [
            self._provider_health_middleware,
            self._provider_error_middleware,
        ]
        self._register_default_providers()

    def provider_chain_snapshot(self) -> dict[str, list[str]]:
        keys = [
            ("quote", "us"),
            ("quote", "cn"),
            ("quote", "hk"),
            ("index", "us"),
            ("index", "cn"),
            ("index", "hk"),
        ]
        return {
            f"{data_type}:{market}": [
                entry.name for entry in self.provider_registry.chain(data_type, market)
            ]
            for data_type, market in keys
        }

    def provider_health_snapshot(self) -> list[dict]:
        now = asyncio.get_running_loop().time()
        snapshot: list[dict] = []
        for (data_type, market, provider_name), state in sorted(
            self._provider_health.items(),
            key=lambda item: item[0],
        ):
            disabled_until = float(state.get("disabled_until", 0) or 0)
            remaining = max(0.0, disabled_until - now)
            snapshot.append(
                {
                    "data_type": data_type,
                    "market": market,
                    "provider": provider_name,
                    "failures": int(state.get("failures", 0) or 0),
                    "circuit_open": remaining > 0,
                    "cooldown_remaining_seconds": round(remaining, 2),
                }
            )
        return snapshot

    def _register_default_providers(self) -> None:
        # quote chain
        self.register_provider("quote", "cn", self.akshare, priority=0)
        self.register_provider("quote", "cn", self.tencent, priority=1)
        self.register_provider("quote", "cn", self.sina, priority=2)

        self.register_provider("quote", "hk", self.akshare, priority=0)
        self.register_provider("quote", "hk", self.tencent, priority=1)
        self.register_provider("quote", "hk", self.yahoo, priority=2)

        self.register_provider("quote", "us", self.yahoo, priority=0)

        # index chain
        self.register_provider("index", "cn", self.akshare, priority=0)
        self.register_provider("index", "cn", self.tencent, priority=1)
        self.register_provider("index", "cn", self.sina, priority=2)

        self.register_provider("index", "hk", self.akshare, priority=0)
        self.register_provider("index", "hk", self.tencent, priority=1)
        self.register_provider("index", "hk", self.yahoo, priority=2)

        self.register_provider("index", "us", self.yahoo, priority=0)

    def register_provider(
        self,
        data_type: ProviderDataType,
        market: str,
        provider: object,
        *,
        priority: int | None = None,
        name: str | None = None,
    ) -> None:
        self.provider_registry.register(
            data_type=data_type,
            market=market,
            provider=provider,
            name=name,
            priority=priority,
        )

    def add_provider_middleware(self, middleware: ProviderMiddleware) -> None:
        self._provider_middlewares.append(middleware)

    async def get_quote(self, ticker: str) -> QuoteOut:
        """获取个股行情，带缓存"""
        ticker = ticker.upper()

        if not self._is_supported_ticker(ticker):
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "TICKER_NOT_FOUND",
                    "message": f"未找到行情标的：{ticker}",
                    "detail": {"ticker": ticker},
                },
            )

        cache_key = f"quote:{ticker}"

        # 尝试从缓存获取
        cached = await _redis_get_safe(self.redis, cache_key)
        if cached:
            try:
                raw = cached.decode() if isinstance(cached, bytes) else cached
                data = json.loads(raw)
                return QuoteOut(ticker=ticker, **data)
            except Exception as e:
                logger.warning(f"Cache parse error: {e}")

        quote = await self._fetch_quote_with_fallback(ticker)
        if not quote:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "MARKET_DATA_UNAVAILABLE",
                    "message": f"行情源不可用：{ticker}",
                    "detail": {"ticker": ticker},
                },
            )

        # 构建响应数据（移除 ticker 避免重复）
        data = {
            "price": quote.price,
            "change_pct": quote.change_pct,
            "name": quote.name,
            "volume": quote.volume,
            "market_status": quote.market_status,
        }

        # 写入缓存（Redis 失败不影响返回结果）
        await _redis_setex_safe(self.redis, cache_key, CACHE_TTL, json.dumps(data))
        return QuoteOut(ticker=ticker, **data)

    async def get_index(self, symbol: str, market: str) -> IndexQuoteOut:
        """获取大盘指数行情"""
        symbol = symbol.upper()
        market = market.lower()
        cache_key = f"index:{market}:{symbol}"

        # 尝试从缓存获取
        cached = await _redis_get_safe(self.redis, cache_key)
        if cached:
            try:
                raw = cached.decode() if isinstance(cached, bytes) else cached
                data = json.loads(raw)
                return IndexQuoteOut(**data)
            except Exception as e:
                logger.warning(f"Index cache parse error: {e}")

        name_map = {
            "SPX": "S&P 500",
            "NDX": "NASDAQ",
            "DJI": "道琼斯",
            "SH": "上证指数",
            "SZ": "深成指",
            "CY": "创业板指",
            "HSI": "恒生指数",
            "HSCEI": "国企指数",
        }
        quote = await self._fetch_index_with_fallback(symbol, market)
        if not quote:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "MARKET_DATA_UNAVAILABLE",
                    "message": f"指数行情源不可用：{symbol}",
                    "detail": {"symbol": symbol, "market": market},
                },
            )
        data = {
            "symbol": symbol,
            "name": name_map.get(symbol, symbol),
            "price": quote.price,
            "change_pct": quote.change_pct,
            "market": market,
        }

        # 写入缓存（Redis 失败不影响返回结果）
        await _redis_setex_safe(self.redis, cache_key, INDEX_CACHE_TTL, json.dumps(data))
        return IndexQuoteOut(**data)

    async def get_all_indices(self, refresh: bool = False) -> list[IndexQuoteOut]:
        """获取所有大盘指数"""
        cache_key = f"market:indices:all:{MARKET_CACHE_VERSION}"
        if not refresh:
            cached_list = await self._load_cached_list(cache_key, IndexQuoteOut)
            if cached_list is not None:
                return cached_list

        indices = [
            ("SPX", "us"), ("NDX", "us"), ("DJI", "us"),
            ("SH", "cn"), ("SZ", "cn"), ("CY", "cn"),
            ("HSI", "hk"), ("HSCEI", "hk"),
        ]
        name_map = {
            "SPX": "S&P 500",
            "NDX": "NASDAQ",
            "DJI": "道琼斯",
            "SH": "上证指数",
            "SZ": "深成指",
            "CY": "创业板指",
            "HSI": "恒生指数",
            "HSCEI": "国企指数",
        }
        cached, missing = await self._get_cached_indices(indices)

        fetched = await self._fetch_missing_indices(missing)
        quotes: list[IndexQuoteOut] = []
        for symbol, market in indices:
            data = cached.get((symbol, market)) or fetched.get((symbol, market))
            if not data:
                logger.error(f"Failed to get index {symbol}")
                continue
            quotes.append(
                IndexQuoteOut(
                    symbol=symbol,
                    name=name_map.get(symbol, symbol),
                    price=data.price,
                    change_pct=data.change_pct,
                    market=market,
                )
            )
        await self._cache_model_list(cache_key, INDEX_CACHE_TTL, quotes)
        return quotes

    async def get_market_board(self, market: str, refresh: bool = False) -> MarketBoardSnapshotOut:
        cache_key = f"market:board:{MARKET_CACHE_VERSION}:{market}"
        if not refresh:
            cached_snapshot = await self._load_cached_model_safe(cache_key, MarketBoardSnapshotOut)
            if cached_snapshot is not None:
                return cached_snapshot

        entries = MARKET_BOARD.get(market, [])
        if not entries:
            return MarketBoardSnapshotOut(items=[], updated_at=datetime.now(timezone.utc))

        tickers = [entry["ticker"] for entry in entries]
        quotes = await self._get_quotes_batch(tickers)
        board: list[MarketBoardItemOut] = []
        for entry in entries:
            quote = quotes.get(entry["ticker"])
            if not quote and self.enable_mock_fallback:
                quote = await self.mock.get_quote(entry["ticker"])
            if not quote:
                continue
            board.append(
                MarketBoardItemOut(
                    ticker=entry["ticker"],
                    name=quote.name or entry["name"],
                    market=market,
                    price=quote.price,
                    change_pct=quote.change_pct,
                    volume=quote.volume,
                    market_status=quote.market_status,
                )
            )
        snapshot = MarketBoardSnapshotOut(
            items=board,
            updated_at=datetime.now(timezone.utc),
        )
        await _redis_setex_safe(
            self.redis,
            cache_key,
            BOARD_CACHE_TTL,
            json.dumps(snapshot.model_dump(mode="json")),
        )
        return snapshot

    async def get_market_overview(self, refresh: bool = False) -> MarketOverviewOut:
        cache_key = f"market:overview:{MARKET_CACHE_VERSION}"
        if not refresh:
            cached = await _redis_get_safe(self.redis, cache_key)
        else:
            cached = None
        if cached:
            try:
                raw = cached.decode() if isinstance(cached, bytes) else cached
                return MarketOverviewOut(**json.loads(raw))
            except Exception as e:
                logger.warning(f"Market overview cache parse error: {e}")

        indices, us_board, cn_board, hk_board = await asyncio.gather(
            self.get_all_indices(refresh=refresh),
            self.get_market_board("us", refresh=refresh),
            self.get_market_board("cn", refresh=refresh),
            self.get_market_board("hk", refresh=refresh),
        )
        overview = MarketOverviewOut(
            indices=indices,
            boards={"us": us_board.items, "cn": cn_board.items, "hk": hk_board.items},
            markets=[
                self._build_market_summary("us", "美股", us_board.items),
                self._build_market_summary("cn", "A 股", cn_board.items),
                self._build_market_summary("hk", "港股", hk_board.items),
            ],
            updated_at=max(us_board.updated_at, cn_board.updated_at, hk_board.updated_at),
        )
        await _redis_setex_safe(
            self.redis,
            cache_key,
            OVERVIEW_CACHE_TTL,
            json.dumps(overview.model_dump(mode="json")),
        )
        return overview

    def _get_provider(self, ticker: str):
        providers = self._quote_providers(ticker)
        return providers[0] if providers else self.yahoo

    async def _get_quotes_batch(self, tickers: list[str]):
        cached, missing = await self._get_cached_quotes(tickers)
        fetched: dict[str, object] = {}

        for chunk_start in range(0, len(missing), BOARD_FETCH_CHUNK_SIZE):
            chunk = missing[chunk_start : chunk_start + BOARD_FETCH_CHUNK_SIZE]
            market_groups: dict[str, list[str]] = {"us": [], "cn": [], "hk": []}
            for ticker in chunk:
                market_groups[self._ticker_market(ticker)].append(ticker)

            batch_tasks = [
                self._fetch_quotes_by_market_chain(market, market_tickers)
                for market, market_tickers in market_groups.items()
                if market_tickers
            ]
            for market_quotes in await asyncio.gather(*batch_tasks):
                fetched.update({ticker: quote for ticker, quote in market_quotes.items() if quote})

            for ticker in chunk:
                quote = fetched.get(ticker)
                if not quote and self.enable_mock_fallback:
                    quote = await self.mock.get_quote(ticker)
                    fetched[ticker] = quote
                if quote:
                    await self._cache_quote_data(ticker, quote)

        return {**cached, **fetched}

    async def _get_cached_quotes(self, tickers: list[str]):
        cached: dict[str, object] = {}
        missing: list[str] = []
        for ticker in tickers:
            cache_key = f"quote:{ticker}"
            raw = await _redis_get_safe(self.redis, cache_key)
            if not raw:
                missing.append(ticker)
                continue
            try:
                payload = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
                cached[ticker] = QuoteOut(ticker=ticker, **payload)
            except Exception as e:
                logger.warning(f"Batch quote cache parse error for {ticker}: {e}")
                missing.append(ticker)
        return cached, missing

    async def _get_cached_indices(self, indices: list[tuple[str, str]]):
        cached: dict[tuple[str, str], IndexQuoteOut] = {}
        missing: list[tuple[str, str]] = []
        for symbol, market in indices:
            cache_key = f"index:{market}:{symbol}"
            raw = await _redis_get_safe(self.redis, cache_key)
            if not raw:
                missing.append((symbol, market))
                continue
            try:
                payload = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
                cached[(symbol, market)] = IndexQuoteOut(**payload)
            except Exception as e:
                logger.warning(f"Batch index cache parse error for {symbol}: {e}")
                missing.append((symbol, market))
        return cached, missing

    async def _fetch_missing_indices(self, missing: list[tuple[str, str]]):
        fetched: dict[tuple[str, str], IndexQuoteOut] = {}
        market_groups: dict[str, list[str]] = {"us": [], "cn": [], "hk": []}
        for symbol, market in missing:
            market_groups[market].append(symbol)

        market_quotes: dict[str, dict[str, object]] = {"us": {}, "cn": {}, "hk": {}}
        batch_tasks = [
            self._fetch_indices_market_result(market, symbols)
            for market, symbols in market_groups.items()
            if symbols
        ]
        for market, result in await asyncio.gather(*batch_tasks):
            market_quotes[market] = result

        name_map = {
            "SPX": "S&P 500",
            "NDX": "NASDAQ",
            "DJI": "道琼斯",
            "SH": "上证指数",
            "SZ": "深成指",
            "CY": "创业板指",
            "HSI": "恒生指数",
            "HSCEI": "国企指数",
        }

        for symbol, market in missing:
            quote = market_quotes.get(market, {}).get(symbol)

            if not quote and self.enable_mock_fallback:
                quote = await self.mock.get_index(symbol)
            if not quote:
                continue
            data = {
                "symbol": symbol,
                "name": name_map.get(symbol, symbol),
                "price": quote.price,
                "change_pct": quote.change_pct,
                "market": market,
            }
            await _redis_setex_safe(self.redis, f"index:{market}:{symbol}", INDEX_CACHE_TTL, json.dumps(data))
            fetched[(symbol, market)] = IndexQuoteOut(**data)
        return fetched

    async def _fetch_quote_with_fallback(self, ticker: str):
        market = self._ticker_market(ticker)
        for provider in self._quote_providers(ticker):
            quote = await self._execute_provider_call(
                data_type="quote",
                market=market,
                key=ticker,
                provider_name=provider.__class__.__name__,
                call=lambda provider=provider: provider.get_quote(ticker),
            )
            if quote:
                return quote
        if self.enable_mock_fallback:
            logger.warning("No upstream quote for %s, falling back to mock", ticker)
            return await self.mock.get_quote(ticker)
        return None

    async def _fetch_index_with_fallback(self, symbol: str, market: str):
        for provider in self._index_providers(market):
            quote = await self._execute_provider_call(
                data_type="index",
                market=market,
                key=symbol,
                provider_name=provider.__class__.__name__,
                call=lambda provider=provider: provider.get_index(symbol),
            )
            if quote:
                return quote
        if self.enable_mock_fallback:
            logger.warning("No upstream index for %s/%s, falling back to mock", market, symbol)
            return await self.mock.get_index(symbol)
        return None

    def _quote_providers(self, ticker: str) -> list:
        market = self._ticker_market(ticker)
        return [entry.provider for entry in self.provider_registry.chain("quote", market)]

    def _index_providers(self, market: str) -> list:
        return [entry.provider for entry in self.provider_registry.chain("index", market)]

    async def _fetch_quotes_by_market_chain(self, market: str, tickers: list[str]) -> dict[str, object]:
        remaining = set(tickers)
        resolved: dict[str, object] = {}
        providers = [entry.provider for entry in self.provider_registry.chain("quote", market)]
        for provider in providers:
            if not remaining:
                break
            request = [ticker for ticker in tickers if ticker in remaining]
            payload = await self._execute_provider_call(
                data_type="quote",
                market=market,
                key=f"batch:{len(request)}",
                provider_name=provider.__class__.__name__,
                call=lambda provider=provider, request=request: provider.get_quotes_batch(request),
            )
            if not isinstance(payload, dict):
                continue
            for ticker in request:
                quote = payload.get(ticker)
                if quote:
                    resolved[ticker] = quote
                    remaining.discard(ticker)
        for ticker in tickers:
            resolved.setdefault(ticker, None)
        return resolved

    async def _fetch_indices_by_market_chain(self, market: str, symbols: list[str]) -> dict[str, object]:
        remaining = set(symbols)
        resolved: dict[str, object] = {}
        for provider in self._index_providers(market):
            if not remaining:
                break
            request = [symbol for symbol in symbols if symbol in remaining]
            payload = await self._execute_provider_call(
                data_type="index",
                market=market,
                key=f"batch:{len(request)}",
                provider_name=provider.__class__.__name__,
                call=lambda provider=provider, request=request: provider.get_indices_batch(request),
            )
            if not isinstance(payload, dict):
                continue
            for symbol in request:
                quote = payload.get(symbol)
                if quote:
                    resolved[symbol] = quote
                    remaining.discard(symbol)
        for symbol in symbols:
            resolved.setdefault(symbol, None)
        return resolved

    async def _fetch_indices_market_result(self, market: str, symbols: list[str]) -> tuple[str, dict[str, object]]:
        return market, await self._fetch_indices_by_market_chain(market, symbols)

    async def _execute_provider_call(
        self,
        *,
        data_type: ProviderDataType,
        market: str,
        key: str,
        provider_name: str,
        call: Callable[[], Awaitable[object]],
    ) -> object:
        ctx = ProviderCallContext(
            data_type=data_type,
            market=market,
            key=key,
            provider_name=provider_name,
        )
        return await self._run_provider_middlewares(ctx, call)

    async def _run_provider_middlewares(
        self,
        ctx: ProviderCallContext,
        call: Callable[[], Awaitable[object]],
    ) -> object:
        next_call = call
        for middleware in reversed(self._provider_middlewares):
            current_next = next_call

            async def wrapped(
                middleware_fn=middleware,
                chained=current_next,
            ):
                return await middleware_fn(ctx, chained)

            next_call = wrapped
        return await next_call()

    async def _provider_health_middleware(
        self,
        ctx: ProviderCallContext,
        call_next: Callable[[], Awaitable[object]],
    ) -> object:
        if self._provider_is_temporarily_disabled(ctx):
            logger.warning(
                "Provider %s skipped for %s/%s (%s): circuit open",
                ctx.provider_name,
                ctx.data_type,
                ctx.market,
                ctx.key,
            )
            return None

        result = await call_next()
        if ctx.had_error:
            self._record_provider_failure(ctx)
            return None

        if result is not None:
            self._record_provider_success(ctx)
        return result

    async def _provider_error_middleware(
        self,
        ctx: ProviderCallContext,
        call_next: Callable[[], Awaitable[object]],
    ) -> object:
        try:
            return await call_next()
        except Exception as e:
            ctx.had_error = True
            logger.warning(
                "Provider %s failed for %s/%s (%s): %s",
                ctx.provider_name,
                ctx.data_type,
                ctx.market,
                ctx.key,
                e,
            )
            return None

    def _provider_state_key(self, ctx: ProviderCallContext) -> tuple[ProviderDataType, str, str]:
        return (ctx.data_type, ctx.market, ctx.provider_name)

    def _provider_state(self, ctx: ProviderCallContext) -> dict[str, float | int]:
        key = self._provider_state_key(ctx)
        return self._provider_health.setdefault(
            key,
            {"failures": 0, "disabled_until": 0.0},
        )

    def _provider_is_temporarily_disabled(self, ctx: ProviderCallContext) -> bool:
        state = self._provider_state(ctx)
        disabled_until = float(state["disabled_until"])
        if disabled_until <= 0:
            return False

        now = asyncio.get_running_loop().time()
        if now < disabled_until:
            return True

        state["disabled_until"] = 0.0
        state["failures"] = 0
        return False

    def _record_provider_failure(self, ctx: ProviderCallContext) -> None:
        state = self._provider_state(ctx)
        failures = int(state["failures"]) + 1
        state["failures"] = failures
        if failures < self.provider_failure_threshold:
            return

        now = asyncio.get_running_loop().time()
        state["disabled_until"] = now + self.provider_cooldown_seconds
        logger.warning(
            "Provider %s disabled for %ss after %s consecutive failures (%s/%s)",
            ctx.provider_name,
            self.provider_cooldown_seconds,
            failures,
            ctx.data_type,
            ctx.market,
        )

    def _record_provider_success(self, ctx: ProviderCallContext) -> None:
        state = self._provider_state(ctx)
        if int(state["failures"]) == 0 and float(state["disabled_until"]) <= 0:
            return
        state["failures"] = 0
        state["disabled_until"] = 0.0

    def _ticker_market(self, ticker: str) -> str:
        if self._is_cn_ticker(ticker):
            return "cn"
        if self._is_hk_ticker(ticker):
            return "hk"
        return "us"

    @staticmethod
    def _is_supported_ticker(ticker: str) -> bool:
        return ticker in SUPPORTED_TICKERS

    @staticmethod
    def _is_cn_ticker(ticker: str) -> bool:
        return ticker.endswith(".SH") or ticker.endswith(".SZ")

    @staticmethod
    def _is_hk_ticker(ticker: str) -> bool:
        return ticker.endswith(".HK")

    async def _cache_quote_data(self, ticker: str, quote) -> None:
        data = {
            "price": quote.price,
            "change_pct": quote.change_pct,
            "name": quote.name,
            "volume": quote.volume,
            "market_status": quote.market_status,
        }
        await _redis_setex_safe(self.redis, f"quote:{ticker}", CACHE_TTL, json.dumps(data))

    async def _load_cached_list(self, cache_key: str, model_cls):
        raw = await _redis_get_safe(self.redis, cache_key)
        if not raw:
            return None
        try:
            payload = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
            return [model_cls(**item) for item in payload]
        except Exception as e:
            logger.warning(f"Aggregate cache parse error for {cache_key}: {e}")
            return None

    async def _load_cached_model_safe(self, cache_key: str, model_cls):
        """安全加载缓存模型（Redis 故障时返回 None）"""
        raw = await _redis_get_safe(self.redis, cache_key)
        if not raw:
            return None
        try:
            payload = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
            return model_cls(**payload)
        except Exception as e:
            logger.warning(f"Model cache parse error for {cache_key}: {e}")
            return None



    async def _cache_model_list(self, cache_key: str, ttl: int, models: list) -> None:
        payload = [model.model_dump(mode="json") for model in models]
        await _redis_setex_safe(self.redis, cache_key, ttl, json.dumps(payload))

    def _build_market_summary(
        self,
        market: str,
        name: str,
        board: list[MarketBoardItemOut],
    ) -> MarketSummaryOut:
        sorted_board = sorted(board, key=lambda item: item.change_pct, reverse=True)
        up_count = sum(1 for item in board if item.change_pct > 0)
        down_count = sum(1 for item in board if item.change_pct < 0)
        flat_count = len(board) - up_count - down_count
        avg_change_pct = round(
            sum(item.change_pct for item in board) / len(board),
            2,
        ) if board else 0.0
        return MarketSummaryOut(
            market=market,
            name=name,
            stock_count=len(board),
            up_count=up_count,
            down_count=down_count,
            flat_count=flat_count,
            avg_change_pct=avg_change_pct,
            leader=sorted_board[0] if sorted_board else None,
            laggard=sorted_board[-1] if sorted_board else None,
        )
