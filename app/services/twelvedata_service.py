import logging
import time as time_module
from collections import deque
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from threading import Lock
from zoneinfo import ZoneInfo

import httpx

from app.core.config import settings
from app.core.exceptions import PriceUnavailableException, RateLimitExceededException

TWELVE_DATA_BASE_URL = "https://api.twelvedata.com"
MARKET_CLOSE_ET = time(16, 0)
EASTERN = ZoneInfo("America/New_York")

# Twelve Data's free tier caps at 8 requests/minute (separate from its 800/day credit
# cap). Tracked in-process via a sliding window -- fine for this app's single-process
# deployment; would need a shared store (e.g. Redis) to hold the line across multiple
# worker processes.
RATE_LIMIT_MAX_CALLS = 8
RATE_LIMIT_WINDOW_SECONDS = 60.0

logger = logging.getLogger(__name__)

_call_timestamps: deque[float] = deque()
_rate_limit_lock = Lock()


@dataclass
class DailyClose:
    ticker: str
    price_cents: int
    as_of: datetime


def _check_rate_limit(ticker: str) -> None:
    """Raises RateLimitExceededException, without making a network call, if calling now
    would push us over Twelve Data's 8-requests/minute free-tier limit."""
    with _rate_limit_lock:
        now = time_module.monotonic()
        while _call_timestamps and now - _call_timestamps[0] >= RATE_LIMIT_WINDOW_SECONDS:
            _call_timestamps.popleft()
        if len(_call_timestamps) >= RATE_LIMIT_MAX_CALLS:
            raise RateLimitExceededException(
                f"Twelve Data rate limit reached ({RATE_LIMIT_MAX_CALLS}/{RATE_LIMIT_WINDOW_SECONDS:.0f}s) "
                f"while fetching '{ticker}'"
            )
        _call_timestamps.append(now)


def get_daily_history(ticker: str, days: int = 30) -> list[DailyClose]:
    """Fetches the most recent `days` daily closes for a ticker from Twelve Data's
    /time_series endpoint. Each close is timestamped at that day's 4pm ET (market close).
    Raises PriceUnavailableException if Twelve Data has no data for the ticker or returns
    an error-shaped response body (some error conditions come back as HTTP 200).
    Raises RateLimitExceededException, without calling out to Twelve Data at all, if
    doing so would exceed the free-tier rate limit."""
    _check_rate_limit(ticker)

    response = httpx.get(
        f"{TWELVE_DATA_BASE_URL}/time_series",
        params={
            "symbol": ticker,
            "interval": "1day",
            "outputsize": days,
            "apikey": settings.twelve_data_api_key,
        },
        timeout=10.0,
    )
    response.raise_for_status()
    data = response.json()

    if data.get("status") != "ok" or "values" not in data:
        raise PriceUnavailableException(f"No historical data returned for ticker '{ticker}'")

    results = []
    for row in data["values"]:
        trade_date = date.fromisoformat(row["datetime"])
        as_of = datetime.combine(trade_date, MARKET_CLOSE_ET, tzinfo=EASTERN).astimezone(timezone.utc)
        results.append(
            DailyClose(ticker=ticker, price_cents=round(float(row["close"]) * 100), as_of=as_of)
        )

    return results
