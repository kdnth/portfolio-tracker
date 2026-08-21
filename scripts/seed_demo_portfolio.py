"""One-off script: seeds a fixed demo portfolio for the public landing page's live analysis
demo (see docs/PRODUCT_SPEC.md, "Public landing page"). Idempotent -- rerunning just reports
the existing demo portfolio's id instead of creating a duplicate; delete the demo user/
portfolio manually first if you want to regenerate its data (e.g. once the synthetic window
has aged out).

The demo endpoints (GET /demo/portfolio, POST /demo/analyze) call the exact same service
code real users hit -- no separate/fake code path. What's different is the *data*: the
demo's holdings use fictional placeholder-company ticker symbols (Contoso/Fabrikam/
Northwind/AdventureWorks -- the standard placeholder names used across the software
industry for demo data) with entirely synthetic, generated price history, rather than real
tickers. This is deliberate: PriceSnapshot is a shared table keyed by ticker across every
user in the app, so fabricating history for a real ticker (e.g. AAPL) would corrupt real
users' charts for that same ticker. Fictional tickers side-step that entirely, at the small,
accepted cost that the demo can no longer piggyback on real users' live-tracked history --
see list_actively_held_tickers() in app/services/price_service.py, which excludes this
portfolio from the live-polling scheduler for the same reason (there's no real market quote
to poll for a fictional company).

Because there's no live polling for these tickers, this seed is a one-time snapshot, not an
ever-growing history -- the synthetic window will gradually age past the 30-day chart range
over the following month. Re-run (after deleting the old demo user) to regenerate a fresh
window when that happens. A scheduled auto-refresh job was considered and deliberately
deferred as unnecessary complexity for a marketing demo page.

After running with --execute, put the printed id in DEMO_PORTFOLIO_ID (env var / .env).

Usage:
    python -m scripts.seed_demo_portfolio             # dry run
    python -m scripts.seed_demo_portfolio --execute   # create (or report existing)
"""

import argparse
import logging
import random
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Portfolio, PortfolioSnapshot, PriceSnapshot, Trade, User
from app.models.holding import Holding
from app.models.trade import TradeOptions

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

DEMO_USERNAME = "demo_portfolio_owner"
DEMO_EMAIL = "demo@portfolio-tracker.internal"
DEMO_PORTFOLIO_NAME = "Demo Portfolio"

MARKET_TZ = ZoneInfo("America/New_York")
MARKET_HOURS = [(9, 30), (10, 30), (11, 30), (12, 30), (13, 30), (14, 30), (15, 30)]
WINDOW_DAYS = 40  # comfortably covers the 1M (30-day) chart range with margin
RANDOM_SEED = 20260821  # fixed so reruns (after a manual reset) look the same

# ticker, start price (cents), daily drift (mean fractional change/day), daily volatility
# (stdev fractional change/day), total shares -- each ticker deliberately tells a different
# story so the analysis has real, varied patterns to describe.
DEMO_TICKERS = [
    ("CTSO", 8000, 0.0015, 0.008, 40),  # steady moderate uptrend, low volatility
    ("FBRKM", 15000, -0.0020, 0.012, 25),  # declining trend
    ("NWIND", 5000, 0.0000, 0.025, 60),  # high volatility, roughly flat overall
    ("ADVWK", 12000, 0.0035, 0.015, 30),  # strong uptrend, still volatile
]


def _market_hour_timestamps(now: datetime) -> list[datetime]:
    """Synthetic 'market hours' timestamps (7/day, weekdays only) from WINDOW_DAYS ago
    through today, never past `now` -- so a partial "today" looks like a session in
    progress rather than fabricating the future."""
    timestamps = []
    day = (now - timedelta(days=WINDOW_DAYS)).astimezone(MARKET_TZ).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    end = now.astimezone(MARKET_TZ)
    while day.date() <= end.date():
        if day.weekday() < 5:
            for hour, minute in MARKET_HOURS:
                candidate = day.replace(hour=hour, minute=minute)
                if candidate <= end:
                    timestamps.append(candidate)
        day += timedelta(days=1)
    return timestamps


