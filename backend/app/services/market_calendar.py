from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

try:
    import pandas as pd
except Exception:  # pragma: no cover - 依赖缺失时走降级逻辑
    pd = None

try:
    import exchange_calendars as xcals
except Exception:  # pragma: no cover - 依赖缺失时走降级逻辑
    xcals = None

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MarketRule:
    market: str
    calendar: str
    timezone_name: str
    sessions: tuple[tuple[time, time], ...]

    @property
    def timezone(self) -> ZoneInfo:
        return ZoneInfo(self.timezone_name)


MARKET_RULES: dict[str, MarketRule] = {
    "us": MarketRule(
        market="us",
        calendar="XNYS",
        timezone_name="America/New_York",
        sessions=((time(9, 30), time(16, 0)),),
    ),
    "cn": MarketRule(
        market="cn",
        calendar="XSHG",
        timezone_name="Asia/Shanghai",
        sessions=((time(9, 30), time(11, 30)), (time(13, 0), time(15, 0))),
    ),
    "hk": MarketRule(
        market="hk",
        calendar="XHKG",
        timezone_name="Asia/Hong_Kong",
        sessions=((time(9, 30), time(12, 0)), (time(13, 0), time(16, 0))),
    ),
}


class MarketCalendarService:
    """统一市场交易时段校验（严格模式优先使用 exchange_calendars）。"""

    STATUS_CACHE_TTL_SECONDS = 15

    def __init__(self):
        self._calendars: dict[str, object] = {}
        self._status_cache: dict[str, tuple[float, bool]] = {}

    def status(self, market: str, now_utc: datetime | None = None) -> str:
        return "open" if self.is_trade_open(market, now_utc=now_utc) else "closed"

    def is_trade_open(self, market: str, now_utc: datetime | None = None) -> bool:
        market = market.lower()
        if now_utc is None:
            cached_status = self._get_cached_status(market)
            if cached_status is not None:
                return cached_status
        now = self._normalize_utc(now_utc)
        rule = self._rule(market)
        if rule is None:
            return False

        calendar = self._calendar(market)
        if calendar is not None and pd is not None:
            try:
                is_open = bool(calendar.is_open_on_minute(pd.Timestamp(now)))
                if now_utc is None:
                    self._set_cached_status(market, is_open)
                return is_open
            except Exception as exc:  # pragma: no cover - 运行时兜底
                logger.warning("calendar is_open_on_minute failed for %s: %s", market, exc)

        is_open = self._is_open_by_clock(rule, now)
        if now_utc is None:
            self._set_cached_status(market, is_open)
        return is_open

    def next_open_at(self, market: str, now_utc: datetime | None = None) -> datetime | None:
        market = market.lower()
        now = self._normalize_utc(now_utc)
        rule = self._rule(market)
        if rule is None:
            return None

        calendar = self._calendar(market)
        same_day_candidate = self._next_open_same_day(rule, now, calendar)
        if same_day_candidate is not None:
            return same_day_candidate

        if calendar is not None and pd is not None:
            ts = pd.Timestamp(now)
            for getter in (self._next_open_with_next_open, self._next_open_with_session):
                candidate = getter(calendar, ts)
                if candidate is not None:
                    return candidate

        return self._next_open_by_clock(rule, now)

    def now_local_iso(self, market: str, now_utc: datetime | None = None) -> str | None:
        rule = self._rule(market.lower())
        if rule is None:
            return None
        now = self._normalize_utc(now_utc).astimezone(rule.timezone)
        return now.isoformat(timespec="seconds")

    def next_open_local_iso(self, market: str, now_utc: datetime | None = None) -> str | None:
        rule = self._rule(market.lower())
        if rule is None:
            return None
        next_open = self.next_open_at(market, now_utc=now_utc)
        if next_open is None:
            return None
        return next_open.astimezone(rule.timezone).isoformat(timespec="seconds")

    def timezone_name(self, market: str) -> str | None:
        rule = self._rule(market.lower())
        if rule is None:
            return None
        return rule.timezone_name

    def session_windows(self, market: str) -> list[str]:
        rule = self._rule(market.lower())
        if rule is None:
            return []
        return [f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}" for start, end in rule.sessions]

    def _calendar(self, market: str):
        if xcals is None:
            return None
        if market not in self._calendars:
            rule = self._rule(market)
            if rule is None:
                return None
            try:
                self._calendars[market] = xcals.get_calendar(rule.calendar)
            except Exception as exc:  # pragma: no cover - 运行时兜底
                logger.warning("load exchange calendar failed for %s: %s", market, exc)
                self._calendars[market] = None
        return self._calendars.get(market)

    def _get_cached_status(self, market: str) -> bool | None:
        cached = self._status_cache.get(market)
        if not cached:
            return None

        cached_at, is_open = cached
        now = datetime.now(timezone.utc).timestamp()
        if now - cached_at > self.STATUS_CACHE_TTL_SECONDS:
            self._status_cache.pop(market, None)
            return None
        return is_open

    def _set_cached_status(self, market: str, is_open: bool) -> None:
        self._status_cache[market] = (datetime.now(timezone.utc).timestamp(), is_open)

    @staticmethod
    def _normalize_utc(now_utc: datetime | None) -> datetime:
        if now_utc is None:
            return datetime.now(timezone.utc)
        if now_utc.tzinfo is None:
            return now_utc.replace(tzinfo=timezone.utc)
        return now_utc.astimezone(timezone.utc)

    @staticmethod
    def _to_utc_datetime(value) -> datetime | None:
        if value is None:
            return None
        if hasattr(value, "to_pydatetime"):
            value = value.to_pydatetime()
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return None

    def _next_open_with_next_open(self, calendar, ts):
        if not hasattr(calendar, "next_open"):
            return None
        try:
            return self._to_utc_datetime(calendar.next_open(ts))
        except Exception:
            return None

    def _next_open_with_session(self, calendar, ts):
        if not hasattr(calendar, "minute_to_session") or not hasattr(calendar, "session_open"):
            return None
        try:
            session = calendar.minute_to_session(ts, direction="next")
            return self._to_utc_datetime(calendar.session_open(session))
        except Exception:
            return None

    @staticmethod
    def _rule(market: str) -> MarketRule | None:
        return MARKET_RULES.get(market)

    def _is_open_by_clock(self, rule: MarketRule, now_utc: datetime) -> bool:
        now_local = now_utc.astimezone(rule.timezone)
        if now_local.weekday() >= 5:
            return False
        now_local_time = now_local.time()
        for start, end in rule.sessions:
            if start <= now_local_time < end:
                return True
        return False

    def _next_open_by_clock(self, rule: MarketRule, now_utc: datetime) -> datetime | None:
        now_local = now_utc.astimezone(rule.timezone)
        now_local_time = now_local.time()

        if now_local.weekday() < 5:
            for start, end in rule.sessions:
                if start <= now_local_time < end:
                    return now_utc
                if now_local_time < start:
                    next_local = datetime.combine(now_local.date(), start, tzinfo=rule.timezone)
                    return next_local.astimezone(timezone.utc)

        for offset in range(1, 15):
            future_day = now_local.date() + timedelta(days=offset)
            probe = datetime.combine(future_day, time(12, 0), tzinfo=rule.timezone)
            if probe.weekday() >= 5:
                continue
            next_local = datetime.combine(future_day, rule.sessions[0][0], tzinfo=rule.timezone)
            return next_local.astimezone(timezone.utc)
        return None

    def _next_open_same_day(self, rule: MarketRule, now_utc: datetime, calendar) -> datetime | None:
        now_local = now_utc.astimezone(rule.timezone)
        if now_local.weekday() >= 5:
            return None

        if calendar is not None and pd is not None and not self._is_session_date(calendar, now_local.date()):
            return None

        now_local_time = now_local.time()
        for start, end in rule.sessions:
            if start <= now_local_time < end:
                return now_utc
            if now_local_time < start:
                next_local = datetime.combine(now_local.date(), start, tzinfo=rule.timezone)
                return next_local.astimezone(timezone.utc)
        return None

    @staticmethod
    def _is_session_date(calendar, day) -> bool:
        if not hasattr(calendar, "is_session") or pd is None:
            return True
        try:
            return bool(calendar.is_session(pd.Timestamp(day)))
        except Exception:
            return True
