from datetime import datetime, timedelta, timezone

from app.models import PortfolioSnapshot, PriceSnapshot


def _record_buy(client, headers, portfolio_id, ticker="AAPL"):
    response = client.post(
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
    assert response.status_code == 201, response.text


def _get_holding_id(client, headers, portfolio_id, ticker="AAPL"):
    response = client.get(f"/portfolios/{portfolio_id}/holdings/", headers=headers)
    holding = next(h for h in response.json() if h["ticker"] == ticker)
    return holding["id"]


def test_portfolio_performance_returns_only_snapshots_in_range(client, make_user, db_session):
    headers = make_user(username="alice", email="alice@test.com")
    portfolio_id = client.post("/portfolios/", json={"name": "Retirement"}, headers=headers).json()["id"]

    now = datetime.now(timezone.utc)
    db_session.add_all([
        PortfolioSnapshot(portfolio_id=portfolio_id, total_market_value_cents=100000, as_of=now - timedelta(hours=2)),
        PortfolioSnapshot(portfolio_id=portfolio_id, total_market_value_cents=90000, as_of=now - timedelta(days=40)),
    ])
    db_session.flush()

    response = client.get(f"/portfolios/{portfolio_id}/performance?range=1M", headers=headers)

    assert response.status_code == 200
    values = [point["total_market_value_cents"] for point in response.json()]
    assert values == [100000]


def test_portfolio_performance_requires_ownership(client, make_user):
    alice_headers = make_user(username="alice", email="alice@test.com")
    bob_headers = make_user(username="bob123", email="bob@test.com")
    portfolio_id = client.post("/portfolios/", json={"name": "Alice's"}, headers=alice_headers).json()["id"]

    response = client.get(f"/portfolios/{portfolio_id}/performance", headers=bob_headers)

    assert response.status_code == 404


def test_portfolio_performance_rejects_invalid_range(client, make_user):
    headers = make_user(username="alice", email="alice@test.com")
    portfolio_id = client.post("/portfolios/", json={"name": "Retirement"}, headers=headers).json()["id"]

    response = client.get(f"/portfolios/{portfolio_id}/performance?range=1Y", headers=headers)

    assert response.status_code == 422


def test_holding_performance_returns_only_matching_ticker_in_range(client, make_user, db_session):
    headers = make_user(username="alice", email="alice@test.com")
    portfolio_id = client.post("/portfolios/", json={"name": "Retirement"}, headers=headers).json()["id"]
    _record_buy(client, headers, portfolio_id, ticker="AAPL")
    _record_buy(client, headers, portfolio_id, ticker="MSFT")
    holding_id = _get_holding_id(client, headers, portfolio_id, ticker="AAPL")

    now = datetime.now(timezone.utc)
    db_session.add_all([
        PriceSnapshot(ticker="AAPL", price_cents=15500, as_of=now - timedelta(hours=1)),
        PriceSnapshot(ticker="AAPL", price_cents=15000, as_of=now - timedelta(days=10)),  # outside 1W window
        PriceSnapshot(ticker="MSFT", price_cents=30000, as_of=now - timedelta(hours=1)),  # wrong ticker
    ])
    db_session.flush()

    response = client.get(f"/portfolios/{portfolio_id}/holdings/{holding_id}/performance?range=1W", headers=headers)

    assert response.status_code == 200
    prices = [point["price_cents"] for point in response.json()]
    assert prices == [15500]


def test_holding_performance_404_when_holding_not_in_portfolio(client, make_user):
    alice_headers = make_user(username="alice", email="alice@test.com")
    bob_headers = make_user(username="bob123", email="bob@test.com")

    alice_portfolio_id = client.post("/portfolios/", json={"name": "Alice's"}, headers=alice_headers).json()["id"]
    _record_buy(client, alice_headers, alice_portfolio_id, ticker="AAPL")
    alice_holding_id = _get_holding_id(client, alice_headers, alice_portfolio_id, ticker="AAPL")

    bob_portfolio_id = client.post("/portfolios/", json={"name": "Bob's"}, headers=bob_headers).json()["id"]

    response = client.get(
        f"/portfolios/{bob_portfolio_id}/holdings/{alice_holding_id}/performance", headers=bob_headers
    )

    assert response.status_code == 404
