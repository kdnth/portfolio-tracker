import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

from app.db.session import SessionLocal
from app.services.price_service import poll_and_record_prices

logger = logging.getLogger(__name__)

MARKET_TIMEZONE = ZoneInfo("America/New_York")
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)
POLL_INTERVAL_MINUTES = 15

scheduler = BackgroundScheduler()


def is_market_hours(now: datetime | None = None) -> bool:
    """Returns True if `now` (default: current time) falls within regular US equity market
    hours -- 9:30am-4:00pm ET, Monday-Friday. No holiday calendar; a fixed weekday/time
    window only, per the product spec's accepted trade-off."""
    now = (now or datetime.now(MARKET_TIMEZONE)).astimezone(MARKET_TIMEZONE)
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    return MARKET_OPEN <= now.time() < MARKET_CLOSE


def run_poll_job() -> None:
    """Scheduler entry point: no-ops outside market hours, otherwise runs one poll cycle
    against a fresh DB session (the scheduler thread doesn't share a request-scoped session)."""
    if not is_market_hours():
        return

    db = SessionLocal()
    try:
        failed_tickers = poll_and_record_prices(db)
        if failed_tickers:
            logger.warning("Price poll skipped tickers with no quote data: %s", failed_tickers)
    finally:
        db.close()


def start_scheduler() -> None:
    scheduler.add_job(run_poll_job, "interval", minutes=POLL_INTERVAL_MINUTES, id="finnhub_price_poll")
    scheduler.start()


def stop_scheduler() -> None:
    scheduler.shutdown(wait=False)
