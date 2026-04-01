from __future__ import annotations

import asyncio
import json
import logging
from contextlib import suppress
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

import httpx
from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.config import settings

logger = logging.getLogger(__name__)

FX_PAIR_USD_CNY = "USD/CNY"
FX_PAIR_HKD_CNY = "HKD/CNY"


def _pair_slug(pair: str) -> str:
    return pair.lower().replace("/", "_")


def _redis_key(kind: str, pair: str) -> str:
    return f"{settings.fx_cache_key_prefix}:{kind}:{_pair_slug(pair)}"


async def _redis_get_safe(redis: Redis | None, key: str) -> bytes | None:
    if redis is None:
        return None
    try:
        return await redis.get(key)
    except RedisError as exc:
        logger.warning("FX redis get failed key=%s error=%s", key, exc)
        return None
    except Exception as exc:
        logger.warning("FX redis get unexpected error key=%s error=%s", key, exc)
        return None


async def _redis_set_safe(redis: Redis | None, key: str, value: str) -> bool:
    if redis is None:
        return False
    try:
        await redis.set(key, value)
        return True
    except RedisError as exc:
        logger.warning("FX redis set failed key=%s error=%s", key, exc)
        return False
    except Exception as exc:
        logger.warning("FX redis set unexpected error key=%s error=%s", key, exc)
        return False


async def _redis_setex_safe(redis: Redis | None, key: str, ttl: int, value: str) -> bool:
    if redis is None:
        return False
    try:
        await redis.setex(key, ttl, value)
        return True
    except RedisError as exc:
        logger.warning("FX redis setex failed key=%s error=%s", key, exc)
        return False
    except Exception as exc:
        logger.warning("FX redis setex unexpected error key=%s error=%s", key, exc)
        return False


def _decode_json(raw: bytes | str | None) -> dict[str, Any] | None:
    if raw is None:
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return data


