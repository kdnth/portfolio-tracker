from datetime import datetime, timezone

import httpx

from app.models import PortfolioSnapshot, PriceSnapshot
from app.services import price_service
from app.services.twelvedata_service import HistoricalBar


def _record_buy(client, headers, portfolio_id, ticker="AAPL"):
    return client.post(
        f"/portfolios/{portfolio_id}/trades/",
        json={
            "ticker": ticker,
            "trade_type": "buy",
            "shares": 10,
            "price_per_share_cents": 15000,
            "executed_at": "2026-07-01T00:00:00Z",
        },
        headers=headers,
    )


def test_recording_a_trade_writes_a_fresh_portfolio_snapshot(client, make_user, db_session):
    headers = make_user(username="alice", email="alice@test.com")
    portfolio_id = client.post("/portfolios/", json={"name": "Growth"}, headers=headers).json()["id"]

    response = _record_buy(client, headers, portfolio_id, ticker="AAPL")
    assert response.status_code == 201

    snapshots = db_session.query(PortfolioSnapshot).filter(
        PortfolioSnapshot.portfolio_id == portfolio_id
    ).all()
    assert len(snapshots) == 1
    assert snapshots[0].total_market_value_cents == 10 * 15000  # 10 shares @ $150.00


def test_second_buy_against_an_existing_holding_succeeds(client, make_user):
    """Regression test: Holding.shares/Trade.shares are Numeric columns, which SQLAlchemy
    returns as decimal.Decimal once a row has actually round-tripped through Postgres (not
    just been flushed). A first trade against a brand-new in-memory Holding doesn't exercise
    this -- only a second trade against an already-committed-and-reloaded holding does, which
    is exactly the case that broke when TradeCreate.shares was still a plain float."""
    headers = make_user(username="alice", email="alice@test.com")
    portfolio_id = client.post("/portfolios/", json={"name": "Growth"}, headers=headers).json()["id"]

    first = _record_buy(client, headers, portfolio_id, ticker="AAPL")
    assert first.status_code == 201

    second = client.post(
        f"/portfolios/{portfolio_id}/trades/",
        json={
            "ticker": "AAPL",
            "trade_type": "buy",
            "shares": 5,
            "price_per_share_cents": 18000,
            "executed_at": "2026-07-02T00:00:00Z",
        },
        headers=headers,
    )

    assert second.status_code == 201
    holdings = client.get(f"/portfolios/{portfolio_id}/holdings/", headers=headers).json()
    assert float(holdings[0]["shares"]) == 15
    # weighted avg: (10*15000 + 5*18000) / 15 = 16000
    assert holdings[0]["avg_cost_basis_cents"] == 16000


def test_sell_against_an_existing_holding_succeeds(client, make_user):
    """Same Decimal/float regression, on the sell path."""
    headers = make_user(username="alice", email="alice@test.com")
    portfolio_id = client.post("/portfolios/", json={"name": "Growth"}, headers=headers).json()["id"]

    buy = _record_buy(client, headers, portfolio_id, ticker="AAPL")
    assert buy.status_code == 201

    sell = client.post(
        f"/portfolios/{portfolio_id}/trades/",
        json={
            "ticker": "AAPL",
            "trade_type": "sell",
            "shares": 4,
            "price_per_share_cents": 17000,
            "executed_at": "2026-07-02T00:00:00Z",
        },
        headers=headers,
    )

    assert sell.status_code == 201
    holdings = client.get(f"/portfolios/{portfolio_id}/holdings/", headers=headers).json()
    assert float(holdings[0]["shares"]) == 6


def test_first_trade_on_a_new_ticker_backfills_history(client, make_user, monkeypatch):
    headers = make_user(username="alice", email="alice@test.com")
    portfolio_id = client.post("/portfolios/", json={"name": "Growth"}, headers=headers).json()["id"]

    calls = []
    monkeypatch.setattr(
        price_service,
        "get_historical_bars",
        lambda ticker: calls.append(ticker)
        or [HistoricalBar(ticker, 14000, datetime(2026, 6, 30, 20, 0, tzinfo=timezone.utc))],
    )

    response = _record_buy(client, headers, portfolio_id, ticker="AAPL")

    assert response.status_code == 201
    assert calls == ["AAPL"]


def test_second_holding_of_an_already_tracked_ticker_does_not_backfill_again(
    client, make_user, db_session, monkeypatch
):
    db_session.add(
        PriceSnapshot(ticker="AAPL", price_cents=14000, as_of=datetime(2026, 6, 30, tzinfo=timezone.utc))
    )
    db_session.flush()

    headers = make_user(username="alice", email="alice@test.com")
    portfolio_id = client.post("/portfolios/", json={"name": "Growth"}, headers=headers).json()["id"]

    calls = []
    monkeypatch.setattr(
        price_service, "get_historical_bars", lambda ticker: calls.append(ticker) or []
    )

    response = _record_buy(client, headers, portfolio_id, ticker="AAPL")

    assert response.status_code == 201
    assert calls == []  # AAPL already has history from another portfolio/user


def test_backfill_failure_does_not_fail_the_trade(client, make_user, monkeypatch):
    headers = make_user(username="alice", email="alice@test.com")
    portfolio_id = client.post("/portfolios/", json={"name": "Growth"}, headers=headers).json()["id"]

    def raise_error(ticker):
        raise httpx.ConnectError("network unreachable")

    monkeypatch.setattr(price_service, "get_historical_bars", raise_error)

    response = _record_buy(client, headers, portfolio_id, ticker="AAPL")

    assert response.status_code == 201


def test_cannot_create_trade_on_other_users_portfolio(client, make_user):
    alice_headers = make_user(username="alice", email="alice@test.com")
    bob_headers = make_user(username="bob123", email="bob@test.com")

    create_response = client.post("/portfolios/", json={"name": "Alice's Portfolio"}, headers=alice_headers)
    portfolio_id = create_response.json()["id"]

    response = client.post(
        f"/portfolios/{portfolio_id}/trades/",
        json={
            "ticker": "AAPL",
            "trade_type": "buy",
            "shares": 10,
            "price_per_share_cents": 15000,
            "executed_at": "2026-07-01T00:00:00Z",
        },
        headers=bob_headers,
    )

    assert response.status_code == 404


def test_buy_creates_holding_and_trade(client, make_user):
    headers = make_user(username="alice", email="alice@test.com")
    portfolio_id = client.post("/portfolios/", json={"name": "Growth"}, headers=headers).json()["id"]

    response = client.post(
        f"/portfolios/{portfolio_id}/trades/",
        json={
            "ticker": "AAPL",
            "trade_type": "buy",
            "shares": 10,
            "price_per_share_cents": 15000,
            "executed_at": "2026-07-01T00:00:00Z",
        },
        headers=headers,
    )

    assert response.status_code == 201
    assert response.json()["trade_type"] == "buy"
    assert response.json()["shares"] == 10

    holdings = client.get(f"/portfolios/{portfolio_id}/holdings/", headers=headers)
    assert holdings.status_code == 200
    assert len(holdings.json()) == 1
    assert holdings.json()[0]["ticker"] == "AAPL"
    assert float(holdings.json()[0]["shares"]) == 10
    assert holdings.json()[0]["avg_cost_basis_cents"] == 15000
    assert holdings.json()[0]["current_price_cents"] == 15000
