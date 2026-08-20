from sqlalchemy import String, Integer, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.db.session import Base
from app.models.base import TimestampMixin


class PriceSnapshot(Base, TimestampMixin):
    __tablename__ = "price_snapshots"
    __table_args__ = (UniqueConstraint("ticker", "as_of", name="uq_price_snapshots_ticker_as_of"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ticker: Mapped[str] = mapped_column(String(5), index=True)
    price_cents: Mapped[int] = mapped_column(Integer)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
