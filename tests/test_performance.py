from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.models import PortfolioSnapshot, PriceSnapshot
from app.services import performance_service

EASTERN = ZoneInfo("America/New_York")


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


def test_holding_performance_1d_returns_only_matching_ticker_in_range(client, make_user, db_session):
    headers = make_user(username="alice", email="alice@test.com")
    portfolio_id = client.post("/portfolios/", json={"name": "Retirement"}, headers=headers).json()["id"]
    _record_buy(client, headers, portfolio_id, ticker="AAPL")
    _record_buy(client, headers, portfolio_id, ticker="MSFT")
    holding_id = _get_holding_id(client, headers, portfolio_id, ticker="AAPL")

    now = datetime.now(timezone.utc)
    db_session.add_all([
        PriceSnapshot(ticker="AAPL", price_cents=15500, as_of=now - timedelta(hours=1)),
        PriceSnapshot(ticker="AAPL", price_cents=15000, as_of=now - timedelta(days=10)),  # outside 1D window
        PriceSnapshot(ticker="MSFT", price_cents=30000, as_of=now - timedelta(hours=1)),  # wrong ticker
    ])
    db_session.flush()

    response = client.get(f"/portfolios/{portfolio_id}/holdings/{holding_id}/performance?range=1D", headers=headers)

    assert response.status_code == 200
    prices = [point["price_cents"] for point in response.json()]
    assert prices == [15500]


def test_holding_performance_1w_returns_daily_ohlc_aggregation(client, make_user, db_session):
    headers = make_user(username="alice", email="alice@test.com")
    portfolio_id = client.post("/portfolios/", json={"name": "Retirement"}, headers=headers).json()["id"]
    _record_buy(client, headers, portfolio_id, ticker="AAPL")
    holding_id = _get_holding_id(client, headers, portfolio_id, ticker="AAPL")

    # Two days ago (3 samples: open=100, high=120, low=100, close=110) and yesterday (2
    # samples). Daytime UTC hours (well clear of midnight in either direction) so the UTC
    # calendar date and the ET-local calendar date always agree here -- the separate
    # cross-midnight test below is what specifically exercises that boundary.
    now = datetime.now(timezone.utc)
    day1 = (now - timedelta(days=2)).replace(hour=14, minute=30, second=0, microsecond=0)
    day2 = (now - timedelta(days=1)).replace(hour=14, minute=30, second=0, microsecond=0)
    db_session.add_all([
        PriceSnapshot(ticker="AAPL", price_cents=10000, as_of=day1),
        PriceSnapshot(ticker="AAPL", price_cents=12000, as_of=day1 + timedelta(hours=2)),
        PriceSnapshot(ticker="AAPL", price_cents=11000, as_of=day1 + timedelta(hours=5)),
        PriceSnapshot(ticker="AAPL", price_cents=9000, as_of=day2),
        PriceSnapshot(ticker="AAPL", price_cents=9500, as_of=day2 + timedelta(hours=2)),
    ])
    db_session.flush()

    response = client.get(f"/portfolios/{portfolio_id}/holdings/{holding_id}/performance?range=1W", headers=headers)

    assert response.status_code == 200
    days = response.json()
    assert [d["date"] for d in days] == [day1.date().isoformat(), day2.date().isoformat()]
    assert days[0] == {
        "date": day1.date().isoformat(),
        "open_cents": 10000,
        "close_cents": 11000,
        "high_cents": 12000,
        "low_cents": 10000,
    }
    assert days[1] == {
        "date": day2.date().isoformat(),
        "open_cents": 9000,
        "close_cents": 9500,
        "high_cents": 9500,
        "low_cents": 9000,
    }


def test_holding_performance_daily_groups_by_exchange_local_date_not_utc(client, make_user, db_session):
    headers = make_user(username="alice", email="alice@test.com")
    portfolio_id = client.post("/portfolios/", json={"name": "Retirement"}, headers=headers).json()["id"]
    _record_buy(client, headers, portfolio_id, ticker="AAPL")
    holding_id = _get_holding_id(client, headers, portfolio_id, ticker="AAPL")

    # 3:30 AM UTC is always still "yesterday" in US Eastern time (UTC-4 or UTC-5, depending
    # on DST) -- the UTC calendar date and the ET-local calendar date disagree here, which is
    # exactly the boundary this test exercises.
    utc_timestamp = (datetime.now(timezone.utc) - timedelta(days=2)).replace(
        hour=3, minute=30, second=0, microsecond=0
    )
    expected_local_date = utc_timestamp.astimezone(ZoneInfo("America/New_York")).date()
    db_session.add(PriceSnapshot(ticker="AAPL", price_cents=10000, as_of=utc_timestamp))
    db_session.flush()

    response = client.get(f"/portfolios/{portfolio_id}/holdings/{holding_id}/performance?range=1W", headers=headers)

    assert response.status_code == 200
    days = response.json()
    assert [d["date"] for d in days] == [expected_local_date.isoformat()]


