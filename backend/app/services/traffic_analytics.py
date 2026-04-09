from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import ipaddress
import json
from typing import Any

import httpx


class TrafficAnalyticsService:
    RETENTION_DAYS = 45
    GEO_CACHE_TTL_SECONDS = 30 * 24 * 60 * 60
    GEO_LOOKUP_TIMEOUT = httpx.Timeout(2.5, connect=1.2)

    def __init__(self, redis_client: Any):
        self.redis = redis_client

    @staticmethod
    def normalize_path(raw_path: str | None) -> str:
        text = str(raw_path or "").strip()
        if not text:
            return "/"
        if not text.startswith("/"):
            text = f"/{text}"
        text = text.split("?", 1)[0].split("#", 1)[0].strip() or "/"
        return text[:200]

    @staticmethod
    def mask_ip(raw_ip: str | None) -> str:
        text = str(raw_ip or "").strip()
        if not text:
            return "unknown"
        if text == "unknown":
            return "unknown"
        if "." in text:
            parts = text.split(".")
            if len(parts) == 4:
                return f"{parts[0]}.{parts[1]}.{parts[2]}.*"
            return text
        if ":" in text:
            parts = text.split(":")
            prefix = ":".join(parts[:4]).strip(":")
            return f"{prefix}:*"
        return text

    @staticmethod
    def should_track(path: str) -> bool:
        if not path:
            return False
        blocked_prefixes = ("/api/", "/_nuxt/", "/__nuxt", "/favicon", "/robots.txt")
        if path == "/api":
            return False
        return not path.startswith(blocked_prefixes)

    @staticmethod
    def normalize_ip(raw_ip: str | None) -> str:
        text = str(raw_ip or "").strip()
        if not text:
            return "unknown"
        if text.count(":") == 1 and "." in text and text.rsplit(":", 1)[1].isdigit():
            return text.rsplit(":", 1)[0]
        return text

    async def record_pageview(self, path: str, raw_ip: str) -> None:
        if not self.redis:
            return

        today = datetime.now(timezone.utc).date().isoformat()
        total_key = "analytics:pv:total"
        daily_key = f"analytics:pv:day:{today}"
        page_key = f"analytics:pv:page:{today}"
        ip_key = f"analytics:pv:ip:{today}"
        ttl_seconds = self.RETENTION_DAYS * 24 * 60 * 60

        await self._incr(total_key)
        await self._incr(daily_key)
        await self._hincrby(page_key, path, 1)
        await self._hincrby(ip_key, self.normalize_ip(raw_ip), 1)
        await self._expire(daily_key, ttl_seconds)
        await self._expire(page_key, ttl_seconds)
        await self._expire(ip_key, ttl_seconds)

    async def get_report(self, days: int = 7, top: int = 15) -> dict:
        if not self.redis:
            return self._empty_report(days=days)

        days = max(1, min(int(days), 30))
        top = max(1, min(int(top), 100))
        today = datetime.now(timezone.utc).date()

        daily: list[dict] = []
        merged_pages: dict[str, int] = defaultdict(int)
        merged_raw_ips: dict[str, int] = defaultdict(int)
        total_pv = 0
        today_pv = 0

        for index in range(days):
            day = today - timedelta(days=(days - index - 1))
            day_key = day.isoformat()
            pv_key = f"analytics:pv:day:{day_key}"
            page_key = f"analytics:pv:page:{day_key}"
            ip_key = f"analytics:pv:ip:{day_key}"

            pv = await self._get_int(pv_key)
            page_map = await self._hgetall_int(page_key)
            ip_map = await self._hgetall_int(ip_key)

            daily.append({"date": day_key, "pv": pv})
            total_pv += pv
            if day == today:
                today_pv = pv

            for page, count in page_map.items():
                merged_pages[page] += count
            for ip, count in ip_map.items():
                merged_raw_ips[ip] += count

        geo_by_ip = await self._resolve_geos(list(merged_raw_ips.keys()))
        region_bucket: dict[str, dict[str, int | str]] = {}
        for raw_ip, count in merged_raw_ips.items():
            geo = geo_by_ip.get(raw_ip) or self._unknown_geo()
            label = str(geo.get("label") or "未知")
            existing = region_bucket.get(label)
            if existing is None:
                region_bucket[label] = {
                    "region": label,
                    "pv": int(count),
                    "level": str(geo.get("level") or "unknown"),
                }
            else:
                existing["pv"] = int(existing.get("pv", 0)) + int(count)

        top_pages = [
            {"path": key, "pv": value}
            for key, value in sorted(merged_pages.items(), key=lambda item: (-item[1], item[0]))[:top]
        ]
        top_ips = [
            {
                "ip": self.mask_ip(raw_ip),
                "pv": value,
                "geo_label": str((geo_by_ip.get(raw_ip) or {}).get("label") or "未知"),
                "geo_level": str((geo_by_ip.get(raw_ip) or {}).get("level") or "unknown"),
            }
            for raw_ip, value in sorted(merged_raw_ips.items(), key=lambda item: (-item[1], item[0]))[:top]
        ]
        top_regions = [
            {
                "region": str(item["region"]),
                "pv": int(item["pv"]),
                "level": str(item["level"]),
            }
            for item in sorted(region_bucket.values(), key=lambda row: (-int(row["pv"]), str(row["region"])))[:top]
        ]

        return {
            "window_days": days,
            "total_pv": total_pv,
            "today_pv": today_pv,
            "unique_page_count": len(merged_pages),
            "unique_ip_count": len(merged_raw_ips),
            "daily": daily,
            "top_pages": top_pages,
            "top_ips": top_ips,
            "top_regions": top_regions,
        }

    def _empty_report(self, days: int) -> dict:
        days = max(1, min(int(days), 30))
        today = datetime.now(timezone.utc).date()
        daily = []
        for index in range(days):
            day = today - timedelta(days=(days - index - 1))
            daily.append({"date": day.isoformat(), "pv": 0})
        return {
            "window_days": days,
            "total_pv": 0,
            "today_pv": 0,
            "unique_page_count": 0,
            "unique_ip_count": 0,
            "daily": daily,
            "top_pages": [],
            "top_ips": [],
            "top_regions": [],
        }

    async def _resolve_geos(self, raw_ips: list[str]) -> dict[str, dict]:
        if not raw_ips:
            return {}

        result: dict[str, dict] = {}
        for raw_ip in raw_ips:
            result[raw_ip] = await self._resolve_geo(raw_ip)
        return result

    async def _resolve_geo(self, raw_ip: str) -> dict:
        normalized_ip = self.normalize_ip(raw_ip)
        if normalized_ip == "unknown":
            return self._unknown_geo()
        if self._is_private_ip(normalized_ip):
            return {"label": "内网", "level": "unknown"}

        cache_key = f"analytics:geo:{normalized_ip}"
        cached = await self._get_cached_geo(cache_key)
        if cached is not None:
            return cached

        geo = await self._fetch_geo(normalized_ip)
        await self._set_cached_geo(cache_key, geo)
        return geo

    async def _fetch_geo(self, raw_ip: str) -> dict:
        try:
            url = f"https://ipwho.is/{raw_ip}"
            async with httpx.AsyncClient(timeout=self.GEO_LOOKUP_TIMEOUT) as client:
                response = await client.get(
                    url,
                    params={"fields": "success,country,country_code,region"},
                )
            if response.status_code != 200:
                return self._unknown_geo()
            payload = response.json()
        except Exception:
            return self._unknown_geo()

        if not isinstance(payload, dict):
            return self._unknown_geo()
        if not payload.get("success"):
            return self._unknown_geo()

        country_code = str(payload.get("country_code") or "").upper()
        country = str(payload.get("country") or "").strip()
        region = str(payload.get("region") or "").strip()

        if country_code == "CN":
            province = region or country or "中国"
            return {"label": province, "level": "province"}

        if country:
            return {"label": country, "level": "country"}

        return self._unknown_geo()

    async def _get_cached_geo(self, cache_key: str) -> dict | None:
        if not hasattr(self.redis, "get"):
            return None
        try:
            raw = await self.redis.get(cache_key)
        except Exception:
            return None
        text = self._to_text(raw)
        if not text:
            return None
        try:
            payload = json.loads(text)
        except Exception:
            return None
        if not isinstance(payload, dict):
            return None
        label = str(payload.get("label") or "").strip()
        level = str(payload.get("level") or "").strip()
        if not label:
            return None
        return {"label": label, "level": level or "unknown"}

    async def _set_cached_geo(self, cache_key: str, geo: dict) -> None:
        if not hasattr(self.redis, "setex"):
            return
        try:
            await self.redis.setex(cache_key, self.GEO_CACHE_TTL_SECONDS, json.dumps(geo, ensure_ascii=False))
        except Exception:
            return

    @staticmethod
    def _is_private_ip(raw_ip: str) -> bool:
        try:
            parsed = ipaddress.ip_address(raw_ip)
        except ValueError:
            return True
        return bool(
            parsed.is_private
            or parsed.is_loopback
            or parsed.is_link_local
            or parsed.is_unspecified
            or parsed.is_reserved
            or parsed.is_multicast
        )

    @staticmethod
    def _unknown_geo() -> dict:
        return {"label": "未知", "level": "unknown"}

    async def _incr(self, key: str) -> None:
        if hasattr(self.redis, "incr"):
            await self.redis.incr(key)

    async def _hincrby(self, key: str, field: str, amount: int) -> None:
        if hasattr(self.redis, "hincrby"):
            await self.redis.hincrby(key, field, amount)

    async def _expire(self, key: str, ttl_seconds: int) -> None:
        if hasattr(self.redis, "expire"):
            await self.redis.expire(key, ttl_seconds)

    async def _get_int(self, key: str) -> int:
        if not hasattr(self.redis, "get"):
            return 0
        raw = await self.redis.get(key)
        return self._to_int(raw)

    async def _hgetall_int(self, key: str) -> dict[str, int]:
        if not hasattr(self.redis, "hgetall"):
            return {}
        raw_map = await self.redis.hgetall(key)
        result: dict[str, int] = {}
        for raw_key, raw_value in (raw_map or {}).items():
            key_text = self._to_text(raw_key)
            if not key_text:
                continue
            result[key_text] = self._to_int(raw_value)
        return result

    @staticmethod
    def _to_text(value: Any) -> str:
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="ignore")
        if value is None:
            return ""
        return str(value)

    def _to_int(self, value: Any) -> int:
        text = self._to_text(value).strip()
        if not text:
            return 0
        try:
            return int(float(text))
        except Exception:
            return 0
