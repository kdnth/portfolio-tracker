from datetime import datetime
from zoneinfo import ZoneInfo

from app.core.scheduler import MARKET_TIMEZONE, is_market_hours

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


def test_market_hours_true_during_weekday_trading_window():
    tuesday_mid_session = datetime(2026, 8, 18, 12, 0, tzinfo=ET)  # Tue, noon ET
    assert is_market_hours(tuesday_mid_session) is True


def test_market_hours_true_exactly_at_open():
    tuesday_open = datetime(2026, 8, 18, 9, 30, tzinfo=ET)
    assert is_market_hours(tuesday_open) is True


def test_market_hours_false_before_open():
    tuesday_early = datetime(2026, 8, 18, 9, 0, tzinfo=ET)
    assert is_market_hours(tuesday_early) is False


def test_market_hours_false_at_close():
    tuesday_close = datetime(2026, 8, 18, 16, 0, tzinfo=ET)
    assert is_market_hours(tuesday_close) is False


def test_market_hours_false_on_weekend():
    saturday_mid_session = datetime(2026, 8, 22, 12, 0, tzinfo=ET)  # Sat
    assert is_market_hours(saturday_mid_session) is False


def test_market_hours_converts_from_other_timezones():
    # 2026-08-18 is in EDT (UTC-4); 14:00 UTC == 10:00 ET, inside the trading window
    tuesday_utc = datetime(2026, 8, 18, 14, 0, tzinfo=UTC)
    assert is_market_hours(tuesday_utc) is True

    # same clock time in UTC, but outside the window once converted to ET
    tuesday_utc_early = datetime(2026, 8, 18, 9, 0, tzinfo=UTC)
    assert is_market_hours(tuesday_utc_early) is False


def test_market_timezone_is_new_york():
    assert MARKET_TIMEZONE.key == "America/New_York"
