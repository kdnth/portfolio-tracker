from datetime import datetime

from sqlalchemy.orm import Session

from app.core.time_utils import start_of_today_utc
from app.models import DemoAnalysisRequestLog

DAILY_DEMO_LIMIT = 2


def count_demo_analyses_today(db: Session, ip_address: str, now: datetime | None = None) -> int:
    """Returns how many demo analyses this IP address has had recorded since UTC midnight
    today. `now` is exposed for tests; defaults to the real current time."""
    cutoff = start_of_today_utc(now)
    return (
        db.query(DemoAnalysisRequestLog)
        .filter(DemoAnalysisRequestLog.ip_address == ip_address, DemoAnalysisRequestLog.created_at >= cutoff)
        .count()
    )


def record_demo_analysis(db: Session, ip_address: str) -> None:
    """Records that this IP just ran a demo analysis, for quota counting. Does not commit;
    the caller's own transaction covers the row staged here."""
    db.add(DemoAnalysisRequestLog(ip_address=ip_address))
