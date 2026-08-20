from sqlalchemy import Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.db.session import Base
from app.models.base import TimestampMixin

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.portfolio import Portfolio


class PortfolioSnapshot(Base, TimestampMixin):
    __tablename__ = "portfolio_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id", ondelete="CASCADE"), index=True)
    total_market_value_cents: Mapped[int] = mapped_column(Integer)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    portfolio: Mapped["Portfolio"] = relationship(back_populates="portfolio_snapshots")
