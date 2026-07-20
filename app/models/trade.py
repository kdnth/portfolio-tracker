import enum

from sqlalchemy import ForeignKey, Enum, Numeric, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import  datetime

from app.db.session import Base
from app.models.base import TimestampMixin
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.holding import Holding

class TradeOptions(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"

class Trade(Base, TimestampMixin):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    holding_id: Mapped[int] = mapped_column(ForeignKey("holdings.id"))
    trade_type: Mapped[TradeOptions] = mapped_column(Enum(TradeOptions))
    shares: Mapped[float] = mapped_column(Numeric(precision=18, scale=6))
    price_per_share_cents: Mapped[int] = mapped_column(Integer)
    executed_at: Mapped[datetime] = mapped_column()

    holding: Mapped["Holding"] = relationship(back_populates="trades")
