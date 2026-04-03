from __future__ import annotations

import asyncio
import csv
import json
import logging
import re
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
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
    MarketTrendOut,
    MarketTrendPointOut,
    QuoteOut,
    StockHistoryPointOut,
    StockIntradayOut,
    StockIntradayPointOut,
)
from app.services.market_calendar import MarketCalendarService
from app.services.market_providers import (
    FAST_HTTP_TIMEOUT,
    AkshareProvider,
    MockProvider,
    SinaProvider,
    TencentProvider,
    YahooProvider,
    _limited_get,
)

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
TREND_CACHE_TTL = 300  # 市场代表指数曲线缓存5分钟
STOCK_HISTORY_CACHE_TTL = 300  # 个股历史行情缓存5分钟
STOCK_INTRADAY_CACHE_TTL = 60  # 分时曲线缓存60秒
STOCK_INTRADAY_LAST_GOOD_TTL = 86400 * 7  # 分时最后有效记录保留7天
STOCK_LISTING_CACHE_TTL = 86400  # 上市时间缓存24小时
BOARD_FETCH_CHUNK_SIZE = 24  # 大榜单分批抓取，避免单次 upstream 请求过大
MARKET_CACHE_VERSION = "v3"
TREND_CACHE_VERSION = "v2"
STOCK_HISTORY_CACHE_VERSION = "v3"
STOCK_INTRADAY_CACHE_VERSION = "v3"
STOCK_LISTING_CACHE_VERSION = "v2"
SHADOW_CACHE_TTL_SECONDS = 300

REPRESENTATIVE_INDEX = {
    "us": {
        "symbol": "us.INX",
        "name": "标普500",
        "kline_symbol": "usINX",
        "kline_response_symbol": "us.INX",
    },
    "cn": {
        "symbol": "sh000001",
        "name": "上证指数",
        "kline_symbol": "sh000001",
        "kline_response_symbol": "sh000001",
    },
    "hk": {
        "symbol": "hkHSI",
        "name": "恒生指数",
        "kline_symbol": "hkHSI",
        "kline_response_symbol": "hkHSI",
    },
}

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