def _generate_price_series(
    rng: random.Random, start_price_cents: int, daily_drift: float, daily_volatility: float, bar_count: int
) -> list[int]:
    """One synthetic price (cents) per bar via a per-bar random walk, scaling the given
    daily drift/volatility down to ~7 bars/trading day."""
    bar_drift = daily_drift / len(MARKET_HOURS)
    bar_volatility = daily_volatility / (len(MARKET_HOURS) ** 0.5)
    price = float(start_price_cents)
    series = []
    for _ in range(bar_count):
        change = rng.gauss(bar_drift, bar_volatility)
        price = max(price * (1 + change), 100)  # floor at $1.00, never zero/negative
        series.append(round(price))
    return series


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute", action="store_true", help="Actually create the demo portfolio (default: dry run)"
    )
    args = parser.parse_args()

    db = SessionLocal()
    try:
        existing_user = db.query(User).filter(User.username == DEMO_USERNAME).first()
        if existing_user is not None:
            portfolio = db.query(Portfolio).filter(Portfolio.user_id == existing_user.id).first()
            logger.info(
                "Demo portfolio already exists -- nothing to do. DEMO_PORTFOLIO_ID=%d "
                "(delete the '%s' user manually first if you want to regenerate it)",
                portfolio.id,
                DEMO_USERNAME,
            )
            return

        if not args.execute:
            logger.info(
                "DRY RUN -- would create demo user '%s' and a portfolio with %d fictional "
                "holdings and synthetic price history. Pass --execute to apply.",
                DEMO_USERNAME,
                len(DEMO_TICKERS),
            )
            return

        rng = random.Random(RANDOM_SEED)
        now = datetime.now(timezone.utc)
        timestamps = _market_hour_timestamps(now)

        user = User(
            username=DEMO_USERNAME,
            email=DEMO_EMAIL,
            # Unusable password -- this account is never logged into. It's only ever
            # referenced by its fixed portfolio_id, from the public demo endpoints.
            password_hash=hash_password(secrets.token_urlsafe(32)),
        )
        db.add(user)
        db.flush()

        portfolio = Portfolio(user_id=user.id, name=DEMO_PORTFOLIO_NAME)
        db.add(portfolio)
        db.flush()

        portfolio_totals = [0] * len(timestamps)

        for ticker, start_price_cents, daily_drift, daily_volatility, total_shares in DEMO_TICKERS:
            series = _generate_price_series(rng, start_price_cents, daily_drift, daily_volatility, len(timestamps))

            db.add_all(
                PriceSnapshot(ticker=ticker, price_cents=price, as_of=ts.astimezone(timezone.utc))
                for ts, price in zip(timestamps, series)
            )

            for i, price in enumerate(series):
                portfolio_totals[i] += round(total_shares * price)

            # Two buys per ticker (60% up front, 40% partway through the window) so the
            # trade-history tool has real entries and avg_cost_basis is a genuine weighted
            # average, not an arbitrarily flat number.
            first_shares = round(total_shares * 0.6, 4)
            second_shares = round(total_shares - first_shares, 4)
            midpoint = len(timestamps) // 2

            holding = Holding(
                portfolio_id=portfolio.id,
                ticker=ticker,
                shares=Decimal(str(total_shares)),
                avg_cost_basis_cents=round(
                    (first_shares * series[0] + second_shares * series[midpoint]) / total_shares
                ),
                current_price_cents=series[-1],
                last_priced_at=timestamps[-1],
            )
            db.add(holding)
            db.flush()

            db.add_all(
                [
                    Trade(
                        holding_id=holding.id,
                        trade_type=TradeOptions.BUY,
                        shares=Decimal(str(first_shares)),
                        price_per_share_cents=series[0],
                        executed_at=timestamps[0],
                    ),
                    Trade(
                        holding_id=holding.id,
                        trade_type=TradeOptions.BUY,
                        shares=Decimal(str(second_shares)),
                        price_per_share_cents=series[midpoint],
                        executed_at=timestamps[midpoint],
                    ),
                ]
            )

        db.add_all(
            PortfolioSnapshot(portfolio_id=portfolio.id, total_market_value_cents=total, as_of=ts.astimezone(timezone.utc))
            for ts, total in zip(timestamps, portfolio_totals)
        )

        db.commit()
        logger.info(
            "Created demo portfolio with %d fictional holdings and %d synthetic price points each. "
            "Set DEMO_PORTFOLIO_ID=%d",
            len(DEMO_TICKERS),
            len(timestamps),
            portfolio.id,
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