def test_holding_performance_daily_excludes_today_before_market_open(
    client, make_user, db_session, monkeypatch
):
    headers = make_user(username="alice", email="alice@test.com")
    portfolio_id = client.post("/portfolios/", json={"name": "Retirement"}, headers=headers).json()["id"]
    _record_buy(client, headers, portfolio_id, ticker="AAPL")
    holding_id = _get_holding_id(client, headers, portfolio_id, ticker="AAPL")

    # 2026-08-20 is a Thursday. The window/cutoff is patched to this same fixed reference
    # point so the test doesn't depend on the real wall clock or the real day of the week.
    now_et = datetime(2026, 8, 20, 8, 0, tzinfo=EASTERN)  # before the 9:30am open
    monkeypatch.setattr(
        performance_service, "_range_cutoff", lambda range_: now_et.astimezone(timezone.utc) - timedelta(days=7)
    )
    db_session.add(PriceSnapshot(ticker="AAPL", price_cents=10000, as_of=now_et.astimezone(timezone.utc)))
    db_session.flush()

    results = performance_service.get_holding_performance_daily(
        db_session, portfolio_id, holding_id, "1W", now=now_et
    )

    assert results == []


def test_holding_performance_daily_has_null_close_during_market_hours(
    client, make_user, db_session, monkeypatch
):
    headers = make_user(username="alice", email="alice@test.com")
    portfolio_id = client.post("/portfolios/", json={"name": "Retirement"}, headers=headers).json()["id"]
    _record_buy(client, headers, portfolio_id, ticker="AAPL")
    holding_id = _get_holding_id(client, headers, portfolio_id, ticker="AAPL")

    today = date(2026, 8, 20)  # Thursday
    open_snapshot = datetime(2026, 8, 20, 9, 30, tzinfo=EASTERN)
    mid_snapshot = datetime(2026, 8, 20, 11, 0, tzinfo=EASTERN)
    now_et = datetime(2026, 8, 20, 12, 0, tzinfo=EASTERN)  # mid-session
    monkeypatch.setattr(
        performance_service, "_range_cutoff", lambda range_: now_et.astimezone(timezone.utc) - timedelta(days=7)
    )
    db_session.add_all([
        PriceSnapshot(ticker="AAPL", price_cents=10000, as_of=open_snapshot.astimezone(timezone.utc)),
        PriceSnapshot(ticker="AAPL", price_cents=10500, as_of=mid_snapshot.astimezone(timezone.utc)),
    ])
    db_session.flush()

    results = performance_service.get_holding_performance_daily(
        db_session, portfolio_id, holding_id, "1W", now=now_et
    )

    assert len(results) == 1
    assert results[0].date == today
    assert results[0].open_cents == 10000
    assert results[0].high_cents == 10500
    assert results[0].low_cents == 10000
    assert results[0].close_cents is None


def test_holding_performance_daily_has_real_close_after_market_close(
    client, make_user, db_session, monkeypatch
):
    headers = make_user(username="alice", email="alice@test.com")
    portfolio_id = client.post("/portfolios/", json={"name": "Retirement"}, headers=headers).json()["id"]
    _record_buy(client, headers, portfolio_id, ticker="AAPL")
    holding_id = _get_holding_id(client, headers, portfolio_id, ticker="AAPL")

    today = date(2026, 8, 20)  # Thursday
    open_snapshot = datetime(2026, 8, 20, 9, 30, tzinfo=EASTERN)
    close_snapshot = datetime(2026, 8, 20, 15, 59, tzinfo=EASTERN)
    now_et = datetime(2026, 8, 20, 16, 30, tzinfo=EASTERN)  # after the 4pm close
    monkeypatch.setattr(
        performance_service, "_range_cutoff", lambda range_: now_et.astimezone(timezone.utc) - timedelta(days=7)
    )
    db_session.add_all([
        PriceSnapshot(ticker="AAPL", price_cents=10000, as_of=open_snapshot.astimezone(timezone.utc)),
        PriceSnapshot(ticker="AAPL", price_cents=9800, as_of=close_snapshot.astimezone(timezone.utc)),
    ])
    db_session.flush()

    results = performance_service.get_holding_performance_daily(
        db_session, portfolio_id, holding_id, "1W", now=now_et
    )

    assert len(results) == 1
    assert results[0].date == today
    assert results[0].open_cents == 10000
    assert results[0].close_cents == 9800
    assert results[0].high_cents == 10000
    assert results[0].low_cents == 9800


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
