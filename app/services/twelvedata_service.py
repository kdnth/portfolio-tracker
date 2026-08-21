import logging
import time as time_module
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from zoneinfo import ZoneInfo

import httpx

from app.core.config import settings
from app.core.exceptions import PriceUnavailableException, RateLimitExceededException

TWELVE_DATA_BASE_URL = "https://api.twelvedata.com"
DEFAULT_EXCHANGE_TIMEZONE = "America/New_York"
# ~7 hourly bars/trading day * ~22 trading days/month, plus slack for holidays/weekends.
DEFAULT_OUTPUTSIZE = 250

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
class HistoricalBar:
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


def get_historical_bars(ticker: str, outputsize: int = DEFAULT_OUTPUTSIZE) -> list[HistoricalBar]:
    """Fetches up to `outputsize` recent hourly bars for a ticker from Twelve Data's
    /time_series endpoint (the default covers roughly 30 calendar days at ~7 trading bars/
    day). Each bar is timestamped using its own reported datetime, localized to the
    exchange's timezone (from the response's meta.exchange_timezone) and converted to UTC
    -- never a synthesized time.

    Bars for the current, not-yet-closed trading day are dropped: Twelve Data's "today"
    entry is provisional (confirmed live -- mid-session, it's byte-identical to the latest
    completed bar), not a real close, and stamping it with any fixed time would be
    fabricating data for a trading day that hasn't finished. Live Finnhub polling owns
    "today" for any actively-tracked ticker instead.

    Raises PriceUnavailableException if Twelve Data has no data for the ticker or returns
    an error-shaped response body (some error conditions come back as HTTP 200).
    Raises RateLimitExceededException, without calling out to Twelve Data at all, if
    doing so would exceed the free-tier rate limit."""
    _check_rate_limit(ticker)

    response = httpx.get(
        f"{TWELVE_DATA_BASE_URL}/time_series",
        params={
            "symbol": ticker,
            "interval": "1h",
            "outputsize": outputsize,
            "apikey": settings.twelve_data_api_key,
        },
        timeout=10.0,
    )
    response.raise_for_status()
    data = response.json()

    if data.get("status") != "ok" or "values" not in data:
        raise PriceUnavailableException(f"No historical data returned for ticker '{ticker}'")

    exchange_tz = ZoneInfo(data.get("meta", {}).get("exchange_timezone", DEFAULT_EXCHANGE_TIMEZONE))
    today_local = datetime.now(exchange_tz).date()

    results = []
    for row in data["values"]:
        local_dt = datetime.fromisoformat(row["datetime"]).replace(tzinfo=exchange_tz)
        if local_dt.date() >= today_local:
            continue  # provisional bar for a trading day that hasn't closed yet

        results.append(
            HistoricalBar(
                ticker=ticker,
                price_cents=round(float(row["close"]) * 100),
                as_of=local_dt.astimezone(timezone.utc),
            )
        )

    return results
