from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime

class PortfolioCreate(BaseModel):
    name: str = Field(max_length=255)

class PortfolioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    name: str
    created_at: datetime
    updated_at: datetime