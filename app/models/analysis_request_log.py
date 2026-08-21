from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.base import TimestampMixin


class AnalysisRequestLog(Base, TimestampMixin):
    """One row per analysis actually run for an authenticated user -- never per attempt
    rejected by the quota. created_at (from TimestampMixin) is the counted timestamp; see
    app/services/analysis_quota_service.py."""

    __tablename__ = "analysis_request_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    portfolio_id: Mapped[int] = mapped_column(ForeignKey("portfolios.id", ondelete="CASCADE"))
