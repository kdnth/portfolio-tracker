from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from app.core.exceptions import PriceUnavailableException, RateLimitExceededException
from app.services import twelvedata_service

EASTERN = ZoneInfo("America/New_York")


class FakeResponse:
    def __init__(self, json_data: dict, status_code: int = 200):
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        pass

    def json(self):
        return self._json_data


def _et_date_string(days_ago: int) -> str:
    return (datetime.now(EASTERN) - timedelta(days=days_ago)).strftime("%Y-%m-%d")


def test_get_historical_bars_parses_each_bars_own_timestamp(monkeypatch):
    captured = {}
    yesterday = _et_date_string(1)

    def fake_get(url, params, timeout):
        captured["url"] = url
        captured["params"] = params
        return FakeResponse(
            {
                "meta": {"symbol": "AAPL", "exchange_timezone": "America/New_York"},
                "status": "ok",
                "values": [
                    {"datetime": f"{yesterday} 15:30:00", "open": "310", "high": "312", "low": "309", "close": "311.34", "volume": "1"},
                    {"datetime": f"{yesterday} 14:30:00", "open": "309", "high": "311", "low": "308", "close": "310.13", "volume": "1"},
                ],
            }
        )

    monkeypatch.setattr(twelvedata_service.httpx, "get", fake_get)
    monkeypatch.setattr(twelvedata_service.settings, "twelve_data_api_key", "test-token")

    results = twelvedata_service.get_historical_bars("AAPL", outputsize=2)

    assert len(results) == 2
    assert results[0].ticker == "AAPL"
    assert results[0].price_cents == 31134
    expected_as_of = (
        datetime.fromisoformat(f"{yesterday} 15:30:00").replace(tzinfo=EASTERN).astimezone(timezone.utc)
    )
    assert results[0].as_of == expected_as_of
    assert results[1].price_cents == 31013
    assert captured["params"] == {
        "symbol": "AAPL",
        "interval": "1h",
        "outputsize": 2,
        "apikey": "test-token",
    }


def test_get_historical_bars_excludes_todays_provisional_bar(monkeypatch):
    today = _et_date_string(0)
    yesterday = _et_date_string(1)

    def fake_get(url, params, timeout):
        return FakeResponse(
            {
                "meta": {"exchange_timezone": "America/New_York"},
                "status": "ok",
                "values": [
                    # Twelve Data's entry for the still-open trading day -- provisional, must be dropped.
                    {"datetime": f"{today} 12:30:00", "open": "1", "high": "1", "low": "1", "close": "300", "volume": "1"},
                    {"datetime": f"{yesterday} 15:30:00", "open": "1", "high": "1", "low": "1", "close": "310.13", "volume": "1"},
                ],
            }
        )

    monkeypatch.setattr(twelvedata_service.httpx, "get", fake_get)

    results = twelvedata_service.get_historical_bars("AAPL")

    assert len(results) == 1
    assert results[0].price_cents == 31013  # only the completed, prior-day bar survives


def test_get_historical_bars_defaults_exchange_timezone_when_meta_omits_it(monkeypatch):
    yesterday = _et_date_string(1)

    def fake_get(url, params, timeout):
        return FakeResponse(
            {
                "status": "ok",  # no "meta" key at all
                "values": [
                    {"datetime": f"{yesterday} 15:30:00", "open": "1", "high": "1", "low": "1", "close": "100", "volume": "1"},
                ],
            }
        )

    monkeypatch.setattr(twelvedata_service.httpx, "get", fake_get)

    results = twelvedata_service.get_historical_bars("AAPL")

    assert len(results) == 1  # doesn't crash without meta.exchange_timezone


def test_get_historical_bars_raises_on_error_status(monkeypatch):
    def fake_get(url, params, timeout):
        return FakeResponse({"code": 404, "message": "invalid symbol", "status": "error"})

    monkeypatch.setattr(twelvedata_service.httpx, "get", fake_get)

    with pytest.raises(PriceUnavailableException):
        twelvedata_service.get_historical_bars("NOTATICKER")


def test_rate_limit_blocks_calls_beyond_the_free_tier_cap(monkeypatch):
    call_count = 0

    def fake_get(url, params, timeout):
        nonlocal call_count
        call_count += 1
        return FakeResponse({"status": "ok", "values": []})

    monkeypatch.setattr(twelvedata_service.httpx, "get", fake_get)

    for _ in range(twelvedata_service.RATE_LIMIT_MAX_CALLS):
        twelvedata_service.get_historical_bars("AAPL")

    assert call_count == twelvedata_service.RATE_LIMIT_MAX_CALLS

    with pytest.raises(RateLimitExceededException):
        twelvedata_service.get_historical_bars("AAPL")

    # the rejected call never reached the network
    assert call_count == twelvedata_service.RATE_LIMIT_MAX_CALLS


def test_rate_limit_allows_calls_again_once_the_window_has_passed(monkeypatch):
    monkeypatch.setattr(
        twelvedata_service.httpx, "get", lambda url, params, timeout: FakeResponse({"status": "ok", "values": []})
    )

    fake_now = 1000.0
    monkeypatch.setattr(twelvedata_service.time_module, "monotonic", lambda: fake_now)

    for _ in range(twelvedata_service.RATE_LIMIT_MAX_CALLS):
        twelvedata_service.get_historical_bars("AAPL")

    with pytest.raises(RateLimitExceededException):
        twelvedata_service.get_historical_bars("AAPL")

    fake_now += twelvedata_service.RATE_LIMIT_WINDOW_SECONDS + 1
    monkeypatch.setattr(twelvedata_service.time_module, "monotonic", lambda: fake_now)

    twelvedata_service.get_historical_bars("AAPL")  # doesn't raise -- window has rolled over
