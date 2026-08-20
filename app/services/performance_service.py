from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import NoSuchElementException
from app.models import Holding, PortfolioSnapshot, PriceSnapshot
from app.schemas.performance import PerformanceRange

RANGE_WINDOWS: dict[PerformanceRange, timedelta] = {
    "1D": timedelta(days=1),
    "1W": timedelta(weeks=1),
    "1M": timedelta(days=30),
}


def _range_cutoff(range_: PerformanceRange) -> datetime:
    return datetime.now(timezone.utc) - RANGE_WINDOWS[range_]


def get_portfolio_performance(db: Session, portfolio_id: int, range_: PerformanceRange) -> list[PortfolioSnapshot]:
    """Returns this portfolio's PortfolioSnapshot rows within the requested range, oldest first."""
    cutoff = _range_cutoff(range_)
    return (
        db.query(PortfolioSnapshot)
        .filter(PortfolioSnapshot.portfolio_id == portfolio_id, PortfolioSnapshot.as_of >= cutoff)
        .order_by(PortfolioSnapshot.as_of.asc())
        .all()
    )


def get_holding_performance(
    db: Session, portfolio_id: int, holding_id: int, range_: PerformanceRange
) -> list[PriceSnapshot]:
    """Returns PriceSnapshot rows for this holding's ticker within the requested range, oldest first.
    Raises NoSuchElementException if the holding doesn't exist or doesn't belong to portfolio_id."""
    holding = db.get(Holding, holding_id)
    if holding is None or holding.portfolio_id != portfolio_id:
        raise NoSuchElementException("Holding not found")

    cutoff = _range_cutoff(range_)
    return (
        db.query(PriceSnapshot)
        .filter(PriceSnapshot.ticker == holding.ticker, PriceSnapshot.as_of >= cutoff)
        .order_by(PriceSnapshot.as_of.asc())
        .all()
    )
