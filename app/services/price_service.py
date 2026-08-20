import logging
from collections import defaultdict
from datetime import datetime, timezone

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.exceptions import PriceUnavailableException, RateLimitExceededException
from app.models import Holding, PortfolioSnapshot, PriceSnapshot
from app.services.finnhub_service import QuoteResult, get_quote
from app.services.twelvedata_service import DailyClose, get_daily_history

logger = logging.getLogger(__name__)


def list_actively_held_tickers(db: Session) -> list[str]:
    """Returns distinct tickers with a nonzero share count across all holdings, portfolio-agnostic.
    Fully-sold positions are excluded so the poll cycle doesn't spend API calls pricing them."""
    rows = db.query(Holding.ticker).filter(Holding.shares > 0).distinct().all()
    return [row[0] for row in rows]


def _record_price_snapshot(db: Session, quote: QuoteResult | DailyClose) -> None:
    """Writes a PriceSnapshot row for the quote, silently skipping if one already exists
    for this (ticker, as_of) pair -- Finnhub returns the last trade's timestamp, which can
    repeat across polls when a ticker hasn't traded since the previous cycle."""
    stmt = (
        pg_insert(PriceSnapshot)
        .values(ticker=quote.ticker, price_cents=quote.price_cents, as_of=quote.as_of)
        .on_conflict_do_nothing(index_elements=["ticker", "as_of"])
    )
    db.execute(stmt)


def _update_holdings_for_ticker(db: Session, quote: QuoteResult) -> None:
    """Updates current_price_cents/last_priced_at on every holding for this ticker, across all portfolios."""
    db.query(Holding).filter(Holding.ticker == quote.ticker).update(
        {"current_price_cents": quote.price_cents, "last_priced_at": quote.as_of}
    )


def _record_portfolio_snapshots(db: Session, as_of: datetime) -> None:
    """Sums current market value per portfolio from its holdings and writes one
    PortfolioSnapshot per portfolio that has an actively-held position."""
    holdings = db.query(Holding).filter(Holding.shares > 0).all()
    totals: dict[int, float] = defaultdict(float)
    for holding in holdings:
        totals[holding.portfolio_id] += float(holding.shares) * holding.current_price_cents

    for portfolio_id, total_cents in totals.items():
        db.add(
            PortfolioSnapshot(
                portfolio_id=portfolio_id,
                total_market_value_cents=round(total_cents),
                as_of=as_of,
            )
        )


def backfill_ticker_history_if_new(db: Session, ticker: str) -> None:
    """If no PriceSnapshot exists yet for this ticker anywhere in the app, backfills the
    most recent 30 daily closes from Twelve Data. A failure here (bad symbol, rate limit,
    network error) is logged and swallowed, never raised -- this is an enrichment step, not
    part of the core trade-recording operation it's called from. Doesn't commit; the caller's
    own transaction covers any rows staged here."""
    already_tracked = db.query(PriceSnapshot).filter(PriceSnapshot.ticker == ticker).first() is not None
    if already_tracked:
        return

    try:
        daily_closes = get_daily_history(ticker)
    except RateLimitExceededException:
        logger.warning(
            "Historical backfill skipped for ticker '%s': Twelve Data rate limit reached "
            "(will retry on the next trade recorded for this ticker)",
            ticker,
        )
        return
    except (PriceUnavailableException, httpx.HTTPError):
        logger.warning("Historical backfill unavailable for new ticker '%s'", ticker)
        return

    for daily_close in daily_closes:
        _record_price_snapshot(db, daily_close)

    logger.info("Backfilled %d day(s) of history for new ticker '%s'", len(daily_closes), ticker)


def poll_and_record_prices(db: Session) -> list[str]:
    """Polls Finnhub for every actively-held ticker, records a PriceSnapshot per successful
    quote, updates each affected Holding's current price, and writes a PortfolioSnapshot per
    affected portfolio. A ticker Finnhub has no data for, or that errors over the network, is
    skipped rather than aborting the rest of the cycle. Returns the list of skipped tickers."""
    poll_time = datetime.now(timezone.utc)
    failed_tickers: list[str] = []

    for ticker in list_actively_held_tickers(db):
        try:
            quote = get_quote(ticker)
        except (PriceUnavailableException, httpx.HTTPError):
            failed_tickers.append(ticker)
            continue

        _record_price_snapshot(db, quote)
        _update_holdings_for_ticker(db, quote)

    _record_portfolio_snapshots(db, poll_time)
    db.commit()
    return failed_tickers
