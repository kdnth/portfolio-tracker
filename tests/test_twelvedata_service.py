from datetime import datetime, timezone

import pytest

from app.core.exceptions import PriceUnavailableException, RateLimitExceededException
from app.services import twelvedata_service


class FakeResponse:
    def __init__(self, json_data: dict, status_code: int = 200):
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self):
        pass

    def json(self):
        return self._json_data


def test_get_daily_history_returns_closes_newest_first(monkeypatch):
    captured = {}

    def fake_get(url, params, timeout):
        captured["url"] = url
        captured["params"] = params
        return FakeResponse(
            {
                "meta": {"symbol": "AAPL"},
                "status": "ok",
                "values": [
                    {"datetime": "2026-08-20", "open": "317.45", "high": "320.28", "low": "310.65", "close": "311.34", "volume": "80658545"},
                    {"datetime": "2026-08-19", "open": "310.13", "high": "319.28", "low": "309.60", "close": "316.83", "volume": "50009121"},
                ],
            }
        )

    monkeypatch.setattr(twelvedata_service.httpx, "get", fake_get)
    monkeypatch.setattr(twelvedata_service.settings, "twelve_data_api_key", "test-token")

    results = twelvedata_service.get_daily_history("AAPL", days=2)

    assert len(results) == 2
    assert results[0].ticker == "AAPL"
    assert results[0].price_cents == 31134
    assert results[0].as_of == datetime(2026, 8, 20, 20, 0, tzinfo=timezone.utc)  # 4pm EDT -> 20:00 UTC
    assert results[1].price_cents == 31683
    assert captured["params"] == {
        "symbol": "AAPL",
        "interval": "1day",
        "outputsize": 2,
        "apikey": "test-token",
    }


def test_get_daily_history_raises_on_error_status(monkeypatch):
    def fake_get(url, params, timeout):
        return FakeResponse({"code": 404, "message": "invalid symbol", "status": "error"})

    monkeypatch.setattr(twelvedata_service.httpx, "get", fake_get)

    with pytest.raises(PriceUnavailableException):
        twelvedata_service.get_daily_history("NOTATICKER")


def test_rate_limit_blocks_calls_beyond_the_free_tier_cap(monkeypatch):
    call_count = 0

    def fake_get(url, params, timeout):
        nonlocal call_count
        call_count += 1
        return FakeResponse({"status": "ok", "values": []})

    monkeypatch.setattr(twelvedata_service.httpx, "get", fake_get)

    for _ in range(twelvedata_service.RATE_LIMIT_MAX_CALLS):
        twelvedata_service.get_daily_history("AAPL")

    assert call_count == twelvedata_service.RATE_LIMIT_MAX_CALLS

    with pytest.raises(RateLimitExceededException):
        twelvedata_service.get_daily_history("AAPL")

    # the rejected call never reached the network
    assert call_count == twelvedata_service.RATE_LIMIT_MAX_CALLS


def test_rate_limit_allows_calls_again_once_the_window_has_passed(monkeypatch):
    monkeypatch.setattr(
        twelvedata_service.httpx, "get", lambda url, params, timeout: FakeResponse({"status": "ok", "values": []})
    )

    fake_now = 1000.0
    monkeypatch.setattr(twelvedata_service.time_module, "monotonic", lambda: fake_now)

    for _ in range(twelvedata_service.RATE_LIMIT_MAX_CALLS):
        twelvedata_service.get_daily_history("AAPL")

    with pytest.raises(RateLimitExceededException):
        twelvedata_service.get_daily_history("AAPL")

    fake_now += twelvedata_service.RATE_LIMIT_WINDOW_SECONDS + 1
    monkeypatch.setattr(twelvedata_service.time_module, "monotonic", lambda: fake_now)

    twelvedata_service.get_daily_history("AAPL")  # doesn't raise -- window has rolled over
