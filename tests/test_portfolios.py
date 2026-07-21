def test_create_portfolio(client, make_user):
    headers = make_user(username="alice", email="alice@test.com")

    response = client.post("/portfolios/", json={"name": "Retirement"}, headers=headers)

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Retirement"
    assert "id" in body

def test_list_portfolios_only_returns_own(client, make_user):
    alice_headers = make_user(username="alice", email="alice@test.com")
    bob_headers = make_user(username="bob123", email="bob@test.com")

    client.post("/portfolios/", json={"name": "Alice's Portfolio"}, headers=alice_headers)
    client.post("/portfolios/", json={"name": "Bob's Portfolio"}, headers=bob_headers)

    response = client.get("/portfolios/", headers=alice_headers)

    assert response.status_code == 200
    names = [p["name"] for p in response.json()]
    assert names == ["Alice's Portfolio"]

def test_cannot_fetch_other_users_portfolio(client, make_user):
    alice_headers = make_user(username="alice", email="alice@test.com")
    bob_headers = make_user(username="bob123", email="bob@test.com")

    create_response = client.post("/portfolios/", json={"name": "Alice's Secret Stash"}, headers=alice_headers)
    portfolio_id = create_response.json()["id"]

    response = client.get(f"/portfolios/{portfolio_id}", headers=bob_headers)

    assert response.status_code == 404
