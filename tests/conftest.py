import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.services import price_service, twelvedata_service

from dotenv import load_dotenv
load_dotenv()

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://postgres:postgres@localhost:5432/portfolio_tracker_test",
)

engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(autouse=True)
def _no_live_backfill(monkeypatch):
    """Recording a trade for a not-yet-tracked ticker triggers a Twelve Data historical
    backfill. Without this, any test that records such a trade would silently make a real
    network call. Tests that specifically exercise backfill behavior re-patch
    get_daily_history themselves, which overrides this default."""
    monkeypatch.setattr(price_service, "get_daily_history", lambda ticker: [])


@pytest.fixture(autouse=True)
def _reset_twelvedata_rate_limit():
    """The Twelve Data rate limiter tracks calls in a module-level deque so it holds across
    requests within one process. Left alone, calls from one test would count against the
    next, eventually tripping the limiter in a test that has nothing to do with rate
    limiting. Reset before every test so each one starts with a clean budget."""
    twelvedata_service._call_timestamps.clear()


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
