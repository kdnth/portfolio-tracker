from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import NoSuchElementException
from app.core.scheduler import MARKET_TIMEZONE
from app.models import Holding, PortfolioSnapshot, PriceSnapshot
from app.schemas.performance import HoldingDailyOHLC, PerformanceRange

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


def _get_holding_snapshots(
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


def get_holding_performance(
    db: Session, portfolio_id: int, holding_id: int, range_: PerformanceRange
) -> list[PriceSnapshot]:
    """Returns raw PriceSnapshot rows for this holding's ticker, oldest first -- one point per
    sample, no aggregation. Used for 1D only; see get_holding_performance_daily for 1W/1M.
    Raises NoSuchElementException if the holding doesn't exist or doesn't belong to portfolio_id."""
    return _get_holding_snapshots(db, portfolio_id, holding_id, range_)


def get_holding_performance_daily(
    db: Session, portfolio_id: int, holding_id: int, range_: PerformanceRange
) -> list[HoldingDailyOHLC]:
    """Returns one open/close/high/low aggregate per calendar day (in US market local time)
    for this holding, within the requested range -- for 1W/1M, per the product spec's "Chart
    range behavior" section. Groups whatever PriceSnapshot rows exist for the ticker; doesn't
    care whether a given day's rows came from backfill or live polling -- a day with more
    samples (live-polled) just derives a more accurate high/low than a day with fewer
    (backfilled) as a natural side effect, not a special case.
    Raises NoSuchElementException if the holding doesn't exist or doesn't belong to portfolio_id."""
    snapshots = _get_holding_snapshots(db, portfolio_id, holding_id, range_)

    daily_groups: dict[date, list[PriceSnapshot]] = defaultdict(list)
    for snapshot in snapshots:
        local_date = snapshot.as_of.astimezone(MARKET_TIMEZONE).date()
        daily_groups[local_date].append(snapshot)

    results = []
    for day in sorted(daily_groups):
        rows = daily_groups[day]  # already oldest-first within the day, from the ordered query
        prices = [row.price_cents for row in rows]
        results.append(
            HoldingDailyOHLC(
                date=day,
                open_cents=rows[0].price_cents,
                close_cents=rows[-1].price_cents,
                high_cents=max(prices),
                low_cents=min(prices),
            )
        )

    return results
