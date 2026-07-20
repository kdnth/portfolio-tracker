from sqlalchemy import String, Integer, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime

from app.db.session import Base
from app.models.base import TimestampMixin

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.portfolio import Portfolio
    from app.models.trade import Trade


class Holding(Base, TimestampMixin):
    __tablename__ = "holdings"
    id: Mapped[int] = mapped_column(primary_key=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id", ondelete="CASCADE"), index=True)
    ticker: Mapped[str] = mapped_column(String(5), index=True)
    shares: Mapped[float] = mapped_column(Numeric(precision=16, scale=6))
    avg_cost_basis_cents: Mapped[int] = mapped_column(Integer)
    current_price_cents: Mapped[int] = mapped_column(Integer)
    last_priced_at: Mapped[datetime] = mapped_column()

    portfolio: Mapped["Portfolio"] = relationship(back_populates="holdings")
    trades: Mapped[list["Trade"]] = relationship(back_populates="holding")