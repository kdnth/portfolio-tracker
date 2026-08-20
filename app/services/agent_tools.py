from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Holding, Trade
from app.schemas.performance import PerformanceRange
from app.services.performance_service import RANGE_WINDOWS, get_holding_performance


def _holding_market_value_cents(shares: Decimal, current_price_cents: int) -> int:
    return round(shares * current_price_cents)


def _holding_cost_basis_cents(shares: Decimal, avg_cost_basis_cents: int) -> int:
    return round(shares * avg_cost_basis_cents)


def get_holdings(db: Session, portfolio_id: int) -> list[dict]:
    """Returns every holding in this portfolio: ticker, shares, avg cost basis, current
    price, market value, and unrealized gain/loss in both dollars and percent."""
    holdings = db.query(Holding).filter(Holding.portfolio_id == portfolio_id).all()

    results = []
    for holding in holdings:
        market_value_cents = _holding_market_value_cents(holding.shares, holding.current_price_cents)
        cost_basis_cents = _holding_cost_basis_cents(holding.shares, holding.avg_cost_basis_cents)
        gain_cents = market_value_cents - cost_basis_cents
        gain_percent = (gain_cents / cost_basis_cents * 100) if cost_basis_cents else 0.0

        results.append(
            {
                "ticker": holding.ticker,
                "shares": float(holding.shares),
                "avg_cost_basis_cents": holding.avg_cost_basis_cents,
                "current_price_cents": holding.current_price_cents,
                "market_value_cents": market_value_cents,
                "unrealized_gain_cents": gain_cents,
                "unrealized_gain_percent": round(gain_percent, 2),
            }
        )

    return results


def get_price_history(db: Session, portfolio_id: int, ticker: str, range: PerformanceRange) -> dict:
    """Returns historical price snapshots for a ticker held in this portfolio. Returns an
    {"error": ...} dict rather than raising if the ticker isn't held here or the range is
    invalid -- lets the model see and react to the problem within the conversation, instead
    of the tool call blowing up the loop."""
    if range not in RANGE_WINDOWS:
        return {"error": f"Invalid range '{range}'. Must be one of: 1D, 1W, 1M."}

    # Tickers are only normalized to uppercase client-side (the trade-entry form), not in
    # the database -- a model-supplied ticker isn't guaranteed to match that casing, and
    # Postgres string equality is case-sensitive.
    ticker = ticker.strip().upper()

    holding = db.query(Holding).filter(Holding.portfolio_id == portfolio_id, Holding.ticker == ticker).first()
    if holding is None:
        return {"error": f"'{ticker}' is not held in this portfolio."}

    snapshots = get_holding_performance(db, portfolio_id, holding.id, range)

    return {
        "ticker": ticker,
        "range": range,
        "prices": [
            {"as_of": snapshot.as_of.isoformat(), "price_cents": snapshot.price_cents}
            for snapshot in snapshots
        ],
    }


def get_trade_history(db: Session, portfolio_id: int, ticker: str | None = None) -> list[dict]:
    """Returns this portfolio's trade history, oldest first, optionally filtered to one ticker."""
    query = db.query(Trade).join(Holding, Trade.holding_id == Holding.id).filter(Holding.portfolio_id == portfolio_id)
    if ticker:
        query = query.filter(Holding.ticker == ticker.strip().upper())

    trades = query.order_by(Trade.executed_at.asc()).all()

    return [
        {
            "ticker": trade.holding.ticker,
            "trade_type": trade.trade_type.value,
            "shares": float(trade.shares),
            "price_per_share_cents": trade.price_per_share_cents,
            "executed_at": trade.executed_at.isoformat(),
        }
        for trade in trades
    ]


AGENT_TOOLS = [
    {
        "name": "get_holdings",
        "description": (
            "Returns every holding in this portfolio: ticker, shares, average cost basis, "
            "current price, market value, and unrealized gain/loss in both dollars and percent."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_price_history",
        "description": "Returns historical price snapshots for a ticker held in this portfolio.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Ticker symbol -- must be a holding in this portfolio.",
                },
                "range": {
                    "type": "string",
                    "enum": ["1D", "1W", "1M"],
                    "description": "Time window: 1D (intraday), 1W, or 1M.",
                },
            },
            "required": ["ticker", "range"],
        },
    },
    {
        "name": "get_trade_history",
        "description": "Returns this portfolio's trade history, oldest first, optionally filtered to one ticker.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Optional ticker to filter trades to. Omit for all trades.",
                },
            },
            "required": [],
        },
    },
]

TOOL_FUNCTIONS = {
    "get_holdings": get_holdings,
    "get_price_history": get_price_history,
    "get_trade_history": get_trade_history,
}
