"""One-off maintenance script: re-backfills tickers still carrying pre-5.2 backfill data.

Before the 5.2 fix, historical backfill fetched one daily bar per day, stamped with a
synthesized timestamp, instead of real hourly bars. `backfill_ticker_history_if_new` only
ever backfills a ticker once (guarded on "does any PriceSnapshot already exist for it"), so
any ticker first tracked before 5.2 shipped is stuck with that old, coarse data forever --
its 1W/1M chart shows only one data point per historical day, which is exactly the "four
lines only look distinct on the most recent day" bug for that ticker specifically.

A day with exactly one PriceSnapshot row is the fingerprint of the old bug: the new hourly
backfill produces ~7 rows/trading day, and live 15-min polling produces far more. A single
row on a real trading day more than two days in the past (days this recent are excluded so
an ticker's first partial day of live tracking is never misdiagnosed as stale) means that
day was never touched by anything but the old code path.

For each ticker with at least one such day, this script deletes those single-row days and
re-fetches fresh hourly bars from Twelve Data via the same get_historical_bars() the regular
backfill path uses -- ON CONFLICT DO NOTHING means any timestamp that happens to coincide
with already-good data is naturally skipped, not duplicated.

Defaults to a dry run (reports what it would do, touches nothing). Pass --execute to
actually delete and re-backfill. Optionally pass --tickers to scope to specific symbols
(comma-separated) instead of scanning every tracked ticker -- useful for testing against one
symbol before running it against everything.

Usage:
    python -m scripts.rebackfill_stale_tickers                  # dry run, all tickers
    python -m scripts.rebackfill_stale_tickers --tickers AAPL   # dry run, one ticker
    python -m scripts.rebackfill_stale_tickers --execute        # actually re-backfill
"""

import argparse
import logging
import time as time_module
from collections import defaultdict
from datetime import date, datetime, timedelta

import httpx

from app.core.exceptions import PriceUnavailableException, RateLimitExceededException
from app.core.scheduler import MARKET_TIMEZONE
from app.db.session import SessionLocal
from app.models import PriceSnapshot
from app.services.price_service import _record_price_snapshot
from app.services.twelvedata_service import get_historical_bars

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

# Days this recent are never flagged stale -- a ticker only just starting to be live-polled
# can legitimately have a single sample on its first day or two of real tracking.
STALE_CHECK_CUTOFF_DAYS = 2

# Twelve Data's free tier caps at 8 requests/minute; get_historical_bars() enforces this
# itself and raises rather than blocking, so this script paces its own calls comfortably
# under that instead of relying on retries.
SECONDS_BETWEEN_TICKERS = 8.0


def _find_stale_tickers(db) -> dict[str, list[date]]:
    """Returns {ticker: [stale_date, ...]} for every ticker with at least one day, older
    than STALE_CHECK_CUTOFF_DAYS, carrying exactly one PriceSnapshot row."""
    cutoff_date = (datetime.now(MARKET_TIMEZONE) - timedelta(days=STALE_CHECK_CUTOFF_DAYS)).date()

    rows = db.query(PriceSnapshot.ticker, PriceSnapshot.as_of).all()
    daily_counts: dict[str, dict[date, int]] = defaultdict(lambda: defaultdict(int))
    for ticker, as_of in rows:
        local_date = as_of.astimezone(MARKET_TIMEZONE).date()
        daily_counts[ticker][local_date] += 1

    stale: dict[str, list[date]] = {}
    for ticker, counts_by_date in daily_counts.items():
        stale_dates = sorted(d for d, count in counts_by_date.items() if count == 1 and d < cutoff_date)
        if stale_dates:
            stale[ticker] = stale_dates

    return stale


def _rebackfill_ticker(db, ticker: str, stale_dates: list[date], execute: bool) -> None:
    logger.info(
        "  %s: %d stale day(s) (%s .. %s)",
        ticker,
        len(stale_dates),
        stale_dates[0].isoformat(),
        stale_dates[-1].isoformat(),
    )

    if not execute:
        return

    stale_date_set = set(stale_dates)
    ticker_rows = db.query(PriceSnapshot).filter(PriceSnapshot.ticker == ticker).all()
    stale_ids = [row.id for row in ticker_rows if row.as_of.astimezone(MARKET_TIMEZONE).date() in stale_date_set]

    deleted = (
        db.query(PriceSnapshot)
        .filter(PriceSnapshot.id.in_(stale_ids))
        .delete(synchronize_session=False)
    )

    try:
        bars = get_historical_bars(ticker)
    except RateLimitExceededException:
        logger.warning("  %s: rate limit reached, skipping re-backfill (rerun the script to retry)", ticker)
        db.rollback()
        return
    except (PriceUnavailableException, httpx.HTTPError) as exc:
        logger.warning("  %s: re-backfill fetch failed (%s), skipping", ticker, exc)
        db.rollback()
        return

    for bar in bars:
        _record_price_snapshot(db, bar)

    db.commit()
    logger.info("  %s: deleted %d stale row(s), inserted %d fresh bar(s)", ticker, deleted, len(bars))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute", action="store_true", help="Actually delete stale rows and re-backfill (default: dry run)"
    )
    parser.add_argument(
        "--tickers", type=str, default=None, help="Comma-separated tickers to scope to (default: all tracked)"
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        stale = _find_stale_tickers(db)

        if args.tickers:
            wanted = {t.strip().upper() for t in args.tickers.split(",")}
            stale = {ticker: dates for ticker, dates in stale.items() if ticker in wanted}

        if not stale:
            logger.info("No stale tickers found.")
            return

        mode = "EXECUTING" if args.execute else "DRY RUN (pass --execute to actually apply)"
        logger.info("%s -- %d stale ticker(s) found:", mode, len(stale))

        for ticker in sorted(stale):
            _rebackfill_ticker(db, ticker, stale[ticker], args.execute)
            if args.execute:
                time_module.sleep(SECONDS_BETWEEN_TICKERS)
    finally:
        db.close()


if __name__ == "__main__":
    main()
