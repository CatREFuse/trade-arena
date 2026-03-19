from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

from redis.asyncio import Redis

from app.schemas import (
    IndexQuoteOut,
    MarketBoardItemOut,
    MarketOverviewOut,
    MarketSummaryOut,
    QuoteOut,
)
from app.services.market_providers import MockProvider, SinaProvider, YahooProvider

logger = logging.getLogger(__name__)

CACHE_TTL = 60  # 个股行情缓存60秒
INDEX_CACHE_TTL = 300  # 大盘指数缓存5分钟
BOARD_CACHE_TTL = 120  # 市场看盘榜单缓存2分钟，兼顾新鲜度和负载
OVERVIEW_CACHE_TTL = 120  # 市场总览缓存2分钟，和看盘榜单保持一致
BOARD_FETCH_CHUNK_SIZE = 24  # 大榜单分批抓取，避免单次 upstream 请求过大
MARKET_CACHE_VERSION = "v2"

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
}


class MarketDataService:
    def __init__(
        self,
        redis: Redis,
        yahoo: YahooProvider | None = None,
        sina: SinaProvider | None = None,
        mock: MockProvider | None = None,
    ):
        self.redis = redis
        self.sina = sina or SinaProvider()
        self.yahoo = yahoo or YahooProvider()
        self.mock = mock or MockProvider()

    async def get_quote(self, ticker: str) -> QuoteOut:
        """获取个股行情，带缓存"""
        ticker = ticker.upper()
        cache_key = f"quote:{ticker}"

        # 尝试从缓存获取
        cached = await self.redis.get(cache_key)
        if cached:
            try:
                raw = cached.decode() if isinstance(cached, bytes) else cached
                data = json.loads(raw)
                return QuoteOut(ticker=ticker, **data)
            except Exception as e:
                logger.warning(f"Cache parse error: {e}")

        provider = self._get_provider(ticker)

        try:
            quote = await provider.get_quote(ticker)
            if not quote:
                # 降级到 mock
                logger.warning(f"Provider returned None for {ticker}, using mock")
                quote = await self.mock.get_quote(ticker)
        except Exception as e:
            logger.error(f"Quote fetch failed for {ticker}: {e}")
            quote = await self.mock.get_quote(ticker)

        # 构建响应数据（移除 ticker 避免重复）
        data = {
            "price": quote.price,
            "change_pct": quote.change_pct,
            "name": quote.name,
            "volume": quote.volume,
            "market_status": quote.market_status,
        }

        # 写入缓存
        await self.redis.setex(cache_key, CACHE_TTL, json.dumps(data))
        return QuoteOut(ticker=ticker, **data)

    async def get_index(self, symbol: str, market: str) -> IndexQuoteOut:
        """获取大盘指数行情"""
        cache_key = f"index:{market}:{symbol}"

        # 尝试从缓存获取
        cached = await self.redis.get(cache_key)
        if cached:
            try:
                raw = cached.decode() if isinstance(cached, bytes) else cached
                data = json.loads(raw)
                return IndexQuoteOut(**data)
            except Exception as e:
                logger.warning(f"Index cache parse error: {e}")

        # 根据市场选择提供商
        if market == "us":
            provider = self.yahoo
            name_map = {"SPX": "S&P 500", "NDX": "NASDAQ", "DJI": "道琼斯"}
        else:
            provider = self.sina
            name_map = {"SH": "上证指数", "SZ": "深成指", "CY": "创业板指"}

        try:
            quote = await provider.get_index(symbol)
            if quote:
                data = {
                    "symbol": symbol,
                    "name": name_map.get(symbol, symbol),
                    "price": quote.price,
                    "change_pct": quote.change_pct,
                    "market": market,
                }
            else:
                # 降级到 mock
                quote = await self.mock.get_index(symbol)
                data = {
                    "symbol": symbol,
                    "name": name_map.get(symbol, symbol),
                    "price": quote.price,
                    "change_pct": quote.change_pct,
                    "market": market,
                }
        except Exception as e:
            logger.error(f"Index fetch failed for {symbol}: {e}")
            quote = await self.mock.get_index(symbol)
            data = {
                "symbol": symbol,
                "name": name_map.get(symbol, symbol),
                "price": quote.price,
                "change_pct": quote.change_pct,
                "market": market,
            }

        # 写入缓存
        await self.redis.setex(cache_key, INDEX_CACHE_TTL, json.dumps(data))
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
        ]
        name_map = {
            "SPX": "S&P 500",
            "NDX": "NASDAQ",
            "DJI": "道琼斯",
            "SH": "上证指数",
            "SZ": "深成指",
            "CY": "创业板指",
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

    async def get_market_board(self, market: str, refresh: bool = False) -> list[MarketBoardItemOut]:
        cache_key = f"market:board:{MARKET_CACHE_VERSION}:{market}"
        if not refresh:
            cached_board = await self._load_cached_list(cache_key, MarketBoardItemOut)
            if cached_board is not None:
                return cached_board

        entries = MARKET_BOARD.get(market, [])
        if not entries:
            return []

        tickers = [entry["ticker"] for entry in entries]
        quotes = await self._get_quotes_batch(tickers)
        board: list[MarketBoardItemOut] = []
        for entry in entries:
            quote = quotes.get(entry["ticker"])
            if not quote:
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
        await self._cache_model_list(cache_key, BOARD_CACHE_TTL, board)
        return board

    async def get_market_overview(self, refresh: bool = False) -> MarketOverviewOut:
        cache_key = f"market:overview:{MARKET_CACHE_VERSION}"
        if not refresh:
            cached = await self.redis.get(cache_key)
        else:
            cached = None
        if cached:
            try:
                raw = cached.decode() if isinstance(cached, bytes) else cached
                return MarketOverviewOut(**json.loads(raw))
            except Exception as e:
                logger.warning(f"Market overview cache parse error: {e}")

        indices, us_board, cn_board = await asyncio.gather(
            self.get_all_indices(refresh=refresh),
            self.get_market_board("us", refresh=refresh),
            self.get_market_board("cn", refresh=refresh),
        )
        overview = MarketOverviewOut(
            indices=indices,
            boards={"us": us_board, "cn": cn_board},
            markets=[
                self._build_market_summary("us", "美股", us_board),
                self._build_market_summary("cn", "A 股", cn_board),
            ],
            updated_at=datetime.now(timezone.utc),
        )
        await self.redis.setex(
            cache_key,
            OVERVIEW_CACHE_TTL,
            json.dumps(overview.model_dump(mode="json")),
        )
        return overview

    def _get_provider(self, ticker: str):
        if ".SH" in ticker or ".SZ" in ticker:
            return self.sina
        return self.yahoo

    async def _get_quotes_batch(self, tickers: list[str]):
        cached, missing = await self._get_cached_quotes(tickers)
        fetched: dict[str, object] = {}

        for chunk_start in range(0, len(missing), BOARD_FETCH_CHUNK_SIZE):
            chunk = missing[chunk_start : chunk_start + BOARD_FETCH_CHUNK_SIZE]
            us_tickers = [ticker for ticker in chunk if self._get_provider(ticker) is self.yahoo]
            cn_tickers = [ticker for ticker in chunk if self._get_provider(ticker) is self.sina]
            results = await asyncio.gather(
                self.yahoo.get_quotes_batch(us_tickers) if us_tickers else self._empty_dict(),
                self.sina.get_quotes_batch(cn_tickers) if cn_tickers else self._empty_dict(),
            )
            for batch in results:
                fetched.update(batch)

            for ticker in chunk:
                quote = fetched.get(ticker)
                if not quote:
                    quote = await self.mock.get_quote(ticker)
                    fetched[ticker] = quote
                await self._cache_quote_data(ticker, quote)

        return {**cached, **fetched}

    async def _get_cached_quotes(self, tickers: list[str]):
        cached: dict[str, object] = {}
        missing: list[str] = []
        for ticker in tickers:
            cache_key = f"quote:{ticker}"
            raw = await self.redis.get(cache_key)
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
            raw = await self.redis.get(cache_key)
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
        us_symbols = [symbol for symbol, market in missing if market == "us"]
        cn_symbols = [symbol for symbol, market in missing if market == "cn"]

        us_task = self.yahoo.get_indices_batch(us_symbols) if us_symbols else self._empty_dict()
        cn_task = self.sina.get_indices_batch(cn_symbols) if cn_symbols else self._empty_dict()
        us_quotes, cn_quotes = await asyncio.gather(us_task, cn_task)
        name_map = {
            "SPX": "S&P 500",
            "NDX": "NASDAQ",
            "DJI": "道琼斯",
            "SH": "上证指数",
            "SZ": "深成指",
            "CY": "创业板指",
        }

        for symbol, market in missing:
            quote = us_quotes.get(symbol) if market == "us" else cn_quotes.get(symbol)
            if not quote:
                quote = await self.mock.get_index(symbol)
            data = {
                "symbol": symbol,
                "name": name_map.get(symbol, symbol),
                "price": quote.price,
                "change_pct": quote.change_pct,
                "market": market,
            }
            await self.redis.setex(f"index:{market}:{symbol}", INDEX_CACHE_TTL, json.dumps(data))
            fetched[(symbol, market)] = IndexQuoteOut(**data)
        return fetched

    async def _cache_quote_data(self, ticker: str, quote) -> None:
        data = {
            "price": quote.price,
            "change_pct": quote.change_pct,
            "name": quote.name,
            "volume": quote.volume,
            "market_status": quote.market_status,
        }
        await self.redis.setex(f"quote:{ticker}", CACHE_TTL, json.dumps(data))

    async def _empty_dict(self) -> dict:
        return {}

    async def _load_cached_list(self, cache_key: str, model_cls):
        raw = await self.redis.get(cache_key)
        if not raw:
            return None
        try:
            payload = json.loads(raw.decode() if isinstance(raw, bytes) else raw)
            return [model_cls(**item) for item in payload]
        except Exception as e:
            logger.warning(f"Aggregate cache parse error for {cache_key}: {e}")
            return None

    async def _cache_model_list(self, cache_key: str, ttl: int, models: list) -> None:
        payload = [model.model_dump(mode="json") for model in models]
        await self.redis.setex(cache_key, ttl, json.dumps(payload))

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
