import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app

from dotenv import load_dotenv
load_dotenv()

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/portfolio_tracker_test",
)

engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture
def db_session():
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()

@pytest.fixture
def client(db_session):
    def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()

@pytest.fixture
def make_user(client):
    def _make_user(username: str, email: str, password: str = "testpassword123"):
        response = client.post("/auth/register", json={
            "username": username,
            "email": email,
            "password": password
        })
        assert response.status_code == 201, response.text
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    return _make_user
