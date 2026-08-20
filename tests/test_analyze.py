import anthropic
import httpx2

from app.api.routes import portfolio as portfolio_routes


def test_analyze_portfolio_returns_report(client, make_user, monkeypatch):
    headers = make_user(username="alice", email="alice@test.com")
    portfolio_id = client.post("/portfolios/", json={"name": "Growth"}, headers=headers).json()["id"]

    monkeypatch.setattr(portfolio_routes, "analyze_portfolio", lambda db, portfolio_id: "This is the analysis.")

    response = client.post(f"/portfolios/{portfolio_id}/analyze", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"report": "This is the analysis."}


def test_analyze_portfolio_requires_ownership(client, make_user, monkeypatch):
    alice_headers = make_user(username="alice", email="alice@test.com")
    bob_headers = make_user(username="bob123", email="bob@test.com")
    portfolio_id = client.post("/portfolios/", json={"name": "Alice's"}, headers=alice_headers).json()["id"]

    called = []
    monkeypatch.setattr(
        portfolio_routes, "analyze_portfolio", lambda db, portfolio_id: called.append(portfolio_id) or "unused"
    )

    response = client.post(f"/portfolios/{portfolio_id}/analyze", headers=bob_headers)

    assert response.status_code == 404
    assert called == []  # never reached the agent for a portfolio the caller doesn't own


def test_analyze_portfolio_returns_502_on_upstream_api_error(client, make_user, monkeypatch):
    headers = make_user(username="alice", email="alice@test.com")
    portfolio_id = client.post("/portfolios/", json={"name": "Growth"}, headers=headers).json()["id"]

    def raise_api_error(db, portfolio_id):
        raise anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com/v1/messages"))

    monkeypatch.setattr(portfolio_routes, "analyze_portfolio", raise_api_error)

    response = client.post(f"/portfolios/{portfolio_id}/analyze", headers=headers)

    assert response.status_code == 502
