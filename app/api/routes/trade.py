from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.core.exceptions import NoSuchElementException
from app.db.session import get_db
from app.models import User
from app.schemas.trade import TradeResponse, TradeCreate
from app.services.portfolio_service import get_owned_portfolio
from app.services.trade_service import create_trade

router = APIRouter(prefix="/portfolios/{portfolio_id}/trades", tags=["trades"])

@router.post("/", response_model=TradeResponse, status_code=status.HTTP_201_CREATED)
def create_trade_route(
        portfolio_id: int,
        payload: TradeCreate,
        current_user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
):
    try:
        get_owned_portfolio(db=db, user_id=current_user.id, portfolio_id=portfolio_id)
    except NoSuchElementException:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Portfolio not found")

    try:
        return create_trade(db=db, portfolio_id=portfolio_id, payload=payload)
    except NoSuchElementException:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot sell more shares than held")



