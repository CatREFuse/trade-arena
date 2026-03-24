"""行情数据提供商"""
from __future__ import annotations

import asyncio
import csv
import logging
import math
import random
import re
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Awaitable, Callable

import httpx

try:
    import akshare as ak
except Exception:  # pragma: no cover - 仅用于运行时降级
    ak = None

logger = logging.getLogger(__name__)


class QuoteData:
    """统一行情数据结构"""
    def __init__(
        self,
        ticker: str,
        price: float,
        change_pct: float,
        volume: int = 0,
        market_status: str = "open",
        name: str = "",
        previous_close: float = 0,
    ):
        self.ticker = ticker
        self.price = price
        self.change_pct = change_pct
        self.volume = volume
        self.market_status = market_status
        self.name = name
        self.previous_close = previous_close

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "price": self.price,
            "change_pct": self.change_pct,
            "volume": self.volume,
            "market_status": self.market_status,
            "name": self.name,
            "previous_close": self.previous_close,
        }


class BaseProvider(ABC):
    """行情提供商基类"""

    @abstractmethod
    async def get_quote(self, ticker: str) -> QuoteData | None:
        """获取个股行情"""
        pass

    @abstractmethod
    async def get_index(self, symbol: str) -> QuoteData | None:
        """获取大盘指数"""
        pass

    async def get_quotes_batch(self, tickers: list[str]) -> dict[str, QuoteData | None]:
        results = await asyncio.gather(*(self.get_quote(ticker) for ticker in tickers), return_exceptions=True)
        quotes: dict[str, QuoteData | None] = {}
        for ticker, result in zip(tickers, results):
            if isinstance(result, Exception):
                logger.warning(f"Batch quote fetch failed for {ticker}: {result}")
                quotes[ticker] = None
                continue
            quotes[ticker] = result
        return quotes

    async def get_indices_batch(self, symbols: list[str]) -> dict[str, QuoteData | None]:
        results = await asyncio.gather(*(self.get_index(symbol) for symbol in symbols), return_exceptions=True)
        quotes: dict[str, QuoteData | None] = {}
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                logger.warning(f"Batch index fetch failed for {symbol}: {result}")
                quotes[symbol] = None
                continue
            quotes[symbol] = result
        return quotes


