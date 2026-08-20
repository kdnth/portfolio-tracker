from datetime import datetime, timedelta, timezone

from app.models import Holding, PriceSnapshot, Portfolio, Trade, User
from app.models.trade import TradeOptions
from app.services import agent_tools


def _make_user_and_portfolio(db_session, username="alice"):
    user = User(username=username, email=f"{username}@test.com", password_hash="hashed")
    db_session.add(user)
    db_session.flush()
    portfolio = Portfolio(user_id=user.id, name=f"{username}'s portfolio")
    db_session.add(portfolio)
    db_session.flush()
    return user, portfolio


def _make_holding(db_session, portfolio_id, ticker, shares, avg_cost_basis_cents=0, current_price_cents=0):
    holding = Holding(
        portfolio_id=portfolio_id,
        ticker=ticker,
        shares=shares,
        avg_cost_basis_cents=avg_cost_basis_cents,
        current_price_cents=current_price_cents,
        last_priced_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(holding)
    db_session.flush()
    return holding


def _make_trade(db_session, holding_id, trade_type, shares, price_per_share_cents, executed_at):
    trade = Trade(
        holding_id=holding_id,
        trade_type=trade_type,
        shares=shares,
        price_per_share_cents=price_per_share_cents,
        executed_at=executed_at,
    )
    db_session.add(trade)
    db_session.flush()
    return trade


def test_get_holdings_computes_market_value_and_gain(db_session):
    _, portfolio = _make_user_and_portfolio(db_session)
    _make_holding(db_session, portfolio.id, "AAPL", shares=10, avg_cost_basis_cents=15000, current_price_cents=18000)
    _make_holding(db_session, portfolio.id, "MSFT", shares=5, avg_cost_basis_cents=30000, current_price_cents=27000)

    results = {row["ticker"]: row for row in agent_tools.get_holdings(db_session, portfolio.id)}

    aapl = results["AAPL"]
    assert aapl["market_value_cents"] == 180000
    assert aapl["unrealized_gain_cents"] == 30000
    assert aapl["unrealized_gain_percent"] == 20.0

    msft = results["MSFT"]
    assert msft["market_value_cents"] == 135000
    assert msft["unrealized_gain_cents"] == -15000
    assert msft["unrealized_gain_percent"] == -10.0


def test_get_holdings_scoped_to_portfolio(db_session):
    _, alice_portfolio = _make_user_and_portfolio(db_session, "alice")
    _, bob_portfolio = _make_user_and_portfolio(db_session, "bob")
    _make_holding(db_session, alice_portfolio.id, "AAPL", shares=10)
    _make_holding(db_session, bob_portfolio.id, "TSLA", shares=3)

    results = agent_tools.get_holdings(db_session, alice_portfolio.id)

    assert [row["ticker"] for row in results] == ["AAPL"]


def test_get_holdings_empty_portfolio_returns_empty_list(db_session):
    _, portfolio = _make_user_and_portfolio(db_session)

    assert agent_tools.get_holdings(db_session, portfolio.id) == []


def test_get_price_history_returns_snapshots_in_range(db_session):
    _, portfolio = _make_user_and_portfolio(db_session)
    _make_holding(db_session, portfolio.id, "AAPL", shares=10)

    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            PriceSnapshot(ticker="AAPL", price_cents=15500, as_of=now - timedelta(hours=1)),
            PriceSnapshot(ticker="AAPL", price_cents=15000, as_of=now - timedelta(days=40)),  # outside 1M
        ]
    )
    db_session.flush()

    result = agent_tools.get_price_history(db_session, portfolio.id, "AAPL", "1M")

    assert "error" not in result
    assert result["ticker"] == "AAPL"
    assert [p["price_cents"] for p in result["prices"]] == [15500]


def test_get_price_history_matches_ticker_case_insensitively(db_session):
    _, portfolio = _make_user_and_portfolio(db_session)
    _make_holding(db_session, portfolio.id, "AAPL", shares=10)
    now = datetime.now(timezone.utc)
    db_session.add(PriceSnapshot(ticker="AAPL", price_cents=15500, as_of=now - timedelta(hours=1)))
    db_session.flush()

    result = agent_tools.get_price_history(db_session, portfolio.id, "aapl", "1M")

    assert "error" not in result
    assert result["ticker"] == "AAPL"
    assert len(result["prices"]) == 1


