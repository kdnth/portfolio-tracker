from pydantic import BaseModel, Field, ConfigDict

from app.models.trade import TradeOptions
from datetime import datetime


class TradeCreate(BaseModel):
    ticker: str = Field(min_length=1, max_length=5)
    trade_type: TradeOptions
    shares: float = Field(gt=0)
    price_per_share_cents: int = Field(gt=0)
    executed_at: datetime


class TradeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    holding_id: int
    trade_type: TradeOptions
    shares: float
    price_per_share_cents: int
    executed_at: datetime
    created_at: datetime