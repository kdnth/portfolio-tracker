from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models import AnalysisRequestLog

DAILY_ANALYSIS_LIMIT = 3


def _start_of_today_utc(now: datetime | None = None) -> datetime:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def count_analyses_today(db: Session, user_id: int, now: datetime | None = None) -> int:
    """Returns how many analyses this user has had recorded since UTC midnight today.
    `now` is exposed for tests; defaults to the real current time."""
    cutoff = _start_of_today_utc(now)
    return (
        db.query(AnalysisRequestLog)
        .filter(AnalysisRequestLog.user_id == user_id, AnalysisRequestLog.created_at >= cutoff)
        .count()
    )


def record_analysis(db: Session, user_id: int, portfolio_id: int) -> None:
    """Records that this user just ran an analysis, for quota counting. Does not commit;
    the caller's own transaction covers the row staged here."""
    db.add(AnalysisRequestLog(user_id=user_id, portfolio_id=portfolio_id))
