from datetime import datetime, timezone

from app.core.config import settings
from app.core.exceptions import PriceUnavailableException
from app.models import Holding, Portfolio, PortfolioSnapshot, PriceSnapshot, User
from app.services import price_service
from app.services.finnhub_service import QuoteResult
from app.services.twelvedata_service import HistoricalBar


def _make_user_and_portfolio(db_session, username="alice"):
    user = User(username=username, email=f"{username}@test.com", password_hash="hashed")
    db_session.add(user)
    db_session.flush()
    portfolio = Portfolio(user_id=user.id, name=f"{username}'s portfolio")
    db_session.add(portfolio)
    db_session.flush()
    return user, portfolio


def _make_holding(db_session, portfolio_id, ticker, shares, current_price_cents=0):
    holding = Holding(
        portfolio_id=portfolio_id,
        ticker=ticker,
        shares=shares,
        avg_cost_basis_cents=10000,
        current_price_cents=current_price_cents,
        last_priced_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(holding)
    db_session.flush()
    return holding


def test_list_actively_held_tickers_excludes_the_demo_portfolio(db_session, monkeypatch):
    _, real_portfolio = _make_user_and_portfolio(db_session, username="alice")
    _, demo_portfolio = _make_user_and_portfolio(db_session, username="demo_portfolio_owner")
    _make_holding(db_session, real_portfolio.id, "AAPL", shares=10)
    _make_holding(db_session, demo_portfolio.id, "CTSO", shares=40)
    monkeypatch.setattr(settings, "demo_portfolio_id", demo_portfolio.id)

    tickers = price_service.list_actively_held_tickers(db_session)

    assert tickers == ["AAPL"]


def test_poll_writes_snapshots_updates_holdings_and_portfolio_total(db_session, monkeypatch):
    _, portfolio = _make_user_and_portfolio(db_session)
    _make_holding(db_session, portfolio.id, "AAPL", shares=10)
    _make_holding(db_session, portfolio.id, "MSFT", shares=5)

    quotes = {
        "AAPL": QuoteResult("AAPL", 15000, datetime(2026, 8, 20, 15, 0, tzinfo=timezone.utc)),
        "MSFT": QuoteResult("MSFT", 30000, datetime(2026, 8, 20, 15, 0, tzinfo=timezone.utc)),
    }
    monkeypatch.setattr(price_service, "get_quote", lambda ticker: quotes[ticker])

    failed = price_service.poll_and_record_prices(db_session)

    assert failed == []

    aapl_holding = db_session.query(Holding).filter(Holding.ticker == "AAPL").one()
    msft_holding = db_session.query(Holding).filter(Holding.ticker == "MSFT").one()
    assert aapl_holding.current_price_cents == 15000
    assert msft_holding.current_price_cents == 30000

    snapshots = db_session.query(PriceSnapshot).all()
    assert {(s.ticker, s.price_cents) for s in snapshots} == {("AAPL", 15000), ("MSFT", 30000)}

    portfolio_snapshot = db_session.query(PortfolioSnapshot).filter(
        PortfolioSnapshot.portfolio_id == portfolio.id
    ).one()
    assert portfolio_snapshot.total_market_value_cents == 10 * 15000 + 5 * 30000


def test_poll_skips_ticker_with_no_quote_data(db_session, monkeypatch):
    _, portfolio = _make_user_and_portfolio(db_session)
    _make_holding(db_session, portfolio.id, "TSLA", shares=3, current_price_cents=20000)

    def raise_unavailable(ticker):
        raise PriceUnavailableException(ticker)

    monkeypatch.setattr(price_service, "get_quote", raise_unavailable)

    failed = price_service.poll_and_record_prices(db_session)

    assert failed == ["TSLA"]
    assert db_session.query(PriceSnapshot).count() == 0

    holding = db_session.query(Holding).filter(Holding.ticker == "TSLA").one()
    assert holding.current_price_cents == 20000  # unchanged

    # portfolio snapshot still written, using the last-known price
    portfolio_snapshot = db_session.query(PortfolioSnapshot).filter(
        PortfolioSnapshot.portfolio_id == portfolio.id
    ).one()
    assert portfolio_snapshot.total_market_value_cents == 3 * 20000


def test_poll_ignores_fully_sold_holdings(db_session, monkeypatch):
    _, portfolio = _make_user_and_portfolio(db_session)
    _make_holding(db_session, portfolio.id, "GME", shares=0, current_price_cents=5000)

    called_with = []
    monkeypatch.setattr(
        price_service,
        "get_quote",
        lambda ticker: called_with.append(ticker) or QuoteResult(ticker, 100, datetime.now(timezone.utc)),
    )

    failed = price_service.poll_and_record_prices(db_session)

    assert failed == []
    assert called_with == []  # never fetched a quote for a zero-share holding
    assert db_session.query(PortfolioSnapshot).count() == 0  # nothing actively held to snapshot


def test_poll_is_idempotent_for_repeated_quote_timestamps(db_session, monkeypatch):
    _, portfolio = _make_user_and_portfolio(db_session)
    _make_holding(db_session, portfolio.id, "AAPL", shares=1)

    same_quote = QuoteResult("AAPL", 15000, datetime(2026, 8, 20, 15, 0, tzinfo=timezone.utc))
    monkeypatch.setattr(price_service, "get_quote", lambda ticker: same_quote)

    price_service.poll_and_record_prices(db_session)
    price_service.poll_and_record_prices(db_session)

    assert db_session.query(PriceSnapshot).count() == 1


def test_backfill_writes_history_for_a_genuinely_new_ticker(db_session, monkeypatch):
    calls = []
    bars = [
        HistoricalBar("AAPL", 15000, datetime(2026, 8, 19, 20, 0, tzinfo=timezone.utc)),
        HistoricalBar("AAPL", 15200, datetime(2026, 8, 20, 20, 0, tzinfo=timezone.utc)),
    ]

    def fake_get_historical_bars(ticker):
        calls.append(ticker)
        return bars

    monkeypatch.setattr(price_service, "get_historical_bars", fake_get_historical_bars)

    price_service.backfill_ticker_history_if_new(db_session, "AAPL")

    assert calls == ["AAPL"]
    snapshots = db_session.query(PriceSnapshot).filter(PriceSnapshot.ticker == "AAPL").all()
    assert {s.price_cents for s in snapshots} == {15000, 15200}


def test_backfill_skips_a_ticker_already_tracked(db_session, monkeypatch):
    db_session.add(
        PriceSnapshot(ticker="MSFT", price_cents=30000, as_of=datetime(2026, 8, 1, tzinfo=timezone.utc))
    )
    db_session.flush()

    calls = []
    monkeypatch.setattr(
        price_service, "get_historical_bars", lambda ticker: calls.append(ticker) or []
    )

    price_service.backfill_ticker_history_if_new(db_session, "MSFT")

    assert calls == []  # never called Twelve Data for an already-tracked ticker


def test_backfill_failure_is_swallowed_not_raised(db_session, monkeypatch):
    def raise_unavailable(ticker):
        raise PriceUnavailableException(ticker)

    monkeypatch.setattr(price_service, "get_historical_bars", raise_unavailable)

    price_service.backfill_ticker_history_if_new(db_session, "TSLA")  # must not raise

    assert db_session.query(PriceSnapshot).filter(PriceSnapshot.ticker == "TSLA").count() == 0


def test_record_portfolio_snapshot_now_sums_current_holdings(db_session):
    _, portfolio = _make_user_and_portfolio(db_session)
    _make_holding(db_session, portfolio.id, "AAPL", shares=10, current_price_cents=15000)
    _make_holding(db_session, portfolio.id, "MSFT", shares=5, current_price_cents=30000)

    price_service.record_portfolio_snapshot_now(db_session, portfolio.id)
    db_session.flush()

    snapshot = db_session.query(PortfolioSnapshot).filter(
        PortfolioSnapshot.portfolio_id == portfolio.id
    ).one()
    assert snapshot.total_market_value_cents == 10 * 15000 + 5 * 30000


def test_record_portfolio_snapshot_now_skips_when_nothing_actively_held(db_session):
    _, portfolio = _make_user_and_portfolio(db_session)
    _make_holding(db_session, portfolio.id, "GME", shares=0, current_price_cents=5000)

    price_service.record_portfolio_snapshot_now(db_session, portfolio.id)

    assert db_session.query(PortfolioSnapshot).filter(
        PortfolioSnapshot.portfolio_id == portfolio.id
    ).count() == 0
