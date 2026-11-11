import os

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url

# No fallback: destructive fixture may only target an explicitly named test database.
url = os.environ.get("DATABASE_URL", "")
if not make_url(url).database.endswith("_test"):
    raise RuntimeError("DATABASE_URL must target a disposable database ending in _test")

from app.db import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.security import _attempts  # noqa: E402
from app.seed import seed  # noqa: E402

ORIGIN = {"Origin": "http://localhost:5173"}


@pytest.fixture(scope="session", autouse=True)
def migrate():
    command.upgrade(Config("alembic.ini"), "head")


@pytest.fixture(autouse=True)
def clean_db():
    with engine.begin() as db:
        db.execute(
            text(
                "TRUNCATE users, accounts, transfers, ledger_entries, idempotency_records, refresh_sessions CASCADE"
            )
        )
    _attempts.clear()
    seed()
    yield


@pytest.fixture
def client():
    with TestClient(app, headers=ORIGIN) as c:
        yield c


def auth(client, email="alice@example.test"):
    response = client.post("/api/v1/auth/login", json={"email": email, "password": "DemoPass123!"})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


@pytest.fixture
def headers(client):
    return auth(client)


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session
