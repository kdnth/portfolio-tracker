from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.core.exceptions import PriceUnavailableException

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"


@dataclass
class QuoteResult:
    ticker: str
    price_cents: int
    as_of: datetime


def get_quote(ticker: str) -> QuoteResult:
    """Fetches the current quote for a ticker from Finnhub's /quote endpoint.
    Raises PriceUnavailableException if Finnhub has no quote data for the ticker
    (an unknown/invalid symbol returns HTTP 200 with zeroed-out fields, not a 404)."""
    response = httpx.get(
        f"{FINNHUB_BASE_URL}/quote",
        params={"symbol": ticker, "token": settings.finnhub_api_key},
        timeout=10.0,
    )
    response.raise_for_status()
    data = response.json()

    price = data.get("c")
    timestamp = data.get("t")
    if not price or not timestamp:
        raise PriceUnavailableException(f"No quote data returned for ticker '{ticker}'")

    return QuoteResult(
        ticker=ticker,
        price_cents=round(price * 100),
        as_of=datetime.fromtimestamp(timestamp, tz=timezone.utc),
    )
