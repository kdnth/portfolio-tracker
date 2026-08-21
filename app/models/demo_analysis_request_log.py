from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import TimestampMixin


class DemoAnalysisRequestLog(Base, TimestampMixin):
    """One row per analysis run against the public demo endpoint, keyed by IP address --
    there's no account to key off since the demo is unauthenticated. See
    app/services/demo_quota_service.py."""

    __tablename__ = "demo_analysis_request_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    ip_address: Mapped[str] = mapped_column(String(45), index=True)  # 45 chars fits IPv6
