import anthropic
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_client_ip
from app.core.exceptions import NoSuchElementException
from app.db.session import get_db
from app.models import Portfolio
from app.schemas.agent import DemoAnalysisResponse
from app.schemas.holding import HoldingResponse
from app.schemas.performance import HoldingDailyOHLC, PerformanceRange, PortfolioValuePoint, PricePoint
from app.schemas.portfolio import PortfolioResponse
from app.services.agent_service import analyze_portfolio
from app.services.demo_quota_service import DAILY_DEMO_LIMIT, count_demo_analyses_today, record_demo_analysis
from app.services.holding_service import list_holdings_for_portfolio
from app.services.performance_service import (
    get_holding_performance,
    get_holding_performance_daily,
    get_portfolio_performance,
)

router = APIRouter(prefix="/demo", tags=["demo"])


def _demo_portfolio_id() -> int:
    """Raises 503 rather than 404 when unconfigured -- this isn't "not found," it's "the
    operator hasn't run scripts/seed_demo_portfolio.py yet."""
    if settings.demo_portfolio_id is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="The demo isn't configured yet."
        )
    return settings.demo_portfolio_id


@router.get("/portfolio", response_model=PortfolioResponse)
def get_demo_portfolio_route(db: Session = Depends(get_db)):
    portfolio = db.get(Portfolio, _demo_portfolio_id())
    if portfolio is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="The demo isn't configured yet."
        )
    return portfolio


@router.get("/holdings", response_model=list[HoldingResponse])
def list_demo_holdings_route(db: Session = Depends(get_db)):
    return list_holdings_for_portfolio(db=db, portfolio_id=_demo_portfolio_id())


@router.get("/performance", response_model=list[PortfolioValuePoint])
def get_demo_performance_route(range: PerformanceRange = "1M", db: Session = Depends(get_db)):
    return get_portfolio_performance(db=db, portfolio_id=_demo_portfolio_id(), range_=range)


@router.get("/holdings/{holding_id}/performance", response_model=list[PricePoint] | list[HoldingDailyOHLC])
def get_demo_holding_performance_route(holding_id: int, range: PerformanceRange = "1M", db: Session = Depends(get_db)):
    portfolio_id = _demo_portfolio_id()
    try:
        if range == "1D":
            return get_holding_performance(db=db, portfolio_id=portfolio_id, holding_id=holding_id, range_=range)
        return get_holding_performance_daily(db=db, portfolio_id=portfolio_id, holding_id=holding_id, range_=range)
    except NoSuchElementException:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Holding not found")


@router.post("/analyze", response_model=DemoAnalysisResponse)
def analyze_demo_portfolio_route(request: Request, db: Session = Depends(get_db)):
    portfolio_id = _demo_portfolio_id()
    ip_address = get_client_ip(request)

    used_today = count_demo_analyses_today(db, ip_address)
    if used_today >= DAILY_DEMO_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"The live demo is limited to {DAILY_DEMO_LIMIT} analyses per day per visitor, "
                "to keep this project's API costs sane. Resets at midnight UTC."
            ),
        )

    try:
        report = analyze_portfolio(db=db, portfolio_id=portfolio_id)
    except anthropic.APIError:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The demo analysis is temporarily unavailable. Please try again.",
        )

    record_demo_analysis(db, ip_address)
    db.commit()

    remaining = max(DAILY_DEMO_LIMIT - used_today - 1, 0)
    return DemoAnalysisResponse(report=report, demo_analyses_remaining_today=remaining)
