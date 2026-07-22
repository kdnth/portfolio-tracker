from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.exceptions import NoSuchElementException
from app.db.session import get_db
from app.models import User
from app.schemas.holding import HoldingResponse
from app.services.holding_service import list_holdings_for_portfolio
from app.services.portfolio_service import get_owned_portfolio

router = APIRouter(prefix="/portfolios/{portfolio_id}/holdings", tags=["holdings"])

@router.get("/", response_model=list[HoldingResponse])
def list_holdings_route(portfolio_id: int, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    try:
        get_owned_portfolio(db=db, user_id=current_user.id, portfolio_id=portfolio_id)
    except NoSuchElementException:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    return list_holdings_for_portfolio(db=db, portfolio_id=portfolio_id)
