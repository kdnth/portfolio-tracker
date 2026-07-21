from fastapi import APIRouter, status, HTTPException, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.exceptions import NoSuchElementException
from app.db.session import get_db
from app.models.user import User
from app.schemas.portfolio import PortfolioResponse, PortfolioCreate
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
