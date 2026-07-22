from sqlalchemy.orm import Session

from app.models import Holding


def list_holdings_for_portfolio(db: Session, portfolio_id: int) -> list[Holding]:
    """Queries DB for holdings belonging to provided portfolio. Returns list of Holdings or empty list if none."""
    return db.query(Holding).filter(Holding.portfolio_id == portfolio_id)