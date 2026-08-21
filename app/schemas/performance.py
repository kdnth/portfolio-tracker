from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

PerformanceRange = Literal["1D", "1W", "1M"]


class PricePoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    as_of: datetime
    price_cents: int


class HoldingDailyOHLC(BaseModel):
    """One day's derived open/close/high/low for a holding's 1W/1M chart -- aggregated from
    whatever PriceSnapshot rows exist that day, not exact intraday records. See the product
    spec's "Chart range behavior" section.

    close_cents is null specifically for the current day while the market is still open --
    there is no real close yet, and showing the latest live price as if it were one would
    misrepresent an in-progress session as a settled value."""

    model_config = ConfigDict(from_attributes=True)
    date: date
    open_cents: int
    close_cents: int | None
    high_cents: int
    low_cents: int


class PortfolioValuePoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    as_of: datetime
    total_market_value_cents: int
