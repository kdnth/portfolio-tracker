from sqlalchemy.orm import Session

from app.core.exceptions import NoSuchElementException
from app.models import Trade, Holding
from app.models.trade import TradeOptions
from app.schemas.trade import TradeCreate


def create_trade(db: Session, portfolio_id: int, payload: TradeCreate) -> Trade:
    """Records a new trade against a portfolio. This will either create or update the matching Holding's aggregate share count and average cost basis.
    Raises NoSuchElementException if attempting to sell more shares than are held."""
    holding = (
        db.query(Holding).filter(Holding.portfolio_id == portfolio_id, Holding.ticker == payload.ticker).first()
    )
    if holding is None:
        holding = Holding(
            portfolio_id=portfolio_id,
            ticker=payload.ticker,
            shares=0,
            avg_cost_basis_cents=0,
            current_price_cents=payload.price_per_share_cents
        )
        db.add(holding)
        db.flush()

    if payload.trade_type == TradeOptions.BUY:
        total_existing_cost = holding.shares * holding.avg_cost_basis_cents
        total_new_cost = payload.shares * payload.price_per_share_cents
        new_total_shares = holding.shares + payload.shares

        holding.avg_cost_basis_cents = int(
            (total_existing_cost + total_new_cost) / new_total_shares
        )
        holding.shares = new_total_shares
    else: # sell
        if payload.shares > holding.shares:
            raise NoSuchElementException()
        holding.shares -= payload.shares

    trade = Trade(
        holding_id=holding.id,
        trade_type=payload.trade_type,
        shares=payload.shares,
        price_per_share_cents=payload.price_per_share_cents,
        executed_at=payload.executed_at
    )
    db.add(trade)
    db.commit()
    db.refresh(trade)
    return trade