class FXService:
    def __init__(self, redis: Redis | None):
        self.redis = redis
        self._client = self._build_client()
        self._task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    def _build_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=settings.fx_http_timeout_seconds,
            follow_redirects=True,
        )

    def _default_rate(self, pair: str) -> float:
        if pair == FX_PAIR_HKD_CNY:
            return float(settings.fx_default_hkd_cny)
        return float(settings.fx_default_usd_cny)

    def _pair_for_market(self, market: str) -> str:
        market_normalized = market.lower()
        if market_normalized == "hk":
            return FX_PAIR_HKD_CNY
        if market_normalized == "cn":
            return "CNY/CNY"
        return FX_PAIR_USD_CNY

    def _extract_rates(self, rates: dict[str, Any]) -> dict[str, float]:
        usd_cny_raw = rates.get("CNY")
        usd_hkd_raw = rates.get("HKD")

        usd_cny = self._coerce_rate(usd_cny_raw)
        usd_hkd = self._coerce_rate(usd_hkd_raw)

        result: dict[str, float] = {}
        if usd_cny is not None and usd_cny > 0:
            result[FX_PAIR_USD_CNY] = float(usd_cny)
        if usd_cny is not None and usd_cny > 0 and usd_hkd is not None and usd_hkd > 0:
            result[FX_PAIR_HKD_CNY] = float(usd_cny / usd_hkd)
        return result

    def _coerce_rate(self, raw: Any) -> Decimal | None:
        if raw is None:
            return None
        try:
            value = Decimal(str(raw))
        except Exception:
            return None
        return value if value > 0 else None

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        if self._client.is_closed:
            self._client = self._build_client()
        self._stop_event.clear()
        self._task = asyncio.create_task(self._refresh_loop(), name="fx-refresh-loop")

    async def stop(self) -> None:
        self._stop_event.set()
        task = self._task
        if task and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        self._task = None
        if not self._client.is_closed:
            await self._client.aclose()

    async def _refresh_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                await self.refresh_once()
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=max(settings.fx_refresh_interval_seconds, 1),
                    )
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("FX refresh loop stopped unexpectedly: %s", exc)

    async def refresh_once(self) -> dict[str, float]:
        try:
            response = await self._client.get(settings.fx_provider_url)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("unexpected FX payload shape")
            rates = payload.get("rates")
            if not isinstance(rates, dict):
                raise ValueError("missing FX rates")
            extracted = self._extract_rates(rates)
            if not extracted:
                raise ValueError("no supported FX rates returned")
            fetched_at = datetime.now(timezone.utc).isoformat()
            source = str(payload.get("provider") or payload.get("base_code") or "remote")
            await self._store_snapshot(extracted, source=source, fetched_at=fetched_at)
            return extracted
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("FX refresh failed: %s", exc)
            return {}

    async def _store_snapshot(
        self,
        rates: dict[str, float],
        *,
        source: str,
        fetched_at: str,
    ) -> None:
        for pair, rate in rates.items():
            payload = json.dumps(
                {
                    "pair": pair,
                    "rate": rate,
                    "source": source,
                    "fetched_at": fetched_at,
                },
                ensure_ascii=False,
            )
            await _redis_setex_safe(
                self.redis,
                _redis_key("current", pair),
                settings.fx_cache_ttl_seconds,
                payload,
            )
            await _redis_set_safe(
                self.redis,
                _redis_key("last_success", pair),
                payload,
            )

    async def _read_current_rate(self, pair: str) -> float | None:
        raw = await _redis_get_safe(self.redis, _redis_key("current", pair))
        payload = _decode_json(raw)
        if not payload:
            return None
        rate = self._coerce_rate(payload.get("rate"))
        if rate is None:
            return None
        return float(rate)

    async def _read_last_success_rate(self, pair: str) -> float | None:
        raw = await _redis_get_safe(self.redis, _redis_key("last_success", pair))
        payload = _decode_json(raw)
        if not payload:
            return None
        rate = self._coerce_rate(payload.get("rate"))
        if rate is None:
            return None
        return float(rate)

    async def _read_rate_payload(
        self, kind: str, pair: str
    ) -> dict[str, Any] | None:
        raw = await _redis_get_safe(self.redis, _redis_key(kind, pair))
        return _decode_json(raw)

    def _parse_fetched_at(self, payload: dict[str, Any]) -> datetime | None:
        fetched_at = payload.get("fetched_at")
        if not isinstance(fetched_at, str):
            return None
        try:
            return datetime.fromisoformat(fetched_at)
        except ValueError:
            return None

    async def get_rate_to_cny(
        self, market: str
    ) -> tuple[float, str, datetime | None]:
        market_normalized = market.lower()
        pair = self._pair_for_market(market_normalized)
        if pair == "CNY/CNY":
            return 1.0, pair, None

        payload = await self._read_rate_payload("current", pair)
        if payload is None:
            await self.refresh_once()
            payload = await self._read_rate_payload("current", pair)
        if payload is None:
            payload = await self._read_rate_payload("last_success", pair)
        if payload is not None:
            rate = self._coerce_rate(payload.get("rate"))
            if rate is not None:
                return float(rate), pair, self._parse_fetched_at(payload)

        return self._default_rate(pair), pair, None

    async def get_rate(self, pair: str) -> float:
        if pair == FX_PAIR_USD_CNY:
            rate, _, _ = await self.get_rate_to_cny("us")
            return rate
        if pair == FX_PAIR_HKD_CNY:
            rate, _, _ = await self.get_rate_to_cny("hk")
            return rate
        cached = await self._read_current_rate(pair)
        if cached is not None:
            return cached
        refreshed = await self.refresh_once()
        refreshed_rate = refreshed.get(pair)
        if refreshed_rate is not None:
            return refreshed_rate
        cached = await self._read_last_success_rate(pair)
        if cached is not None:
            return cached
        return self._default_rate(pair)

    async def get_usd_cny(self) -> float:
        rate, _, _ = await self.get_rate_to_cny("us")
        return rate

    async def get_hkd_cny(self) -> float:
        rate, _, _ = await self.get_rate_to_cny("hk")
        return rate

    async def get_rates(self) -> dict[str, float]:
        usd_cny, _, _ = await self.get_rate_to_cny("us")
        hkd_cny, _, _ = await self.get_rate_to_cny("hk")
        return {
            FX_PAIR_USD_CNY: usd_cny,
            FX_PAIR_HKD_CNY: hkd_cny,
        }
