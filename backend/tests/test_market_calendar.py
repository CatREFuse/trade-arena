from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.services.market_calendar import MarketCalendarService, xcals


def _utc(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


def test_cn_market_open_and_lunch_break():
    svc = MarketCalendarService()

    assert svc.is_trade_open("cn", _utc(2026, 3, 30, 2, 0))  # 10:00 CST
    assert not svc.is_trade_open("cn", _utc(2026, 3, 30, 3, 45))  # 11:45 CST
    assert not svc.is_trade_open("cn", _utc(2026, 3, 30, 10, 30))  # 18:30 CST


def test_us_market_regular_and_pre_market():
    svc = MarketCalendarService()

    assert not svc.is_trade_open("us", _utc(2026, 3, 30, 12, 0))  # 08:00 ET
    assert svc.is_trade_open("us", _utc(2026, 3, 30, 14, 0))  # 10:00 ET


def test_next_open_for_cn_during_lunch_break():
    svc = MarketCalendarService()
    lunch_break = _utc(2026, 3, 30, 3, 45)  # 11:45 CST

    next_open = svc.next_open_at("cn", lunch_break)

    assert next_open is not None
    assert next_open.astimezone(timezone.utc).isoformat() == _utc(2026, 3, 30, 5, 0).isoformat()  # 13:00 CST


@pytest.mark.skipif(xcals is None, reason="exchange_calendars not installed")
def test_us_holiday_is_closed():
    svc = MarketCalendarService()
    # 2026-12-25 (US holiday), 15:00 ET would be open on normal weekdays
    assert not svc.is_trade_open("us", _utc(2026, 12, 25, 20, 0))


def test_market_status_uses_short_ttl_cache(monkeypatch):
    class FakeCalendar:
        def __init__(self):
            self.calls = 0

        def is_open_on_minute(self, _timestamp):
            self.calls += 1
            return True

    svc = MarketCalendarService()
    fake_calendar = FakeCalendar()
    monkeypatch.setattr(svc, "_calendar", lambda _market: fake_calendar)

    assert svc.is_trade_open("us") is True
    assert svc.is_trade_open("us") is True
    assert fake_calendar.calls == 1


def test_session_windows_supports_display_timezone():
    svc = MarketCalendarService()
    windows = svc.session_windows(
        "us",
        now_utc=_utc(2026, 3, 30, 14, 0),  # 10:00 ET
        display_timezone_name="Asia/Shanghai",
    )
    assert windows == ["21:30-04:00(+1)"]


def test_now_local_iso_supports_display_timezone():
    svc = MarketCalendarService()
    now_local = svc.now_local_iso(
        "us",
        now_utc=_utc(2026, 3, 30, 14, 0),  # 22:00 CST
        display_timezone_name="Asia/Shanghai",
    )
    assert now_local == "2026-03-30T22:00:00+08:00"