class YahooProvider(BaseProvider):
    """Yahoo Finance 提供商 - 用于美股"""

    SPARK_URL = "https://query1.finance.yahoo.com/v7/finance/spark"
    STOOQ_SNAPSHOT_URL = "https://stooq.com/q/l/"
    STOOQ_HISTORY_URL = "https://stooq.com/q/d/l/"
    STOOQ_FIELDS = "sd2t2ohlcvnp"
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
    }
    INDEX_MAP = {
        "SPX": "^GSPC",  # S&P 500
        "NDX": "^IXIC",  # NASDAQ
        "DJI": "^DJI",  # Dow Jones
    }
    STOOQ_INDEX_MAP = {
        "SPX": "^spx",
        "NDX": "^ndq",
        "DJI": "^dji",
    }
    STOOQ_NAME_MAP = {
        "AAPL": "Apple",
        "MSFT": "Microsoft",
        "NVDA": "NVIDIA",
        "GOOGL": "Alphabet",
        "AMZN": "Amazon",
        "META": "Meta",
        "TSLA": "Tesla",
        "AMD": "AMD",
        "NFLX": "Netflix",
        "PLTR": "Palantir",
        "BRK.B": "Berkshire Hathaway",
        "JPM": "JPMorgan",
        "V": "Visa",
        "MA": "Mastercard",
        "SPX": "S&P 500",
        "NDX": "NASDAQ 100",
        "DJI": "Dow Jones",
    }

    async def get_quote(self, ticker: str) -> QuoteData | None:
        """优先使用 Yahoo spark API，失败时回退到 Stooq 快照数据。"""
        normalized = self._normalize_symbol(ticker)
        try:
            data = await self._fetch_spark(normalized)
            if not data:
                return await self._fetch_stooq_quote(ticker)
            return self._parse_spark(ticker=ticker, data=data)
        except Exception as e:
            logger.warning(f"Yahoo fetch failed for {ticker}: {e}")
            return await self._fetch_stooq_quote(ticker)

    async def get_index(self, symbol: str) -> QuoteData | None:
        """获取美股大盘指数"""
        yahoo_symbol = self.INDEX_MAP.get(symbol, symbol)
        try:
            data = await self._fetch_spark(yahoo_symbol)
            if not data:
                return await self._fetch_stooq_quote(symbol, is_index=True)
            return self._parse_spark(ticker=symbol, data=data)
        except Exception as e:
            logger.warning(f"Yahoo index fetch failed for {symbol}: {e}")
            return await self._fetch_stooq_quote(symbol, is_index=True)

    async def get_quotes_batch(self, tickers: list[str]) -> dict[str, QuoteData | None]:
        if not tickers:
            return {}

        symbol_map = {self._normalize_symbol(ticker): ticker for ticker in tickers}
        try:
            payload = await self._fetch_spark_batch(list(symbol_map.keys()))
            quotes = {
                original_ticker: self._parse_spark(ticker=original_ticker, data=data)
                for symbol, data in payload.items()
                if (original_ticker := symbol_map.get(symbol))
            }
        except Exception as e:
            logger.warning(f"Yahoo batch quote fetch failed: {e}")
            quotes = {}

        missing = [ticker for ticker in tickers if ticker not in quotes or quotes[ticker] is None]
        if missing:
            fallback = await self._fetch_stooq_batch(missing)
            quotes.update(fallback)
            unresolved = [ticker for ticker in missing if ticker not in fallback or fallback[ticker] is None]
            if unresolved:
                history = await asyncio.gather(
                    *(self._fetch_stooq_history_quote(ticker) for ticker in unresolved),
                    return_exceptions=True,
                )
                for ticker, result in zip(unresolved, history):
                    quotes[ticker] = None if isinstance(result, Exception) else result
        return quotes

    async def get_indices_batch(self, symbols: list[str]) -> dict[str, QuoteData | None]:
        if not symbols:
            return {}

        symbol_map = {self.INDEX_MAP.get(symbol, symbol): symbol for symbol in symbols}
        try:
            payload = await self._fetch_spark_batch(list(symbol_map.keys()))
            quotes = {
                original_symbol: self._parse_spark(ticker=original_symbol, data=data)
                for yahoo_symbol, data in payload.items()
                if (original_symbol := symbol_map.get(yahoo_symbol))
            }
        except Exception as e:
            logger.warning(f"Yahoo batch index fetch failed: {e}")
            quotes = {}

        missing = [symbol for symbol in symbols if symbol not in quotes or quotes[symbol] is None]
        if missing:
            fallback = await self._fetch_stooq_batch(missing, is_index=True)
            quotes.update(fallback)
            unresolved = [symbol for symbol in missing if symbol not in fallback or fallback[symbol] is None]
            if unresolved:
                history = await asyncio.gather(
                    *(self._fetch_stooq_history_quote(symbol, is_index=True) for symbol in unresolved),
                    return_exceptions=True,
                )
                for symbol, result in zip(unresolved, history):
                    quotes[symbol] = None if isinstance(result, Exception) else result
        return quotes

    async def _fetch_spark(self, symbol: str) -> dict | None:
        payload = await self._fetch_spark_batch([symbol])
        return payload.get(symbol)

    async def _fetch_spark_batch(self, symbols: list[str]) -> dict[str, dict]:
        params = {
            "symbols": ",".join(symbols),
            "range": "1d",
            "interval": "5m",
            "indicators": "close",
            "includeTimestamps": "true",
        }

        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(self.SPARK_URL, params=params, headers=self.HEADERS)
            resp.raise_for_status()
            payload = resp.json()

        spark = payload.get("spark", {})
        results = spark.get("result") or []
        quotes: dict[str, dict] = {}
        for result in results:
            symbol = result.get("symbol")
            responses = result.get("response") or []
            if symbol and responses:
                quotes[symbol] = responses[0]
        return quotes

    def _parse_spark(self, ticker: str, data: dict) -> QuoteData | None:
        meta = data.get("meta") or {}
        indicators = data.get("indicators") or {}
        quotes = indicators.get("quote") or [{}]
        quote = quotes[0] if quotes else {}

        price = self._coerce_number(meta.get("regularMarketPrice"))
        if price is None:
            price = self._last_numeric(quote.get("close", []))
        if price is None:
            return None

        previous_close = self._extract_previous_close(meta, quote) or price
        change_pct = ((price - previous_close) / previous_close * 100) if previous_close else 0
        volume = self._coerce_number(meta.get("regularMarketVolume"))
        if volume is None:
            volume = self._last_numeric(quote.get("volume", [])) or 0

        return QuoteData(
            ticker=ticker,
            price=round(price, 2),
            change_pct=round(change_pct, 2),
            volume=int(volume),
            market_status=self._market_status(meta.get("currentTradingPeriod")),
            name=meta.get("shortName") or meta.get("longName") or "",
            previous_close=round(previous_close, 2),
        )

    async def _fetch_stooq_quote(self, ticker: str, is_index: bool = False) -> QuoteData | None:
        batch = await self._fetch_stooq_batch([ticker], is_index=is_index)
        quote = batch.get(ticker)
        if quote:
            return quote
        return await self._fetch_stooq_history_quote(ticker, is_index=is_index)

    async def _fetch_stooq_batch(
        self,
        tickers: list[str],
        is_index: bool = False,
    ) -> dict[str, QuoteData | None]:
        symbol_map: dict[str, str] = {}
        for ticker in tickers:
            stooq_symbol = self._stooq_symbol(ticker, is_index=is_index)
            if stooq_symbol:
                symbol_map[stooq_symbol.lower()] = ticker

        if not symbol_map:
            return {}

        params = {
            "s": " ".join(symbol_map.keys()),
            "f": self.STOOQ_FIELDS,
            "e": "csv",
        }
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(self.STOOQ_SNAPSHOT_URL, params=params, headers=self.HEADERS)
            resp.raise_for_status()
        return self._parse_stooq_snapshot_csv(resp.text, symbol_map)

    async def _fetch_stooq_history_quote(self, ticker: str, is_index: bool = False) -> QuoteData | None:
        stooq_symbol = self._stooq_symbol(ticker, is_index=is_index)
        if not stooq_symbol:
            return None

        today = datetime.now(timezone.utc).date()
        start = today - timedelta(days=7)
        params = {
            "s": stooq_symbol,
            "i": "d",
            "d1": start.strftime("%Y%m%d"),
            "d2": today.strftime("%Y%m%d"),
        }
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(self.STOOQ_HISTORY_URL, params=params, headers=self.HEADERS)
            resp.raise_for_status()
            return self._parse_stooq_history_csv(ticker, resp.text)

    @classmethod
    def _parse_stooq_snapshot_csv(
        cls,
        text: str,
        symbol_map: dict[str, str],
    ) -> dict[str, QuoteData | None]:
        quotes: dict[str, QuoteData | None] = {}
        rows = csv.reader(line for line in text.splitlines() if line.strip())
        for row in rows:
            if len(row) < 10:
                continue

            raw_symbol, *_rest, close, volume, name, previous_close = [part.strip() for part in row[:10]]
            ticker = symbol_map.get(raw_symbol.lower())
            if not ticker or close == "N/D":
                continue

            price = cls._coerce_number(close)
            prev_value = cls._coerce_number(previous_close) or price
            volume_value = cls._coerce_number(volume) or 0
            if price is None:
                continue

            change_pct = ((price - prev_value) / prev_value * 100) if prev_value else 0
            resolved_name = cls.STOOQ_NAME_MAP.get(ticker, name.title() if name else ticker)
            quotes[ticker] = QuoteData(
                ticker=ticker,
                price=round(price, 2),
                change_pct=round(change_pct, 2),
                volume=int(volume_value),
                market_status="closed",
                name=resolved_name,
                previous_close=round(prev_value, 2),
            )
        return quotes

    @classmethod
    def _parse_stooq_history_csv(cls, ticker: str, text: str) -> QuoteData | None:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) < 2:
            return None

        rows = []
        for raw in lines[1:]:
            parts = [part.strip() for part in raw.split(",")]
            if len(parts) < 6 or parts[1] == "N/D":
                continue
            rows.append(parts)

        if not rows:
            return None

        latest = rows[-1]
        previous = rows[-2] if len(rows) >= 2 else latest
        close = cls._coerce_number(latest[4])
        previous_close = cls._coerce_number(previous[4]) or close
        volume = cls._coerce_number(latest[5]) or 0
        if close is None:
            return None

        change_pct = ((close - previous_close) / previous_close * 100) if previous_close else 0
        return QuoteData(
            ticker=ticker,
            price=round(close, 2),
            change_pct=round(change_pct, 2),
            volume=int(volume),
            market_status="closed",
            name=cls.STOOQ_NAME_MAP.get(ticker, ticker),
            previous_close=round(previous_close, 2),
        )

    @staticmethod
    def _normalize_symbol(ticker: str) -> str:
        if ticker.endswith(".SH") or ticker.endswith(".SZ") or ticker.endswith(".HK"):
            return ticker
        return ticker.replace(".", "-")

    def _stooq_symbol(self, ticker: str, is_index: bool = False) -> str | None:
        if is_index:
            return self.STOOQ_INDEX_MAP.get(ticker)
        normalized = self._normalize_symbol(ticker).lower()
        if not normalized:
            return None
        if normalized.endswith(".hk"):
            return normalized
        return f"{normalized}.us"

    @staticmethod
    def _coerce_number(value) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _extract_previous_close(cls, meta: dict, quote: dict) -> float | None:
        for key in ("previousClose", "chartPreviousClose"):
            value = cls._coerce_number(meta.get(key))
            if value is not None:
                return value

        closes = [cls._coerce_number(item) for item in quote.get("close", [])]
        closes = [item for item in closes if item is not None]
        if len(closes) >= 2:
            return closes[-2]
        if closes:
            return closes[-1]
        return None

    @classmethod
    def _last_numeric(cls, values: list) -> float | None:
        for value in reversed(values or []):
            number = cls._coerce_number(value)
            if number is not None:
                return number
        return None

    @staticmethod
    def _market_status(periods: dict | None) -> str:
        if not periods:
            return "unknown"

        now = int(datetime.now(timezone.utc).timestamp())
        time_ranges = {
            "pre": "pre",
            "regular": "open",
            "post": "post",
        }
        for key, status in time_ranges.items():
            period = periods.get(key) or {}
            start = period.get("start")
            end = period.get("end")
            if start and end and start <= now <= end:
                return status
        return "closed"


