def test_register_duplicate_username_fails(client, make_user):
    make_user(username="alice", email="alice@test.com")

    response = client.post("/auth/register", json={
        "username": "alice",
        "email": "someone_else@test.com",
        "password": "testpassword123",
    })

    assert response.status_code == 400


def test_login_with_username(client, make_user):
    make_user(username="alice", email="alice@test.com", password="realpassword123")

    response = client.post("/auth/login", json={
        "identifier": "alice",
        "password": "realpassword123",
    })

    assert response.status_code == 200
    assert "access_token" in response.json()


def test_login_with_email(client, make_user):
    make_user(username="alice", email="alice@test.com", password="realpassword123")

    response = client.post("/auth/login", json={
        "identifier": "alice@test.com",
        "password": "realpassword123",
    })

    assert response.status_code == 200


def test_login_wrong_password_fails(client, make_user):
    make_user(username="alice", email="alice@test.com", password="realpassword123")

    response = client.post("/auth/login", json={
        "identifier": "alice",
        "password": "wrongpassword",
    })

    assert response.status_code == 401
