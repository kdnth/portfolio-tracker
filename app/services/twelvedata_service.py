from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from zoneinfo import ZoneInfo

import httpx

from app.core.config import settings
from app.core.exceptions import PriceUnavailableException

TWELVE_DATA_BASE_URL = "https://api.twelvedata.com"
MARKET_CLOSE_ET = time(16, 0)
EASTERN = ZoneInfo("America/New_York")


@dataclass
class DailyClose:
    ticker: str
    price_cents: int
    as_of: datetime


def get_daily_history(ticker: str, days: int = 30) -> list[DailyClose]:
    """Fetches the most recent `days` daily closes for a ticker from Twelve Data's
    /time_series endpoint. Each close is timestamped at that day's 4pm ET (market close).
    Raises PriceUnavailableException if Twelve Data has no data for the ticker or returns
    an error-shaped response body (some error conditions come back as HTTP 200)."""
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
