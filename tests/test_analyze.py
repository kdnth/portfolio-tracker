from datetime import datetime, timezone

import anthropic
import httpx2

from app.api.routes import portfolio as portfolio_routes
from app.models import AnalysisRequestLog, User
from app.services.analysis_quota_service import DAILY_ANALYSIS_LIMIT


def _make_analyzable_portfolio(client, headers, name="Growth"):
    return client.post("/portfolios/", json={"name": name}, headers=headers).json()["id"]


def test_analyze_portfolio_returns_report(client, make_user, monkeypatch):
    headers = make_user(username="alice", email="alice@test.com")
    portfolio_id = _make_analyzable_portfolio(client, headers)

    monkeypatch.setattr(portfolio_routes, "analyze_portfolio", lambda db, portfolio_id: "This is the analysis.")

    response = client.post(f"/portfolios/{portfolio_id}/analyze", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"report": "This is the analysis.", "analyses_remaining_today": DAILY_ANALYSIS_LIMIT - 1}


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


def test_analyze_portfolio_blocks_after_daily_limit_reached(client, make_user, monkeypatch):
    headers = make_user(username="alice", email="alice@test.com")
    portfolio_id = _make_analyzable_portfolio(client, headers)
    monkeypatch.setattr(portfolio_routes, "analyze_portfolio", lambda db, portfolio_id: "report")

    for i in range(DAILY_ANALYSIS_LIMIT):
        response = client.post(f"/portfolios/{portfolio_id}/analyze", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["analyses_remaining_today"] == DAILY_ANALYSIS_LIMIT - 1 - i

    response = client.post(f"/portfolios/{portfolio_id}/analyze", headers=headers)

    assert response.status_code == 429
    assert "limit" in response.json()["detail"].lower()


def test_analyze_portfolio_admin_bypasses_daily_limit(client, make_user, db_session, monkeypatch):
    headers = make_user(username="alice", email="alice@test.com")
    portfolio_id = _make_analyzable_portfolio(client, headers)
    db_session.query(User).filter(User.username == "alice").update({"is_admin": True})
    db_session.commit()
    monkeypatch.setattr(portfolio_routes, "analyze_portfolio", lambda db, portfolio_id: "report")

    for _ in range(DAILY_ANALYSIS_LIMIT + 2):
        response = client.post(f"/portfolios/{portfolio_id}/analyze", headers=headers)
        assert response.status_code == 200, response.text
        assert response.json()["analyses_remaining_today"] is None


def test_count_analyses_today_excludes_rows_from_before_utc_midnight(client, make_user, db_session):
    from app.services.analysis_quota_service import count_analyses_today

    headers = make_user(username="alice", email="alice@test.com")
    user = db_session.query(User).filter(User.username == "alice").first()
    portfolio_id = _make_analyzable_portfolio(client, headers)

    now = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
    yesterday_late = datetime(2026, 8, 20, 23, 59, 0, tzinfo=timezone.utc)
    today_early = datetime(2026, 8, 21, 0, 0, 1, tzinfo=timezone.utc)

    db_session.add_all([
        AnalysisRequestLog(user_id=user.id, portfolio_id=portfolio_id, created_at=yesterday_late),
        AnalysisRequestLog(user_id=user.id, portfolio_id=portfolio_id, created_at=today_early),
    ])
    db_session.flush()

    assert count_analyses_today(db_session, user.id, now=now) == 1


def test_get_analysis_quota_reflects_usage(client, make_user, monkeypatch):
    headers = make_user(username="alice", email="alice@test.com")
    portfolio_id = _make_analyzable_portfolio(client, headers)
    monkeypatch.setattr(portfolio_routes, "analyze_portfolio", lambda db, portfolio_id: "report")

    response = client.get("/users/me/analysis-quota", headers=headers)
    assert response.json() == {"limit": DAILY_ANALYSIS_LIMIT, "used_today": 0, "remaining": DAILY_ANALYSIS_LIMIT}

    client.post(f"/portfolios/{portfolio_id}/analyze", headers=headers)

    response = client.get("/users/me/analysis-quota", headers=headers)
    assert response.json() == {
        "limit": DAILY_ANALYSIS_LIMIT,
        "used_today": 1,
        "remaining": DAILY_ANALYSIS_LIMIT - 1,
    }


def test_get_analysis_quota_shows_unlimited_for_admin(client, make_user, db_session):
    headers = make_user(username="alice", email="alice@test.com")
    db_session.query(User).filter(User.username == "alice").update({"is_admin": True})
    db_session.commit()

    response = client.get("/users/me/analysis-quota", headers=headers)

    assert response.json()["remaining"] is None
