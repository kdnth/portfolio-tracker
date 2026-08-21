from datetime import datetime, timezone

from app.api.routes import demo as demo_routes
from app.core.config import settings
from app.models import Holding, Portfolio, PriceSnapshot, User
from app.services.demo_quota_service import DAILY_DEMO_LIMIT


def _make_demo_portfolio(db_session, ticker="AAPL"):
    user = User(username="demo_owner", email="demo_owner@test.com", password_hash="hashed")
    db_session.add(user)
    db_session.flush()
    portfolio = Portfolio(user_id=user.id, name="Demo Portfolio")
    db_session.add(portfolio)
    db_session.flush()
    holding = Holding(
        portfolio_id=portfolio.id,
        ticker=ticker,
        shares=10,
        avg_cost_basis_cents=15000,
        current_price_cents=16000,
        last_priced_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(holding)
    db_session.add(PriceSnapshot(ticker=ticker, price_cents=16000, as_of=datetime.now(timezone.utc)))
    db_session.flush()
    return portfolio, holding


def test_demo_endpoints_return_503_when_not_configured(client, monkeypatch):
    monkeypatch.setattr(settings, "demo_portfolio_id", None)

    assert client.get("/demo/portfolio").status_code == 503
    assert client.get("/demo/holdings").status_code == 503
    assert client.get("/demo/performance").status_code == 503
    assert client.post("/demo/analyze").status_code == 503


def test_demo_endpoints_return_seeded_data(client, db_session, monkeypatch):
    portfolio, holding = _make_demo_portfolio(db_session)
    monkeypatch.setattr(settings, "demo_portfolio_id", portfolio.id)

    portfolio_response = client.get("/demo/portfolio")
    assert portfolio_response.status_code == 200
    assert portfolio_response.json()["id"] == portfolio.id

    holdings_response = client.get("/demo/holdings")
    assert holdings_response.status_code == 200
    tickers = [h["ticker"] for h in holdings_response.json()]
    assert tickers == ["AAPL"]

    performance_response = client.get("/demo/holdings/%d/performance" % holding.id, params={"range": "1D"})
    assert performance_response.status_code == 200


def test_demo_holding_performance_404_for_unknown_holding(client, db_session, monkeypatch):
    portfolio, _ = _make_demo_portfolio(db_session)
    monkeypatch.setattr(settings, "demo_portfolio_id", portfolio.id)

    response = client.get("/demo/holdings/999999/performance")

    assert response.status_code == 404


def test_demo_analyze_blocks_third_call_same_ip(client, db_session, monkeypatch):
    portfolio, _ = _make_demo_portfolio(db_session)
    monkeypatch.setattr(settings, "demo_portfolio_id", portfolio.id)
    monkeypatch.setattr(demo_routes, "analyze_portfolio", lambda db, portfolio_id: "demo report")

    headers = {"X-Forwarded-For": "203.0.113.5"}
    for i in range(DAILY_DEMO_LIMIT):
        response = client.post("/demo/analyze", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["demo_analyses_remaining_today"] == DAILY_DEMO_LIMIT - 1 - i

    response = client.post("/demo/analyze", headers=headers)

    assert response.status_code == 429
    assert "limit" in response.json()["detail"].lower()


def test_demo_analyze_different_ip_has_its_own_quota(client, db_session, monkeypatch):
    portfolio, _ = _make_demo_portfolio(db_session)
    monkeypatch.setattr(settings, "demo_portfolio_id", portfolio.id)
    monkeypatch.setattr(demo_routes, "analyze_portfolio", lambda db, portfolio_id: "demo report")

    first_ip = {"X-Forwarded-For": "203.0.113.5"}
    second_ip = {"X-Forwarded-For": "198.51.100.9"}

    for _ in range(DAILY_DEMO_LIMIT):
        assert client.post("/demo/analyze", headers=first_ip).status_code == 200
    assert client.post("/demo/analyze", headers=first_ip).status_code == 429

    # A different IP is unaffected by the first IP's exhausted quota.
    response = client.post("/demo/analyze", headers=second_ip)
    assert response.status_code == 200
    assert response.json()["demo_analyses_remaining_today"] == DAILY_DEMO_LIMIT - 1
