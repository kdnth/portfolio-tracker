from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

PerformanceRange = Literal["1D", "1W", "1M"]


class PricePoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    as_of: datetime
    price_cents: int


class PortfolioValuePoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    as_of: datetime
    total_market_value_cents: int
