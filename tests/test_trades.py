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
