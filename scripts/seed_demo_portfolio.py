"""One-off script: seeds a fixed demo portfolio for the public landing page's live analysis
demo (see docs/PRODUCT_SPEC.md, "Public landing page"). Idempotent -- rerunning just reports
the existing demo portfolio's id instead of creating a duplicate.

The demo endpoints (GET /demo/portfolio, POST /demo/analyze) call the exact same service
code real users hit, bound to this one fixed portfolio_id -- no separate/fake data path.

Tickers are chosen because they're common and likely already actively tracked by real
users -- if so, backfill_ticker_history_if_new() is a no-op (it only ever backfills a
ticker's very first tracking, anywhere in the app) and the demo gets real historical chart
data immediately instead of waiting on its own fresh 30-day backfill.

After running with --execute, put the printed id in DEMO_PORTFOLIO_ID (env var / .env).

Usage:
    python -m scripts.seed_demo_portfolio             # dry run
    python -m scripts.seed_demo_portfolio --execute   # create (or report existing)
"""

import argparse
import logging
import secrets
from datetime import datetime, timedelta, timezone

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models import Portfolio, User
from app.models.trade import TradeOptions
from app.schemas.trade import TradeCreate
from app.services.trade_service import create_trade

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

DEMO_USERNAME = "demo_portfolio_owner"
DEMO_EMAIL = "demo@portfolio-tracker.internal"
DEMO_PORTFOLIO_NAME = "Demo Portfolio"

# ticker, shares, price_per_share_cents, days_ago
DEMO_TRADES = [
    ("AAPL", 12, 18000, 75),
    ("MSFT", 6, 39500, 60),
    ("GOOGL", 10, 15500, 45),
    ("WMT", 20, 6800, 30),
]


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
            logger.info("Demo portfolio already exists -- nothing to do. DEMO_PORTFOLIO_ID=%d", portfolio.id)
            return

        if not args.execute:
            logger.info(
                "DRY RUN -- would create demo user '%s' and a portfolio with %d trade(s). "
                "Pass --execute to apply.",
                DEMO_USERNAME,
                len(DEMO_TRADES),
            )
            return

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

        now = datetime.now(timezone.utc)
        for ticker, shares, price_cents, days_ago in DEMO_TRADES:
            create_trade(
                db,
                portfolio.id,
                TradeCreate(
                    ticker=ticker,
                    trade_type=TradeOptions.BUY,
                    shares=shares,
                    price_per_share_cents=price_cents,
                    executed_at=now - timedelta(days=days_ago),
                ),
            )

        logger.info(
            "Created demo portfolio with %d trade(s). Set DEMO_PORTFOLIO_ID=%d",
            len(DEMO_TRADES),
            portfolio.id,
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
