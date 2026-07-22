from pydantic import BaseModel, ConfigDict

from datetime import datetime


class HoldingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    portfolio_id: int
    ticker: str
    shares: float
    avg_cost_basis_cents: int
    current_price_cents: int
    last_priced_at: datetime
    created_at: datetime
    updated_at: datetime