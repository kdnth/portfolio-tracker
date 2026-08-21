from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.agent import AnalysisQuotaResponse
from app.schemas.user import UserResponse
from app.services.analysis_quota_service import DAILY_ANALYSIS_LIMIT, count_analyses_today

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserResponse)
def get_current_user_route(current_user: User=Depends(get_current_user)):
    return current_user

@router.get("/me/analysis-quota", response_model=AnalysisQuotaResponse)
def get_analysis_quota_route(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    used_today = count_analyses_today(db, current_user.id)
    remaining = None if current_user.is_admin else max(DAILY_ANALYSIS_LIMIT - used_today, 0)
    return AnalysisQuotaResponse(limit=DAILY_ANALYSIS_LIMIT, used_today=used_today, remaining=remaining)