from sqlalchemy.orm import Session

from app.core.exceptions import NoSuchElementException
from app.models.portfolio import Portfolio
from app.schemas.portfolio import PortfolioCreate


def create_portfolio(db: Session, user_id: int, payload: PortfolioCreate) -> Portfolio:
    """Creates new portfolio in DB. Returns created Portfolio."""
    portfolio = Portfolio(user_id=user_id, name=payload.name)
    db.add(portfolio)
    db.commit()
    db.refresh(portfolio)
    return portfolio

def list_portfolios_for_user(db: Session, user_id: int) -> list[Portfolio]:
    """Queries DB for portfolios belonging to User with matching user_id. Returns list of Portfolios or empty list if none exist."""
    return db.query(Portfolio).filter(Portfolio.user_id == user_id).all()

def get_owned_portfolio(db: Session, user_id: int, portfolio_id: int) -> Portfolio:
    """Queries DB for portfolio with matching user_id and portfolio_id. Returns matching Portfolio.
    Raises NoSuchElementException if portfolio doesn't exist or portfolio doesn't belong to user."""
    portfolio = db.get(Portfolio, portfolio_id)
    if portfolio is None:
        raise NoSuchElementException("Portfolio not found")
    if portfolio.user_id != user_id:
        raise NoSuchElementException("Portfolio not found")

    return portfolio