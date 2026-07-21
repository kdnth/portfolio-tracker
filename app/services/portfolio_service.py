from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.portfolio import Portfolio
from app.schemas.portfolio import PortfolioCreate, PortfolioResponse


def create_portfolio(db: Session, user_id: int, payload: PortfolioCreate) -> Portfolio:
    portfolio = Portfolio(user_id=user_id, name=payload.name)
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    return portfolio

def list_portfolios_for_user(db: Session, user_id: int) -> list[PortfolioResponse]:
    return db.query(Portfolio).filter(Portfolio.user_id == user_id)

def get_owned_portfolio(db: Session, user_id: int, portfolio_id: int) -> Portfolio:
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
    if portfolio.user_id != user_id:
        # 404 not 403 to prevent information leak
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    return portfolio