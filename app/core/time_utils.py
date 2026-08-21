from datetime import datetime, timezone


def start_of_today_utc(now: datetime | None = None) -> datetime:
    """Returns UTC midnight for `now` (default: the real current time) -- the fixed daily
    reset boundary shared by the authenticated and demo analysis quotas."""
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)
