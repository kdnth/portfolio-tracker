from datetime import datetime, timezone

import pytest

from app.core.exceptions import PriceUnavailableException
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