class TencentProvider(BaseProvider):
    """腾讯行情接口 - 用于 A 股和港股，支持批量查询"""

    QUOTE_URL = "https://qt.gtimg.cn/q="
    HEADERS = {
        "Referer": "https://gu.qq.com/",
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
    }
    INDEX_MAP = {
        "SH": "s_sh000001",  # 上证指数
        "SZ": "s_sz399001",  # 深成指
        "CY": "s_sz399006",  # 创业板指
        "HSI": "hkHSI",  # 恒生指数
        "HSCEI": "hkHSCEI",  # 国企指数
    }

    async def get_quote(self, ticker: str) -> QuoteData | None:
        code = self._to_quote_symbol(ticker)
        if not code:
            return None
        payload = await self._fetch_payload([code])
        return self._parse_quote_payload(ticker, payload.get(code))

    async def get_index(self, symbol: str) -> QuoteData | None:
        code = self.INDEX_MAP.get(symbol)
        if not code:
            return None
        payload = await self._fetch_payload([code])
        return self._parse_index_payload(symbol, code, payload.get(code))

    async def get_quotes_batch(self, tickers: list[str]) -> dict[str, QuoteData | None]:
        if not tickers:
            return {}

        symbol_map: dict[str, str] = {}
        for ticker in tickers:
            code = self._to_quote_symbol(ticker)
            if code:
                symbol_map[code] = ticker

        if not symbol_map:
            return {ticker: None for ticker in tickers}

        payload = await self._fetch_payload(list(symbol_map.keys()))
        quotes: dict[str, QuoteData | None] = {}
        for code, ticker in symbol_map.items():
            quotes[ticker] = self._parse_quote_payload(ticker, payload.get(code))
        for ticker in tickers:
            quotes.setdefault(ticker, None)
        return quotes

    async def get_indices_batch(self, symbols: list[str]) -> dict[str, QuoteData | None]:
        if not symbols:
            return {}

        symbol_map = {
            code: symbol
            for symbol in symbols
            if (code := self.INDEX_MAP.get(symbol))
        }
        if not symbol_map:
            return {symbol: None for symbol in symbols}

        payload = await self._fetch_payload(list(symbol_map.keys()))
        quotes: dict[str, QuoteData | None] = {}
        for code, symbol in symbol_map.items():
            quotes[symbol] = self._parse_index_payload(symbol, code, payload.get(code))
        for symbol in symbols:
            quotes.setdefault(symbol, None)
        return quotes

    async def _fetch_payload(self, codes: list[str]) -> dict[str, str]:
        if not codes:
            return {}
        url = f"{self.QUOTE_URL}{','.join(codes)}"
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url, headers=self.HEADERS)
            resp.raise_for_status()
        return self._parse_response_text(resp.text)

    @classmethod
    def _parse_response_text(cls, text: str) -> dict[str, str]:
        parsed: dict[str, str] = {}
        for match in re.finditer(r'v_([^=]+)="([^"]*)";', text):
            parsed[match.group(1)] = match.group(2)
        return parsed

    @classmethod
    def _parse_quote_payload(cls, ticker: str, payload: str | None) -> QuoteData | None:
        if not payload:
            return None
        fields = payload.split("~")
        if len(fields) < 7:
            return None

        price = cls._coerce_number(fields[3])
        previous_close = cls._coerce_number(fields[4])
        if price is None:
            return None
        if previous_close is None:
            previous_close = price

        volume = cls._coerce_number(fields[6]) or 0
        if ticker.endswith(".SH") or ticker.endswith(".SZ"):
            volume *= 100

        change_pct = ((price - previous_close) / previous_close * 100) if previous_close else 0
        return QuoteData(
            ticker=ticker,
            price=round(price, 2),
            change_pct=round(change_pct, 2),
            volume=int(volume),
            market_status="open",
            name=fields[1].strip(),
            previous_close=round(previous_close, 2),
        )

    @classmethod
    def _parse_index_payload(
        cls,
        symbol: str,
        source_code: str,
        payload: str | None,
    ) -> QuoteData | None:
        if not payload:
            return None
        fields = payload.split("~")
        if len(fields) < 6:
            return None

        price = cls._coerce_number(fields[3])
        if price is None:
            return None

        # A 股指数（s_ 前缀）直接返回涨跌幅字段；港股指数按昨收计算
        if source_code.startswith("s_"):
            change_pct = cls._coerce_number(fields[5]) or 0
            previous_close = price
        else:
            previous_close = cls._coerce_number(fields[4]) or price
            change_pct = ((price - previous_close) / previous_close * 100) if previous_close else 0

        return QuoteData(
            ticker=symbol,
            price=round(price, 2),
            change_pct=round(change_pct, 2),
            volume=0,
            market_status="open",
            name=fields[1].strip(),
            previous_close=round(previous_close, 2),
        )

    @staticmethod
    def _to_quote_symbol(ticker: str) -> str | None:
        normalized = ticker.upper()
        if normalized.endswith(".SH"):
            return f"sh{normalized.removesuffix('.SH')}"
        if normalized.endswith(".SZ"):
            return f"sz{normalized.removesuffix('.SZ')}"
        if normalized.endswith(".HK"):
            code = normalized.removesuffix(".HK")
            if not code.isdigit():
                return None
            return f"hk{code.zfill(5)}"
        return None

    @staticmethod
    def _coerce_number(value: str | float | int | None) -> float | None:
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