def test_get_price_history_errors_for_ticker_not_held(db_session):
    _, portfolio = _make_user_and_portfolio(db_session)
    _make_holding(db_session, portfolio.id, "AAPL", shares=10)

    result = agent_tools.get_price_history(db_session, portfolio.id, "TSLA", "1M")

    assert "error" in result
    assert "not held" in result["error"]


def test_get_price_history_errors_for_invalid_range(db_session):
    _, portfolio = _make_user_and_portfolio(db_session)
    _make_holding(db_session, portfolio.id, "AAPL", shares=10)

    result = agent_tools.get_price_history(db_session, portfolio.id, "AAPL", "1Y")

    assert "error" in result


def test_get_trade_history_returns_all_trades_oldest_first(db_session):
    _, portfolio = _make_user_and_portfolio(db_session)
    aapl = _make_holding(db_session, portfolio.id, "AAPL", shares=10)
    msft = _make_holding(db_session, portfolio.id, "MSFT", shares=5)
    _make_trade(db_session, aapl.id, TradeOptions.BUY, 10, 15000, datetime(2026, 7, 2, tzinfo=timezone.utc))
    _make_trade(db_session, msft.id, TradeOptions.BUY, 5, 30000, datetime(2026, 7, 1, tzinfo=timezone.utc))

    results = agent_tools.get_trade_history(db_session, portfolio.id)

    assert [row["ticker"] for row in results] == ["MSFT", "AAPL"]  # oldest first


def test_get_trade_history_filters_by_ticker(db_session):
    _, portfolio = _make_user_and_portfolio(db_session)
    aapl = _make_holding(db_session, portfolio.id, "AAPL", shares=10)
    msft = _make_holding(db_session, portfolio.id, "MSFT", shares=5)
    _make_trade(db_session, aapl.id, TradeOptions.BUY, 10, 15000, datetime(2026, 7, 1, tzinfo=timezone.utc))
    _make_trade(db_session, msft.id, TradeOptions.BUY, 5, 30000, datetime(2026, 7, 1, tzinfo=timezone.utc))

    results = agent_tools.get_trade_history(db_session, portfolio.id, ticker="AAPL")

    assert [row["ticker"] for row in results] == ["AAPL"]


def test_get_trade_history_filters_by_ticker_case_insensitively(db_session):
    _, portfolio = _make_user_and_portfolio(db_session)
    aapl = _make_holding(db_session, portfolio.id, "AAPL", shares=10)
    msft = _make_holding(db_session, portfolio.id, "MSFT", shares=5)
    _make_trade(db_session, aapl.id, TradeOptions.BUY, 10, 15000, datetime(2026, 7, 1, tzinfo=timezone.utc))
    _make_trade(db_session, msft.id, TradeOptions.BUY, 5, 30000, datetime(2026, 7, 1, tzinfo=timezone.utc))

    results = agent_tools.get_trade_history(db_session, portfolio.id, ticker="aapl")

    assert [row["ticker"] for row in results] == ["AAPL"]


def test_get_trade_history_scoped_to_portfolio(db_session):
    _, alice_portfolio = _make_user_and_portfolio(db_session, "alice")
    _, bob_portfolio = _make_user_and_portfolio(db_session, "bob")
    alice_holding = _make_holding(db_session, alice_portfolio.id, "AAPL", shares=10)
    bob_holding = _make_holding(db_session, bob_portfolio.id, "AAPL", shares=3)
    _make_trade(db_session, alice_holding.id, TradeOptions.BUY, 10, 15000, datetime(2026, 7, 1, tzinfo=timezone.utc))
    _make_trade(db_session, bob_holding.id, TradeOptions.BUY, 3, 16000, datetime(2026, 7, 1, tzinfo=timezone.utc))

    results = agent_tools.get_trade_history(db_session, alice_portfolio.id)

    assert len(results) == 1
    assert results[0]["shares"] == 10.0