def _pick_cn_ticker(code: str) -> str | None:
    sh = f"{code}.SH"
    sz = f"{code}.SZ"
    if sh in SUPPORTED_TICKERS and sz in SUPPORTED_TICKERS:
        # CN codes are typically partitioned by prefix; keep deterministic fallback.
        if code.startswith(("0", "2", "3")):
            return sz
        if code.startswith(("6", "9")):
            return sh
        return sh
    if sh in SUPPORTED_TICKERS:
        return sh
    if sz in SUPPORTED_TICKERS:
        return sz
    return None


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
        self.market_calendar = MarketCalendarService()
        self.provider_registry = ProviderRegistry()
        self._provider_health: dict[tuple[ProviderDataType, str, str], dict[str, float | int]] = {}
        self._provider_middlewares: list[ProviderMiddleware] = [
            self._provider_health_middleware,
            self._provider_error_middleware,
        ]
        self._shadow_cache: dict[str, tuple[float, object]] = {}
        self._background_refresh_tasks: dict[str, asyncio.Task[None]] = {}
        self._singleflight_tasks: dict[str, asyncio.Task[object]] = {}
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
        original_ticker = ticker.upper()
        ticker = self._normalize_supported_ticker(original_ticker)
        if ticker is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "TICKER_NOT_FOUND",
                    "message": f"未找到行情标的：{original_ticker}",
                    "detail": {"ticker": original_ticker},
                },
            )

        market = self._ticker_market(ticker)

        cache_key = f"quote:{ticker}"
        market_status = self._market_status(market)

        # 尝试从缓存获取
        cached = await _redis_get_safe(self.redis, cache_key)
        if cached:
            try:
                raw = cached.decode() if isinstance(cached, bytes) else cached
                data = json.loads(raw)
                data["market_status"] = market_status
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
            "market_status": market_status,
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

    async def get_quotes_batch(self, tickers: list[str]) -> dict[str, QuoteOut | None]:
        normalized: list[str] = []
        seen: set[str] = set()
        for ticker in tickers:
            normalized_ticker = ticker.upper()
            if normalized_ticker in seen:
                continue
            seen.add(normalized_ticker)
            if self._is_supported_ticker(normalized_ticker):
                normalized.append(normalized_ticker)

        status_cache = self._resolve_market_statuses(self._ticker_market(ticker) for ticker in normalized)
        raw_quotes = await self._get_quotes_batch(normalized, status_cache=status_cache)
        return {
            ticker: self._coerce_quote_out(ticker, raw_quotes.get(ticker), status_cache=status_cache)
            for ticker in normalized
        }

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
        return await self._run_singleflight(
            cache_key,
            lambda: self._build_and_store_market_board(cache_key, market),
        )

    async def get_market_overview(self, refresh: bool = False) -> MarketOverviewOut:
        cache_key = f"market:overview:{MARKET_CACHE_VERSION}"
        if not refresh:
            cached_overview = await self._load_cached_model_safe(cache_key, MarketOverviewOut)
            if cached_overview is not None:
                self._set_shadow_cache(cache_key, cached_overview)
                return cached_overview

            shadow_overview = self._get_shadow_cache(cache_key, MarketOverviewOut)
            if shadow_overview is not None:
                self._ensure_background_refresh(cache_key, self._refresh_market_overview_cache)
                return shadow_overview

            in_flight = self._background_refresh_tasks.get(cache_key)
            if in_flight and not in_flight.done():
                with suppress(asyncio.TimeoutError):
                    await asyncio.wait_for(asyncio.shield(in_flight), timeout=0.35)
                cached_overview = await self._load_cached_model_safe(cache_key, MarketOverviewOut)
                if cached_overview is not None:
                    self._set_shadow_cache(cache_key, cached_overview)
                    return cached_overview

        return await self._run_singleflight(
            cache_key,
            lambda: self._build_and_store_market_overview(cache_key, refresh=refresh),
        )

    async def get_market_trend(self, market: str, points: int = 30, refresh: bool = False) -> MarketTrendOut:
        market = market.lower()
        if market not in REPRESENTATIVE_INDEX:
            raise HTTPException(
                status_code=400,
                detail={"error": "INVALID_MARKET", "message": "market 仅支持 us/cn/hk"},
            )

        points = max(8, min(points, 120))
        cache_key = f"market:trend:{TREND_CACHE_VERSION}:{MARKET_CACHE_VERSION}:{market}:{points}"
        if not refresh:
            cached_trend = await self._load_cached_model_safe(cache_key, MarketTrendOut)
            if cached_trend is not None:
                return cached_trend

        trend = await self._build_market_trend(market, points)
        await self._cache_model(cache_key, TREND_CACHE_TTL, trend)
        return trend

    async def get_stock_history(
        self,
        ticker: str,
        *,
        days: int = 90,
        refresh: bool = False,
    ) -> list[StockHistoryPointOut]:
        original_ticker = ticker.upper()
        ticker = self._normalize_supported_ticker(original_ticker)
        if ticker is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "TICKER_NOT_FOUND",
                    "message": f"未找到行情标的：{original_ticker}",
                    "detail": {"ticker": original_ticker},
                },
            )

        days = max(30, min(days, 365))
        cache_key = f"stock:history:{STOCK_HISTORY_CACHE_VERSION}:{MARKET_CACHE_VERSION}:{ticker}:{days}"
        if not refresh:
            cached_history = await self._load_cached_list(cache_key, StockHistoryPointOut)
            if cached_history is not None:
                return cached_history

        history = await self._build_stock_history(ticker, days)
        await self._cache_model_list(cache_key, STOCK_HISTORY_CACHE_TTL, history)
        return history

    async def get_stock_intraday(
        self,
        ticker: str,
        *,
        span: str = "1d",
        interval: str = "5m",
        refresh: bool = False,
    ) -> StockIntradayOut:
        original_ticker = ticker.upper()
        ticker = self._normalize_supported_ticker(original_ticker)
        if ticker is None:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "TICKER_NOT_FOUND",
                    "message": f"未找到行情标的：{original_ticker}",
                    "detail": {"ticker": original_ticker},
                },
            )

        normalized_span = span.lower()
        if normalized_span not in {"1d", "5d"}:
            normalized_span = "1d"
        normalized_interval = interval.lower()
        if normalized_interval != "5m":
            normalized_interval = "5m"

        cache_key = (
            f"stock:intraday:{STOCK_INTRADAY_CACHE_VERSION}:{MARKET_CACHE_VERSION}:"
            f"{ticker}:{normalized_span}:{normalized_interval}"
        )
        last_good_cache_key = (
            f"stock:intraday:last-good:{STOCK_INTRADAY_CACHE_VERSION}:{MARKET_CACHE_VERSION}:"
            f"{ticker}:{normalized_span}:{normalized_interval}"
        )
        if not refresh:
            cached = await self._load_cached_model_safe(cache_key, StockIntradayOut)
            if cached is not None:
                return cached

        market = self._ticker_market(ticker)
        market_status = self._market_status(market)

        if not refresh and market_status != "open":
            last_good = await self._load_cached_model_safe(last_good_cache_key, StockIntradayOut)
            if last_good is not None and self._is_intraday_points_usable(
                last_good.points,
                span=normalized_span,
                interval=normalized_interval,
            ):
                await self._cache_model(cache_key, STOCK_INTRADAY_CACHE_TTL, last_good)
                return last_good

        points, is_usable_record = await self._build_stock_intraday_points(
            ticker=ticker,
            span=normalized_span,
            interval=normalized_interval,
            market_status=market_status,
        )
        result = StockIntradayOut(
            ticker=ticker,
            interval=normalized_interval,
            span=normalized_span,
            points=points,
            updated_at=datetime.now(timezone.utc),
        )
        await self._cache_model(cache_key, STOCK_INTRADAY_CACHE_TTL, result)
        if is_usable_record:
            await self._cache_model(last_good_cache_key, STOCK_INTRADAY_LAST_GOOD_TTL, result)
        return result

    async def get_stock_listing_date(
        self,
        ticker: str,
        *,
        refresh: bool = False,
    ) -> str | None:
        original_ticker = ticker.upper()
        ticker = self._normalize_supported_ticker(original_ticker)
        if ticker is None:
            return None

        cache_key = (
            f"stock:listing:{STOCK_LISTING_CACHE_VERSION}:{MARKET_CACHE_VERSION}:{ticker}"
        )
        if not refresh:
            raw = await _redis_get_safe(self.redis, cache_key)
            if raw:
                value = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
                if value != "null":
                    return value
                return None

        listed_at: str | None = None
        try:
            symbol = self._to_yahoo_chart_symbol(ticker)
            payload = await self._fetch_yahoo_chart_payload(
                symbol=symbol,
                interval="1mo",
                range_="max",
            )
            timestamps = (
                ((payload.get("chart") or {}).get("result") or [{}])[0].get("timestamp")
                or []
            )
            if timestamps:
                listed_at = datetime.fromtimestamp(int(timestamps[0]), tz=timezone.utc).date().isoformat()
        except Exception as exc:
            logger.warning("Fetch listing date failed for %s: %s", ticker, exc)

        if listed_at is None:
            with suppress(Exception):
                history = await self.get_stock_history(ticker, days=365, refresh=False)
                if history:
                    oldest = min(history, key=lambda item: item.ts)
                    listed_at = oldest.date

        with suppress(Exception):
            await _redis_setex_safe(
                self.redis,
                cache_key,
                STOCK_LISTING_CACHE_TTL,
                listed_at if listed_at is not None else "null",
            )
        return listed_at

    async def _build_market_trend(self, market: str, points: int) -> MarketTrendOut:
        representative = REPRESENTATIVE_INDEX[market]
        symbol = representative["symbol"]
        kline_symbol = representative["kline_symbol"]
        response_symbol = representative["kline_response_symbol"]
        params = {
            "param": f"{kline_symbol},day,,,240",
        }

        response = await _limited_get(
            "tencent",
            "https://web.ifzq.gtimg.cn/appstock/app/kline/kline",
            client_name="tencent-trend",
            timeout=FAST_HTTP_TIMEOUT,
            params=params,
            headers=TencentProvider.HEADERS,
        )
        response.raise_for_status()
        payload = response.json()

        series = self._parse_tencent_kline_series(payload, response_symbol, points)
        if not series:
            raise HTTPException(
                status_code=503,
                detail={"error": "TREND_DATA_UNAVAILABLE", "message": "代表指数曲线暂不可用"},
            )

        return MarketTrendOut(
            market=market,
            symbol=symbol,
            name=representative["name"],
            points=series,
            updated_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _parse_tencent_kline_series(
        payload: dict, symbol: str, points: int
    ) -> list[MarketTrendPointOut]:
        raw_data = (payload.get("data") or {}).get(symbol) or {}
        day_rows = raw_data.get("day") or []
        if not day_rows:
            return []
        parsed: list[MarketTrendPointOut] = []
        for row in day_rows:
            if len(row) < 3:
                continue
            date_str = str(row[0]).strip()
            close = row[2]
            if close in (None, ""):
                continue
            ts = MarketDataService._parse_kline_ts(date_str)
            if ts is None:
                continue
            parsed.append(
                MarketTrendPointOut(
                    ts=ts,
                    close=round(float(close), 4),
                )
            )
        latest_price = MarketDataService._extract_tencent_latest_price(raw_data, symbol)
        if parsed and latest_price is not None:
            parsed[-1] = MarketTrendPointOut(
                ts=int(datetime.now(timezone.utc).timestamp() * 1000),
                close=round(latest_price, 4),
            )
        if len(parsed) > points:
            return parsed[-points:]
        return parsed

    async def _build_stock_history(self, ticker: str, days: int) -> list[StockHistoryPointOut]:
        yahoo_history = await self._build_stock_history_from_yahoo(ticker, days)
        if self._is_stock_history_usable(yahoo_history, days):
            return yahoo_history[-days:]

        payload, response_symbol = await self._fetch_tencent_stock_history_payload(ticker, days)
        if payload is not None and response_symbol is not None:
            series = self._parse_tencent_stock_history_series(payload, response_symbol, days)
            if self._is_stock_history_usable(series, days):
                return series

        stooq_history = await self._build_stock_history_from_stooq(ticker, days)
        if self._is_stock_history_usable(stooq_history, days):
            return stooq_history[-days:]

        fallback_history = await self._build_stock_history_from_quote_fallback(ticker, days)
        if fallback_history:
            return fallback_history

        raise HTTPException(
            status_code=503,
            detail={
                "error": "HISTORY_DATA_UNAVAILABLE",
                "message": f"历史行情暂不可用：{ticker}",
                "detail": {"ticker": ticker},
            },
        )

    async def _build_stock_history_from_yahoo(
        self,
        ticker: str,
        days: int,
    ) -> list[StockHistoryPointOut]:
        symbol = self._to_yahoo_chart_symbol(ticker)
        range_ = self._yahoo_history_range(days)
        try:
            payload = await self._fetch_yahoo_chart_payload(
                symbol=symbol,
                interval="1d",
                range_=range_,
            )
            points = self._parse_yahoo_chart_points(payload)
            history: list[StockHistoryPointOut] = []
            for point in points:
                history.append(
                    StockHistoryPointOut(
                        ts=point.ts,
                        date=datetime.fromtimestamp(point.ts / 1000, tz=timezone.utc).date().isoformat(),
                        open=point.open,
                        high=point.high,
                        low=point.low,
                        close=point.close,
                        volume=point.volume or 0,
                    )
                )
            if len(history) > days:
                return history[-days:]
            return history
        except Exception as exc:
            logger.warning("Fetch yahoo stock history failed for %s: %s", ticker, exc)
            return []

    async def _build_stock_history_from_stooq(
        self,
        ticker: str,
        days: int,
    ) -> list[StockHistoryPointOut]:
        symbol = self._to_stooq_history_symbol(ticker)
        if not symbol:
            return []

        today = datetime.now(timezone.utc).date()
        start = today - timedelta(days=max(days * 3, 180))
        params = {
            "s": symbol,
            "i": "d",
            "d1": start.strftime("%Y%m%d"),
            "d2": today.strftime("%Y%m%d"),
        }

        try:
            response = await _limited_get(
                "stooq",
                "https://stooq.com/q/d/l/",
                client_name="stooq-stock-history",
                timeout=FAST_HTTP_TIMEOUT,
                params=params,
                headers=YahooProvider.HEADERS,
            )
            response.raise_for_status()
        except Exception as exc:
            logger.warning("Fetch stooq stock history failed for %s: %s", ticker, exc)
            return []

        lines = [line.strip() for line in response.text.splitlines() if line.strip()]
        if len(lines) < 2:
            return []

        parsed: list[StockHistoryPointOut] = []
        for row in csv.DictReader(lines):
            date_raw = str(row.get("Date") or "").strip()
            if not date_raw:
                continue
            ts = self._parse_kline_ts(date_raw)
            if ts is None:
                continue
            open_ = self._safe_float(row.get("Open"))
            high = self._safe_float(row.get("High"))
            low = self._safe_float(row.get("Low"))
            close = self._safe_float(row.get("Close"))
            if None in {open_, high, low, close}:
                continue
            volume = self._safe_int(row.get("Volume")) or 0
            parsed.append(
                StockHistoryPointOut(
                    ts=ts,
                    date=date_raw,
                    open=open_,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                )
            )

        if len(parsed) > days:
            return parsed[-days:]
        return parsed

    async def _build_stock_history_from_quote_fallback(
        self,
        ticker: str,
        days: int,
    ) -> list[StockHistoryPointOut]:
        with suppress(Exception):
            quote = await self.get_quote(ticker, refresh=False)
            price = float(quote.price)
            volume = int(quote.volume or 0)
            today = datetime.now(timezone.utc).date()
            points: list[StockHistoryPointOut] = []
            for offset in range(days):
                day = today - timedelta(days=days - offset - 1)
                ts = int(datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc).timestamp() * 1000)
                points.append(
                    StockHistoryPointOut(
                        ts=ts,
                        date=day.isoformat(),
                        open=price,
                        high=price,
                        low=price,
                        close=price,
                        volume=volume,
                    )
                )
            return points
        return []

    async def _fetch_tencent_stock_history_payload(
        self,
        ticker: str,
        days: int,
    ) -> tuple[dict | None, str | None]:
        fetch_points = max(120, min(days * 2, 480))
        for candidate in self._tencent_kline_candidates(ticker):
            params = {"param": f"{candidate},day,,,{fetch_points}"}
            try:
                response = await _limited_get(
                    "tencent",
                    "https://web.ifzq.gtimg.cn/appstock/app/kline/kline",
                    client_name="tencent-stock-history",
                    timeout=FAST_HTTP_TIMEOUT,
                    params=params,
                    headers=TencentProvider.HEADERS,
                )
                response.raise_for_status()
                payload = response.json()
            except Exception as exc:
                logger.warning("Fetch stock history failed for %s via %s: %s", ticker, candidate, exc)
                continue

            raw_data = payload.get("data") or {}
            if candidate not in raw_data:
                continue
            if raw_data.get(candidate, {}).get("day"):
                return payload, candidate
        return None, None

    @classmethod
    def _tencent_kline_candidates(cls, ticker: str) -> list[str]:
        normalized = ticker.upper()
        if cls._is_cn_ticker(normalized):
            code, market = normalized.split(".")
            return [f"{market.lower()}{code}"]
        if cls._is_hk_ticker(normalized):
            code = normalized.removesuffix(".HK")
            return [f"hk{code.zfill(5)}", f"hk{code.zfill(4)}"]

        us_base = normalized
        return [
            f"us{us_base}",
            f"us{us_base.replace('.', '-')}",
            f"us{us_base.replace('.', '')}",
        ]

    @classmethod
    def _parse_tencent_stock_history_series(
        cls,
        payload: dict,
        symbol: str,
        days: int,
    ) -> list[StockHistoryPointOut]:
        raw_data = (payload.get("data") or {}).get(symbol) or {}
        day_rows = raw_data.get("day") or []
        if not day_rows:
            return []

        parsed: list[StockHistoryPointOut] = []
        for row in day_rows:
            if len(row) < 6:
                continue
            date_str = str(row[0]).strip()
            ts = cls._parse_kline_ts(date_str)
            if ts is None:
                continue
            try:
                open_price = round(float(row[1]), 4)
                close_price = round(float(row[2]), 4)
                high_price = round(float(row[3]), 4)
                low_price = round(float(row[4]), 4)
                volume = int(float(row[5]))
            except (TypeError, ValueError):
                continue
            parsed.append(
                StockHistoryPointOut(
                    ts=ts,
                    date=date_str,
                    open=open_price,
                    high=high_price,
                    low=low_price,
                    close=close_price,
                    volume=volume,
                )
            )

        if len(parsed) > days:
            return parsed[-days:]
        return parsed

    @staticmethod
    def _is_stock_history_usable(history: list[StockHistoryPointOut], days: int) -> bool:
        if not history:
            return False
        del days
        return len(history) >= 2

    async def _build_stock_intraday_points(
        self,
        *,
        ticker: str,
        span: str,
        interval: str,
        market_status: str,
    ) -> tuple[list[StockIntradayPointOut], bool]:
        symbol = self._to_yahoo_chart_symbol(ticker)
        try:
            payload = await self._fetch_yahoo_chart_payload(
                symbol=symbol,
                interval=interval,
                range_=span,
            )
            points = self._parse_yahoo_chart_points(payload)
            if self._is_intraday_points_usable(points, span=span, interval=interval):
                return points, True
            if points:
                logger.warning(
                    "Yahoo intraday points are insufficient for %s (span=%s interval=%s, count=%s), use fallback",
                    ticker,
                    span,
                    interval,
                    len(points),
                )
        except Exception as exc:
            logger.warning("Fetch stock intraday failed for %s: %s", ticker, exc)

        if market_status != "open":
            history_fallback = await self._build_intraday_history_fallback(
                ticker=ticker,
                span=span,
                interval=interval,
            )
            if history_fallback:
                return history_fallback, False

        # 最后回退：在目标 span/interval 内构造平线，避免“跨年两点”破图。
        fallback = await self._build_intraday_flat_fallback(
            ticker=ticker,
            span=span,
            interval=interval,
        )
        return fallback, False

    async def _build_intraday_history_fallback(
        self,
        *,
        ticker: str,
        span: str,
        interval: str,
    ) -> list[StockIntradayPointOut]:
        with suppress(Exception):
            history = await self.get_stock_history(ticker, days=30, refresh=False)
            if not history:
                return []
            source = history[-min(len(history), 120):]
            closes = [float(point.close) for point in source if float(point.close) > 0]
            if not closes:
                return []

            point_count = self._span_point_count(span)
            step_ms = self._interval_to_ms(interval) or 5 * 60 * 1000
            end_ts_seconds = int(datetime.now(timezone.utc).timestamp())
            step_seconds = step_ms // 1000
            end_ts_seconds = (end_ts_seconds // step_seconds) * step_seconds
            start_ts = end_ts_seconds * 1000 - (point_count - 1) * step_ms

            points: list[StockIntradayPointOut] = []
            for idx in range(point_count):
                ratio = idx / max(point_count - 1, 1)
                source_idx = round(ratio * (len(closes) - 1))
                value = round(closes[source_idx], 4)
                ts = start_ts + idx * step_ms
                points.append(
                    StockIntradayPointOut(
                        ts=ts,
                        time=datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat(),
                        open=value,
                        high=value,
                        low=value,
                        close=value,
                        volume=None,
                    )
                )
            return points
        return []

    async def _fetch_yahoo_chart_payload(
        self,
        *,
        symbol: str,
        interval: str,
        range_: str,
    ) -> dict:
        response = await _limited_get(
            "yahoo",
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            client_name="yahoo-chart",
            timeout=FAST_HTTP_TIMEOUT,
            headers=YahooProvider.HEADERS,
            params={
                "interval": interval,
                "range": range_,
                "includePrePost": "false",
                "events": "div,splits",
            },
        )
        response.raise_for_status()
        return response.json()

    @classmethod
    def _parse_yahoo_chart_points(cls, payload: dict) -> list[StockIntradayPointOut]:
        chart = payload.get("chart") or {}
        result_list = chart.get("result") or []
        if not result_list:
            return []
        result = result_list[0] or {}
        timestamps = result.get("timestamp") or []
        quote = (((result.get("indicators") or {}).get("quote") or [{}])[0] or {})
        opens = quote.get("open") or []
        highs = quote.get("high") or []
        lows = quote.get("low") or []
        closes = quote.get("close") or []
        volumes = quote.get("volume") or []

        points: list[StockIntradayPointOut] = []
        for idx, ts in enumerate(timestamps):
            close_price = cls._value_at(closes, idx)
            if close_price is None:
                continue
            open_price = cls._value_at(opens, idx) or close_price
            high_price = cls._value_at(highs, idx) or max(open_price, close_price)
            low_price = cls._value_at(lows, idx) or min(open_price, close_price)
            volume_raw = cls._value_at(volumes, idx)
            points.append(
                StockIntradayPointOut(
                    ts=int(ts) * 1000,
                    time=datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat(),
                    open=round(open_price, 4),
                    high=round(high_price, 4),
                    low=round(low_price, 4),
                    close=round(close_price, 4),
                    volume=int(volume_raw) if volume_raw is not None else None,
                )
            )
        return points

    @staticmethod
    def _value_at(items: list, index: int) -> float | None:
        if index >= len(items):
            return None
        value = items[index]
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _is_intraday_points_usable(
        cls,
        points: list[StockIntradayPointOut],
        *,
        span: str,
        interval: str,
    ) -> bool:
        if len(points) < 4:
            return False
        step_ms = cls._interval_to_ms(interval)
        if step_ms <= 0:
            return False

        first_ts = points[0].ts
        last_ts = points[-1].ts
        if last_ts <= first_ts:
            return False

        max_span_ms = 48 * 60 * 60 * 1000 if span == "1d" else 8 * 24 * 60 * 60 * 1000
        if last_ts - first_ts > max_span_ms:
            return False

        gaps = [max(0, points[idx + 1].ts - points[idx].ts) for idx in range(len(points) - 1)]
        avg_gap = sum(gaps) / len(gaps) if gaps else 0
        # 允许夜盘/休市造成的间隔，但均值不应远超目标粒度。
        return avg_gap <= step_ms * 18

    async def _build_intraday_flat_fallback(
        self,
        *,
        ticker: str,
        span: str,
        interval: str,
    ) -> list[StockIntradayPointOut]:
        step_ms = self._interval_to_ms(interval)
        if step_ms <= 0:
            step_ms = 5 * 60 * 1000

        point_count = self._span_point_count(span)

        end_ts_seconds = int(datetime.now(timezone.utc).timestamp())
        step_seconds = step_ms // 1000
        end_ts_seconds = (end_ts_seconds // step_seconds) * step_seconds
        start_ts = end_ts_seconds * 1000 - (point_count - 1) * step_ms
        seed_price = await self._resolve_intraday_seed_price(ticker)
        value = round(seed_price, 4)

        points: list[StockIntradayPointOut] = []
        for idx in range(point_count):
            ts = start_ts + idx * step_ms
            points.append(
                StockIntradayPointOut(
                    ts=ts,
                    time=datetime.fromtimestamp(ts / 1000, tz=timezone.utc).isoformat(),
                    open=value,
                    high=value,
                    low=value,
                    close=value,
                    volume=None,
                )
            )
        return points

    async def _resolve_intraday_seed_price(self, ticker: str) -> float:
        with suppress(Exception):
            quote = await self.get_quote(ticker)
            price = float(quote.price)
            if price > 0:
                return price

        with suppress(Exception):
            history = await self.get_stock_history(ticker, days=30, refresh=False)
            if history:
                close = float(history[-1].close)
                if close > 0:
                    return close
        return 1.0

    @staticmethod
    def _interval_to_ms(interval: str) -> int:
        text = interval.strip().lower()
        match = re.fullmatch(r"(\d+)([mhd])", text)
        if match is None:
            return 0
        value = int(match.group(1))
        unit = match.group(2)
        factor = {"m": 60_000, "h": 3_600_000, "d": 86_400_000}.get(unit, 0)
        return value * factor

    @staticmethod
    def _span_point_count(span: str) -> int:
        span_points = {"1d": 24 * 60 // 5, "5d": 5 * 24 * 60 // 5}
        return max(24, span_points.get(span, 24 * 60 // 5))

    @classmethod
    def _to_yahoo_chart_symbol(cls, ticker: str) -> str:
        normalized = ticker.upper()
        if cls._is_cn_ticker(normalized):
            code, market = normalized.split(".")
            if market == "SH":
                return f"{code}.SS"
            return f"{code}.{market}"
        if cls._is_hk_ticker(normalized):
            return normalized
        return normalized.replace(".", "-")

    @classmethod
    def _to_stooq_history_symbol(cls, ticker: str) -> str | None:
        normalized = ticker.upper()
        if cls._is_hk_ticker(normalized):
            return normalized.lower()
        if cls._is_cn_ticker(normalized):
            return normalized.lower()
        base = normalized.replace(".", "-").lower()
        if not base:
            return None
        return f"{base}.us"

    @staticmethod
    def _yahoo_history_range(days: int) -> str:
        if days <= 30:
            return "1mo"
        if days <= 90:
            return "3mo"
        if days <= 180:
            return "6mo"
        if days <= 365:
            return "1y"
        return "2y"

    @staticmethod
    def _safe_float(value) -> float | None:
        try:
            if value in (None, "", "N/D"):
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _safe_int(value) -> int | None:
        try:
            if value in (None, "", "N/D"):
                return None
            return int(float(value))
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_kline_ts(date_str: str) -> int | None:
        for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
                return int(dt.timestamp() * 1000)
            except ValueError:
                continue
        return None

    @staticmethod
    def _extract_tencent_latest_price(raw_data: dict, symbol: str) -> float | None:
        qt_block = raw_data.get("qt") or {}
        quote = qt_block.get(symbol) or []
        if not isinstance(quote, list) or len(quote) < 4:
            return None
        try:
            return float(quote[3])
        except (TypeError, ValueError):
            return None

    def _get_provider(self, ticker: str):
        providers = self._quote_providers(ticker)
        return providers[0] if providers else self.yahoo

    async def _get_quotes_batch(
        self,
        tickers: list[str],
        *,
        status_cache: dict[str, str] | None = None,
    ):
        cached, missing = await self._get_cached_quotes(tickers, status_cache=status_cache)
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

    async def _get_cached_quotes(
        self,
        tickers: list[str],
        *,
        status_cache: dict[str, str] | None = None,
    ):
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
                market = self._ticker_market(ticker)
                payload["market_status"] = self._market_status(market, status_cache)
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

    @classmethod
    def _normalize_supported_ticker(cls, ticker: str) -> str | None:
        normalized = ticker.strip().upper()
        if not normalized:
            return None

        if normalized in SUPPORTED_TICKERS:
            return normalized

        # Allow BRK-B style aliases to map to BRK.B if present.
        if "-" in normalized:
            dotted = normalized.replace("-", ".")
            if dotted in SUPPORTED_TICKERS:
                return dotted

        # sh600519 / sz300750
        prefixed_cn = re.fullmatch(r"(SH|SZ)(\d{6})", normalized)
        if prefixed_cn:
            market, code = prefixed_cn.groups()
            candidate = f"{code}.{market}"
            if candidate in SUPPORTED_TICKERS:
                return candidate
            return None

        # 600519sh / 300750sz
        suffixed_cn = re.fullmatch(r"(\d{6})(SH|SZ)", normalized)
        if suffixed_cn:
            code, market = suffixed_cn.groups()
            candidate = f"{code}.{market}"
            if candidate in SUPPORTED_TICKERS:
                return candidate
            return None

        # Pure CN code: 600519 / 000001 / 300750
        pure_cn = re.fullmatch(r"\d{6}", normalized)
        if pure_cn:
            candidate = _pick_cn_ticker(normalized)
            if candidate:
                return candidate
            return None

        # hk0700 / hk700
        prefixed_hk = re.fullmatch(r"HK(\d{3,5})", normalized)
        if prefixed_hk:
            code = prefixed_hk.group(1).zfill(4)
            candidate = f"{code}.HK"
            if candidate in SUPPORTED_TICKERS:
                return candidate
            return None

        # 0700 / 700 (HK ticker style)
        pure_hk = re.fullmatch(r"\d{3,5}", normalized)
        if pure_hk:
            code = normalized.zfill(4)
            candidate = f"{code}.HK"
            if candidate in SUPPORTED_TICKERS:
                return candidate
            return None

        return None

    @staticmethod
    def _is_cn_ticker(ticker: str) -> bool:
        return ticker.endswith(".SH") or ticker.endswith(".SZ")

    @staticmethod
    def _is_hk_ticker(ticker: str) -> bool:
        return ticker.endswith(".HK")

    async def _cache_quote_data(self, ticker: str, quote) -> None:
        market = self._ticker_market(ticker)
        data = {
            "price": quote.price,
            "change_pct": quote.change_pct,
            "name": quote.name,
            "volume": quote.volume,
            "market_status": self._market_status(market),
        }
        await _redis_setex_safe(self.redis, f"quote:{ticker}", CACHE_TTL, json.dumps(data))

    def _coerce_quote_out(
        self,
        ticker: str,
        quote,
        status_cache: dict[str, str] | None = None,
    ) -> QuoteOut | None:
        if quote is None:
            return None
        if isinstance(quote, QuoteOut):
            return quote

        market = self._ticker_market(ticker)
        return QuoteOut(
            ticker=ticker,
            price=quote.price,
            change_pct=quote.change_pct,
            name=getattr(quote, "name", None),
            volume=getattr(quote, "volume", None),
            market_status=self._market_status(market, status_cache),
        )

    async def _build_and_store_market_board(self, cache_key: str, market: str) -> MarketBoardSnapshotOut:
        entries = MARKET_BOARD.get(market, [])
        if not entries:
            return MarketBoardSnapshotOut(items=[], updated_at=datetime.now(timezone.utc))

        tickers = [entry["ticker"] for entry in entries]
        status_cache = {market: self._market_status(market)}
        quotes = await self._get_quotes_batch(tickers, status_cache=status_cache)
        current_market_status = status_cache[market]
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
                    market_status=current_market_status,
                )
            )
        snapshot = MarketBoardSnapshotOut(items=board, updated_at=datetime.now(timezone.utc))
        await _redis_setex_safe(
            self.redis,
            cache_key,
            BOARD_CACHE_TTL,
            json.dumps(snapshot.model_dump(mode="json")),
        )
        return snapshot

    async def _build_market_overview(self, refresh: bool = False) -> MarketOverviewOut:
        indices, us_board, cn_board, hk_board = await asyncio.gather(
            self.get_all_indices(refresh=refresh),
            self.get_market_board("us", refresh=refresh),
            self.get_market_board("cn", refresh=refresh),
            self.get_market_board("hk", refresh=refresh),
        )
        return MarketOverviewOut(
            indices=indices,
            boards={"us": us_board.items, "cn": cn_board.items, "hk": hk_board.items},
            markets=[
                self._build_market_summary("us", "美股", us_board.items),
                self._build_market_summary("cn", "A 股", cn_board.items),
                self._build_market_summary("hk", "港股", hk_board.items),
            ],
            updated_at=max(us_board.updated_at, cn_board.updated_at, hk_board.updated_at),
        )

    async def _store_market_overview(self, cache_key: str, overview: MarketOverviewOut) -> None:
        await _redis_setex_safe(
            self.redis,
            cache_key,
            OVERVIEW_CACHE_TTL,
            json.dumps(overview.model_dump(mode="json")),
        )
        self._set_shadow_cache(cache_key, overview)

    async def _build_and_store_market_overview(
        self,
        cache_key: str,
        *,
        refresh: bool,
    ) -> MarketOverviewOut:
        overview = await self._build_market_overview(refresh=refresh)
        await self._store_market_overview(cache_key, overview)
        return overview

    async def _refresh_market_overview_cache(self) -> None:
        cache_key = f"market:overview:{MARKET_CACHE_VERSION}"
        overview = await self._build_market_overview(refresh=True)
        await self._store_market_overview(cache_key, overview)

    def _ensure_background_refresh(
        self,
        cache_key: str,
        refresh_factory: Callable[[], Awaitable[None]],
    ) -> None:
        task = self._background_refresh_tasks.get(cache_key)
        if task and not task.done():
            return

        async def runner() -> None:
            try:
                await refresh_factory()
            except Exception as exc:
                logger.warning("Background refresh failed for %s: %s", cache_key, exc)
            finally:
                current = self._background_refresh_tasks.get(cache_key)
                if current is asyncio.current_task():
                    self._background_refresh_tasks.pop(cache_key, None)

        self._background_refresh_tasks[cache_key] = asyncio.create_task(runner())

    async def _run_singleflight(
        self,
        cache_key: str,
        factory: Callable[[], Awaitable[object]],
    ):
        task = self._singleflight_tasks.get(cache_key)
        if task and not task.done():
            return await asyncio.shield(task)

        async def runner():
            try:
                return await factory()
            finally:
                current = self._singleflight_tasks.get(cache_key)
                if current is asyncio.current_task():
                    self._singleflight_tasks.pop(cache_key, None)

        task = asyncio.create_task(runner())
        self._singleflight_tasks[cache_key] = task
        return await asyncio.shield(task)

    def _get_shadow_cache(self, cache_key: str, model_cls):
        cached = self._shadow_cache.get(cache_key)
        if not cached:
            return None

        cached_at, payload = cached
        now = asyncio.get_running_loop().time()
        if now - cached_at > SHADOW_CACHE_TTL_SECONDS:
            self._shadow_cache.pop(cache_key, None)
            return None

        return payload if isinstance(payload, model_cls) else None

    def _set_shadow_cache(self, cache_key: str, payload: object) -> None:
        self._shadow_cache[cache_key] = (asyncio.get_running_loop().time(), payload)

    def _market_status(
        self,
        market: str,
        status_cache: dict[str, str] | None = None,
    ) -> str:
        if status_cache is not None:
            cached_status = status_cache.get(market)
            if cached_status is not None:
                return cached_status

        market_status = self.market_calendar.status(market)
        if status_cache is not None:
            status_cache[market] = market_status
        return market_status

    def _resolve_market_statuses(self, markets) -> dict[str, str]:
        resolved: dict[str, str] = {}
        for market in markets:
            if market not in resolved:
                resolved[market] = self.market_calendar.status(market)
        return resolved

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

    async def _cache_model(self, cache_key: str, ttl: int, model) -> None:
        await _redis_setex_safe(
            self.redis,
            cache_key,
            ttl,
            json.dumps(model.model_dump(mode="json")),
        )

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