class AkshareProvider(BaseProvider):
    """AKShare 提供商 - 优先用于 A/HK 行情与指数"""

    SNAPSHOT_TTL_SECONDS = 20
    REQUEST_TIMEOUT_SECONDS = 4
    MISSING_VALUES = {"", "-", "--", "None", "null", "nan", "NaN"}

    QUOTE_CODE_COLUMNS = ("代码", "symbol", "证券代码", "股票代码", "code")
    QUOTE_NAME_COLUMNS = ("名称", "name", "股票简称", "证券简称")
    QUOTE_PRICE_COLUMNS = ("最新价", "trade", "当前价", "现价", "最新", "close")
    QUOTE_CHANGE_PCT_COLUMNS = ("涨跌幅", "涨跌幅(%)", "changepercent", "pct_chg")
    QUOTE_PREV_CLOSE_COLUMNS = ("昨收", "昨收价", "settlement", "前收盘", "昨日收盘")
    QUOTE_VOLUME_COLUMNS = ("成交量", "成交量(股)", "volume")

    INDEX_CODE_COLUMNS = ("代码", "symbol", "指数代码", "code")
    INDEX_NAME_COLUMNS = ("名称", "name", "指数名称")
    INDEX_PRICE_COLUMNS = ("最新价", "现价", "最新", "close")
    INDEX_CHANGE_PCT_COLUMNS = ("涨跌幅", "涨跌幅(%)", "changepercent", "pct_chg")
    INDEX_PREV_CLOSE_COLUMNS = ("昨收", "昨收价", "前收盘", "昨日收盘")

    def __init__(self):
        self._snapshot_cache: dict[str, tuple[float, dict[str, QuoteData]]] = {}
        self._snapshot_locks = {
            "cn_quote": asyncio.Lock(),
            "hk_quote": asyncio.Lock(),
            "cn_index": asyncio.Lock(),
            "hk_index": asyncio.Lock(),
        }

    async def get_quote(self, ticker: str) -> QuoteData | None:
        ticker = ticker.upper()
        if ticker.endswith(".SH") or ticker.endswith(".SZ"):
            snapshot = await self._load_snapshot("cn_quote", self._load_cn_quote_map)
            return snapshot.get(ticker)
        if ticker.endswith(".HK"):
            normalized = self._normalize_hk_ticker(ticker)
            if not normalized:
                return None
            snapshot = await self._load_snapshot("hk_quote", self._load_hk_quote_map)
            return snapshot.get(normalized)
        return None

    async def get_index(self, symbol: str) -> QuoteData | None:
        symbol = symbol.upper()
        if symbol in {"SH", "SZ", "CY", "HS300"}:
            snapshot = await self._load_snapshot("cn_index", self._load_cn_index_map)
            return snapshot.get(symbol)
        if symbol in {"HSI", "HSCEI"}:
            snapshot = await self._load_snapshot("hk_index", self._load_hk_index_map)
            return snapshot.get(symbol)
        return None

    async def get_quotes_batch(self, tickers: list[str]) -> dict[str, QuoteData | None]:
        if not tickers:
            return {}

        results: dict[str, QuoteData | None] = {ticker: None for ticker in tickers}
        cn_ticker_map: dict[str, str] = {}
        hk_ticker_map: dict[str, str] = {}

        for ticker in tickers:
            normalized = ticker.upper()
            if normalized.endswith(".SH") or normalized.endswith(".SZ"):
                cn_ticker_map[normalized] = ticker
            elif normalized.endswith(".HK"):
                hk_ticker = self._normalize_hk_ticker(normalized)
                if hk_ticker:
                    hk_ticker_map[hk_ticker] = ticker

        if cn_ticker_map:
            snapshot = await self._load_snapshot("cn_quote", self._load_cn_quote_map)
            for normalized, original in cn_ticker_map.items():
                results[original] = snapshot.get(normalized)

        if hk_ticker_map:
            snapshot = await self._load_snapshot("hk_quote", self._load_hk_quote_map)
            for normalized, original in hk_ticker_map.items():
                results[original] = snapshot.get(normalized)

        return results

    async def get_indices_batch(self, symbols: list[str]) -> dict[str, QuoteData | None]:
        if not symbols:
            return {}

        results: dict[str, QuoteData | None] = {symbol: None for symbol in symbols}
        symbol_map = {symbol.upper(): symbol for symbol in symbols}
        cn_symbols = [symbol for symbol in symbol_map if symbol in {"SH", "SZ", "CY", "HS300"}]
        hk_symbols = [symbol for symbol in symbol_map if symbol in {"HSI", "HSCEI"}]

        if cn_symbols:
            snapshot = await self._load_snapshot("cn_index", self._load_cn_index_map)
            for symbol in cn_symbols:
                results[symbol_map[symbol]] = snapshot.get(symbol)

        if hk_symbols:
            snapshot = await self._load_snapshot("hk_index", self._load_hk_index_map)
            for symbol in hk_symbols:
                results[symbol_map[symbol]] = snapshot.get(symbol)
        return results

    async def _load_snapshot(
        self,
        cache_key: str,
        loader: Callable[[], Awaitable[dict[str, QuoteData]]],
    ) -> dict[str, QuoteData]:
        now = asyncio.get_running_loop().time()
        cached = self._snapshot_cache.get(cache_key)
        if cached and now - cached[0] <= self.SNAPSHOT_TTL_SECONDS:
            return cached[1]

        lock = self._snapshot_locks[cache_key]
        async with lock:
            now = asyncio.get_running_loop().time()
            cached = self._snapshot_cache.get(cache_key)
            if cached and now - cached[0] <= self.SNAPSHOT_TTL_SECONDS:
                return cached[1]

            loaded = await loader()
            if loaded:
                self._snapshot_cache[cache_key] = (now, loaded)
                return loaded

            if cached:
                self._snapshot_cache[cache_key] = (now, cached[1])
                return cached[1]
            self._snapshot_cache[cache_key] = (now, {})
            return {}

    async def _load_cn_quote_map(self) -> dict[str, QuoteData]:
        frames = [
            ("stock_zh_a_spot_em", lambda: ak.stock_zh_a_spot_em()),
            ("stock_zh_a_spot", lambda: ak.stock_zh_a_spot()),
        ]
        return await self._load_quote_map_from_frames(frames, self._parse_cn_quote_frame)

    async def _load_hk_quote_map(self) -> dict[str, QuoteData]:
        frames = [
            ("stock_hk_spot_em", lambda: ak.stock_hk_spot_em()),
            ("stock_hk_spot", lambda: ak.stock_hk_spot()),
        ]
        return await self._load_quote_map_from_frames(frames, self._parse_hk_quote_frame)

    async def _load_cn_index_map(self) -> dict[str, QuoteData]:
        frames = [
            ("stock_zh_index_spot_sina", lambda: ak.stock_zh_index_spot_sina()),
            ("stock_zh_index_spot_em", lambda: ak.stock_zh_index_spot_em(symbol="上证系列指数")),
        ]
        return await self._load_quote_map_from_frames(frames, self._parse_cn_index_frame)

    async def _load_hk_index_map(self) -> dict[str, QuoteData]:
        frames = [
            ("stock_hk_index_spot_sina", lambda: ak.stock_hk_index_spot_sina()),
            ("stock_hk_index_spot_em", lambda: ak.stock_hk_index_spot_em()),
        ]
        return await self._load_quote_map_from_frames(frames, self._parse_hk_index_frame)

    async def _load_quote_map_from_frames(
        self,
        frames: list[tuple[str, Callable[[], object]]],
        parser: Callable[[object], dict[str, QuoteData]],
    ) -> dict[str, QuoteData]:
        if ak is None:
            return {}

        for name, loader in frames:
            frame = await self._fetch_frame(name, loader)
            if frame is None:
                continue
            parsed = parser(frame)
            if parsed:
                return parsed
        return {}

    async def _fetch_frame(self, name: str, loader: Callable[[], object]):
        try:
            frame = await asyncio.wait_for(
                asyncio.to_thread(loader),
                timeout=self.REQUEST_TIMEOUT_SECONDS,
            )
            if frame is None or getattr(frame, "empty", True):
                return None
            return frame
        except Exception as e:
            logger.warning("AKShare fetch failed for %s: %s", name, e)
            return None

    def _parse_cn_quote_frame(self, frame) -> dict[str, QuoteData]:
        quotes: dict[str, QuoteData] = {}
        for row in frame.to_dict(orient="records"):
            ticker = self._extract_cn_ticker(row)
            if not ticker:
                continue
            quote = self._build_stock_quote(ticker, row)
            if quote:
                quotes[ticker] = quote
        return quotes

    def _parse_hk_quote_frame(self, frame) -> dict[str, QuoteData]:
        quotes: dict[str, QuoteData] = {}
        for row in frame.to_dict(orient="records"):
            ticker = self._extract_hk_ticker(row)
            if not ticker:
                continue
            quote = self._build_stock_quote(ticker, row)
            if quote:
                quotes[ticker] = quote
        return quotes

    def _parse_cn_index_frame(self, frame) -> dict[str, QuoteData]:
        quotes: dict[str, QuoteData] = {}
        for row in frame.to_dict(orient="records"):
            symbol = self._match_cn_index_symbol(row)
            if not symbol:
                continue
            quote = self._build_index_quote(symbol, row)
            if quote:
                quotes[symbol] = quote
        return quotes

    def _parse_hk_index_frame(self, frame) -> dict[str, QuoteData]:
        quotes: dict[str, QuoteData] = {}
        for row in frame.to_dict(orient="records"):
            symbol = self._match_hk_index_symbol(row)
            if not symbol:
                continue
            quote = self._build_index_quote(symbol, row)
            if quote:
                quotes[symbol] = quote
        return quotes

    def _build_stock_quote(self, ticker: str, row: dict) -> QuoteData | None:
        price = self._pick_number(row, self.QUOTE_PRICE_COLUMNS)
        if price is None:
            return None

        previous_close = self._pick_number(row, self.QUOTE_PREV_CLOSE_COLUMNS)
        change_pct = self._pick_number(row, self.QUOTE_CHANGE_PCT_COLUMNS)
        if change_pct is None and previous_close:
            change_pct = (price - previous_close) / previous_close * 100
        if change_pct is None:
            change_pct = 0.0
        if previous_close is None:
            previous_close = price / (1 + change_pct / 100) if change_pct else price

        volume = self._pick_number(row, self.QUOTE_VOLUME_COLUMNS) or 0
        name = self._pick_text(row, self.QUOTE_NAME_COLUMNS) or ticker

        return QuoteData(
            ticker=ticker,
            price=round(price, 2),
            change_pct=round(change_pct, 2),
            volume=int(volume),
            market_status="open",
            name=name,
            previous_close=round(previous_close, 2),
        )

    def _build_index_quote(self, symbol: str, row: dict) -> QuoteData | None:
        price = self._pick_number(row, self.INDEX_PRICE_COLUMNS)
        if price is None:
            return None

        previous_close = self._pick_number(row, self.INDEX_PREV_CLOSE_COLUMNS)
        change_pct = self._pick_number(row, self.INDEX_CHANGE_PCT_COLUMNS)
        if change_pct is None and previous_close:
            change_pct = (price - previous_close) / previous_close * 100
        if change_pct is None:
            change_pct = 0.0
        if previous_close is None:
            previous_close = price / (1 + change_pct / 100) if change_pct else price

        name = self._pick_text(row, self.INDEX_NAME_COLUMNS) or symbol
        return QuoteData(
            ticker=symbol,
            price=round(price, 2),
            change_pct=round(change_pct, 2),
            volume=0,
            market_status="open",
            name=name,
            previous_close=round(previous_close, 2),
        )

    def _extract_cn_ticker(self, row: dict) -> str | None:
        raw = self._pick_text(row, self.QUOTE_CODE_COLUMNS)
        token = self._sanitize_token(raw)
        if not token:
            return None

        if token.startswith("SH") and token[2:].isdigit():
            return f"{token[2:8]}.SH"
        if token.startswith("SZ") and token[2:].isdigit():
            return f"{token[2:8]}.SZ"

        digits = re.sub(r"\D", "", token)
        if len(digits) != 6:
            return None
        suffix = ".SH" if digits.startswith(("5", "6", "9")) else ".SZ"
        return f"{digits}{suffix}"

    def _extract_hk_ticker(self, row: dict) -> str | None:
        raw = self._pick_text(row, self.QUOTE_CODE_COLUMNS)
        return self._normalize_hk_ticker(raw)

    def _match_cn_index_symbol(self, row: dict) -> str | None:
        code = self._sanitize_token(self._pick_text(row, self.INDEX_CODE_COLUMNS))
        name = self._pick_text(row, self.INDEX_NAME_COLUMNS)

        if code in {"000001", "SH000001", "SSH000001", "S_SH000001"} or ("上证" in name and "国企" not in name):
            return "SH"
        if code in {"399001", "SZ399001", "SSZ399001", "S_SZ399001"} or "深成指" in name or "深证成指" in name:
            return "SZ"
        if code in {"399006", "SZ399006", "SSZ399006", "S_SZ399006"} or "创业板" in name:
            return "CY"
        if code in {"000300", "SH000300", "SSH000300", "S_SH000300"} or "沪深300" in name:
            return "HS300"
        return None

    def _match_hk_index_symbol(self, row: dict) -> str | None:
        code = self._sanitize_token(self._pick_text(row, self.INDEX_CODE_COLUMNS))
        name = self._pick_text(row, self.INDEX_NAME_COLUMNS)

        if code in {"HSI", "HKHSI"} or ("恒生指数" in name and "国企" not in name and "中国企业" not in name):
            return "HSI"
        if code in {"HSCEI", "HKHSCEI", "HSCCI", "HSHCI"} or "国企指数" in name or "中国企业指数" in name:
            return "HSCEI"
        return None

    @classmethod
    def _normalize_hk_ticker(cls, raw: str) -> str | None:
        token = cls._sanitize_token(raw)
        if not token:
            return None
        if token.endswith("HK"):
            token = token[:-2]
        if token.startswith("HK"):
            token = token[2:]
        digits = re.sub(r"\D", "", token)
        if not digits:
            return None
        core = digits.lstrip("0") or "0"
        if len(core) < 4:
            core = core.zfill(4)
        return f"{core}.HK"

    @classmethod
    def _pick_text(cls, row: dict, columns: tuple[str, ...]) -> str:
        for column in columns:
            if column not in row:
                continue
            value = row.get(column)
            if value is None:
                continue
            text = str(value).strip()
            if not text or text in cls.MISSING_VALUES:
                continue
            return text
        return ""

    @classmethod
    def _pick_number(cls, row: dict, columns: tuple[str, ...]) -> float | None:
        for column in columns:
            if column not in row:
                continue
            number = cls._coerce_number(row.get(column))
            if number is not None:
                return number
        return None

    @classmethod
    def _sanitize_token(cls, value) -> str:
        if value is None:
            return ""
        text = str(value).strip().upper()
        if not text or text in cls.MISSING_VALUES:
            return ""
        return re.sub(r"[^A-Z0-9.]", "", text)

    @classmethod
    def _coerce_number(cls, value) -> float | None:
        if value is None:
            return None
        if isinstance(value, float) and math.isnan(value):
            return None
        if isinstance(value, str):
            cleaned = value.strip().replace(",", "").replace("%", "")
            if not cleaned or cleaned in cls.MISSING_VALUES:
                return None
            value = cleaned
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


