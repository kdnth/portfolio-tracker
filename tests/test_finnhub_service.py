from datetime import datetime, timezone

import pytest

from app.core.exceptions import PriceUnavailableException
from app.services import finnhub_service


class FakeResponse:
    def __init__(self, json_data: dict):
        self._json_data = json_data

    def raise_for_status(self):
        pass

    def json(self):
        return self._json_data


def test_get_quote_returns_price_and_timestamp(monkeypatch):
    captured = {}

    def fake_get(url, params, timeout):
        captured["url"] = url
        captured["params"] = params
        return FakeResponse({"c": 261.74, "d": 3.75, "dp": 1.45, "h": 263.0, "l": 258.5, "o": 259.5, "pc": 257.99, "t": 1699029600})

    monkeypatch.setattr(finnhub_service.httpx, "get", fake_get)
    monkeypatch.setattr(finnhub_service.settings, "finnhub_api_key", "test-token")

    result = finnhub_service.get_quote("AAPL")

    assert result.ticker == "AAPL"
    assert result.price_cents == 26174
    assert result.as_of == datetime.fromtimestamp(1699029600, tz=timezone.utc)
    assert captured["params"] == {"symbol": "AAPL", "token": "test-token"}
    assert captured["url"] == f"{finnhub_service.FINNHUB_BASE_URL}/quote"


def test_get_quote_raises_when_ticker_unknown(monkeypatch):
    def fake_get(url, params, timeout):
        return FakeResponse({"c": 0, "d": 0, "dp": 0, "h": 0, "l": 0, "o": 0, "pc": 0, "t": 0})

    monkeypatch.setattr(finnhub_service.httpx, "get", fake_get)

    with pytest.raises(PriceUnavailableException):
        finnhub_service.get_quote("NOTATICKER")
