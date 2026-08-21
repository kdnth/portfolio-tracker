import anthropic
from fastapi import APIRouter, status, HTTPException, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.exceptions import NoSuchElementException
from app.db.session import get_db
from app.models.user import User
from app.schemas.agent import AnalysisResponse
from app.schemas.performance import PerformanceRange, PortfolioValuePoint
from app.schemas.portfolio import PortfolioResponse, PortfolioCreate
from app.services.agent_service import analyze_portfolio
from app.services.analysis_quota_service import DAILY_ANALYSIS_LIMIT, count_analyses_today, record_analysis
from app.services.performance_service import get_portfolio_performance
from app.services.portfolio_service import create_portfolio, get_owned_portfolio, list_portfolios_for_user

router = APIRouter(prefix="/portfolios", tags=["portfolios"])

@router.post("/", response_model=PortfolioResponse, status_code=status.HTTP_201_CREATED)
def create_portfolio_route(payload: PortfolioCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    portfolio = create_portfolio(db=db, user_id=current_user.id, payload=payload)
    return portfolio

@router.get("/{portfolio_id}", response_model=PortfolioResponse)
def get_portfolio_route(portfolio_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        portfolio = get_owned_portfolio(db=db, user_id=current_user.id, portfolio_id=portfolio_id)
    except NoSuchElementException:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Portfolio does not exist"
        )
    return portfolio


@router.get("/", response_model=list[PortfolioResponse])
def get_portfolios_route(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return list_portfolios_for_user(db=db, user_id=current_user.id)

@router.get("/{portfolio_id}/performance", response_model=list[PortfolioValuePoint])
def get_portfolio_performance_route(
        portfolio_id: int,
        range: PerformanceRange = "1M",
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    try:
        get_owned_portfolio(db=db, user_id=current_user.id, portfolio_id=portfolio_id)
    except NoSuchElementException:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    return get_portfolio_performance(db=db, portfolio_id=portfolio_id, range_=range)

@router.post("/{portfolio_id}/analyze", response_model=AnalysisResponse)
def analyze_portfolio_route(
        portfolio_id: int,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
):
    try:
        get_owned_portfolio(db=db, user_id=current_user.id, portfolio_id=portfolio_id)
    except NoSuchElementException:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    used_today = count_analyses_today(db, current_user.id)
    if not current_user.is_admin and used_today >= DAILY_ANALYSIS_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily analysis limit reached ({DAILY_ANALYSIS_LIMIT}/day). Resets at midnight UTC.",
        )

    try:
        report = analyze_portfolio(db=db, portfolio_id=portfolio_id)
    except anthropic.APIError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Analysis is temporarily unavailable. Please try again.",
        )

    record_analysis(db, current_user.id, portfolio_id)
    db.commit()

    remaining = None if current_user.is_admin else max(DAILY_ANALYSIS_LIMIT - used_today - 1, 0)
    return AnalysisResponse(report=report, analyses_remaining_today=remaining)