class SinaProvider(BaseProvider):
    """新浪财经 API - 用于A股，免费无需 key"""

    # A股代码映射
    CN_STOCKS = {
        "600519.SH": "sh600519",  # 茅台
        "000858.SZ": "sz000858",  # 五粮液
        "601318.SH": "sh601318",  # 中国平安
        "300750.SZ": "sz300750",  # 宁德时代
        "002594.SZ": "sz002594",  # 比亚迪
        "600036.SH": "sh600036",  # 招商银行
        "000001.SZ": "sz000001",  # 平安银行
        "601899.SH": "sh601899",  # 紫金矿业
        "000333.SZ": "sz000333",  # 美的集团
        "600900.SH": "sh600900",  # 长江电力
        "601012.SH": "sh601012",  # 隆基绿能
        "000568.SZ": "sz000568",  # 泸州老窖
        "002415.SZ": "sz002415",  # 海康威视
        "603288.SH": "sh603288",  # 海天味业
    }

    # A股指数映射
    CN_INDICES = {
        "SH": "s_sh000001",   # 上证指数
        "SZ": "s_sz399001",   # 深成指
        "CY": "s_sz399006",   # 创业板指
        "HS300": "s_sh000300", # 沪深300
    }

    async def get_quote(self, ticker: str) -> QuoteData | None:
        """获取A股行情"""
        sina_code = self.CN_STOCKS.get(ticker)
        if not sina_code:
            # 尝试转换格式
            sina_code = self._convert_to_sina_code(ticker)
            if not sina_code:
                return None

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                url = f"https://hq.sinajs.cn/list={sina_code}"
                headers = {
                    "Referer": "https://finance.sina.com.cn",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                resp = await client.get(url, headers=headers)
                resp.encoding = "gb2312"
                return self._parse_stock_response(ticker, resp.text)
        except Exception as e:
            logger.warning(f"Sina fetch failed for {ticker}: {e}")
            return None

    async def get_index(self, symbol: str) -> QuoteData | None:
        """获取A股大盘指数"""
        sina_code = self.CN_INDICES.get(symbol)
        if not sina_code:
            return None

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                url = f"https://hq.sinajs.cn/list={sina_code}"
                headers = {
                    "Referer": "https://finance.sina.com.cn",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                resp = await client.get(url, headers=headers)
                resp.encoding = "gb2312"
                return self._parse_index_response(symbol, resp.text)
        except Exception as e:
            logger.warning(f"Sina index fetch failed for {symbol}: {e}")
            return None

    def _convert_to_sina_code(self, ticker: str) -> str | None:
        """转换股票代码到新浪格式"""
        # 600519.SH -> sh600519
        # 000858.SZ -> sz000858
        if ".SH" in ticker:
            return "sh" + ticker.replace(".SH", "")
        elif ".SZ" in ticker:
            return "sz" + ticker.replace(".SZ", "")
        return None

    def _parse_stock_response(self, ticker: str, text: str) -> QuoteData | None:
        """解析股票行情响应"""
        try:
            # 格式: var hq_str_sh600519="贵州茅台,1670.00,1650.00,1680.00...
            match = re.search(r'"([^"]*)"', text)
            if not match:
                return None

            data = match.group(1).split(",")
            if len(data) < 8:
                return None

            name = data[0]  # 股票名称
            price = float(data[3])  # 当前价
            prev_close = float(data[2])  # 昨收
            change_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0
            volume = int(int(data[8]) / 100)  # 成交量（手转股）

            return QuoteData(
                ticker=ticker,
                price=round(price, 2),
                change_pct=round(change_pct, 2),
                volume=volume,
                market_status="open",
                name=name,
                previous_close=round(prev_close, 2),
            )
        except Exception as e:
            logger.error(f"Parse error: {e}, text: {text[:100]}")
            return None

    def _parse_index_response(self, symbol: str, text: str) -> QuoteData | None:
        """解析指数行情响应"""
        try:
            # 格式: var hq_str_s_sh000001="上证指数,3287.45,-5.12,-0.15...
            match = re.search(r'"([^"]*)"', text)
            if not match:
                return None

            data = match.group(1).split(",")
            if len(data) < 4:
                return None

            name = data[0]  # 指数名称
            price = float(data[1])  # 当前点数
            change_pct = float(data[3])  # 涨跌幅百分比

            return QuoteData(
                ticker=symbol,
                price=price,
                change_pct=change_pct,
                volume=0,
                market_status="open",
                name=name,
            )
        except Exception as e:
            logger.error(f"Parse index error: {e}, text: {text[:100]}")
            return None


class MockProvider(BaseProvider):
    """Mock 数据提供商 - 用于降级"""

    MOCK_PRICES = {
        "AAPL": 195.0, "MSFT": 425.0, "NVDA": 890.0, "GOOGL": 175.0,
        "AMZN": 205.0, "META": 510.0, "TSLA": 245.0, "BRK-B": 420.0,
        "JPM": 215.0, "V": 290.0, "UNH": 520.0, "MA": 485.0, "AMD": 170.0,
        "600519.SH": 1680.0, "601318.SH": 48.0, "600036.SH": 35.0,
        "000858.SZ": 135.0, "300750.SZ": 210.0, "601899.SH": 18.0,
        "002594.SZ": 280.0, "000001.SZ": 12.0,
    }

    MOCK_INDICES = {
        "SPX": 5892.0, "NDX": 19205.0, "DJI": 43100.0,
        "SH": 3287.0, "SZ": 10450.0, "CY": 2105.0,
    }

    async def get_quote(self, ticker: str) -> QuoteData:
        base_price = self.MOCK_PRICES.get(ticker, 100.0)
        jitter = random.uniform(-0.02, 0.02)
        price = round(base_price * (1 + jitter), 2)
        change_pct = round(jitter * 100, 2)

        return QuoteData(
            ticker=ticker,
            price=price,
            change_pct=change_pct,
            volume=random.randint(100000, 10000000),
            market_status="open",
            previous_close=base_price,
        )

    async def get_index(self, symbol: str) -> QuoteData:
        base = self.MOCK_INDICES.get(symbol, 3000.0)
        jitter = random.uniform(-0.01, 0.01)
        price = round(base * (1 + jitter), 2)
        change_pct = round(jitter * 100, 2)

        return QuoteData(
            ticker=symbol,
            price=price,
            change_pct=change_pct,
            volume=0,
            market_status="open",
        )


def get_provider(ticker: str) -> BaseProvider:
    """根据 ticker 选择合适的提供商"""
    # A股代码特征
    if ".SH" in ticker or ".SZ" in ticker or ".HK" in ticker:
        return AkshareProvider()
    # 美股（字母代码）
    return YahooProvider()
