import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import DBAPIError

from app.config import Settings
from app.db import SessionLocal, engine
from app.main import app
from app.models import Account, AuditEvent, LedgerEntry
from app.seed import ALICE, BOB
from tests.conftest import ORIGIN, auth
from tests.test_platform import BODY, PATH, assert_integrity, balances, parallel, send


def opened(client, headers):
    result = client.post(
        PATH + "/accounts",
        headers=headers,
        json={"name": "Travel savings", "account_type": "SAVINGS"},
    )
    assert result.status_code == 201, result.text
    return result.json()


def test_zero_balance_lifecycle_and_audit(client, headers, db):
    row = opened(client, headers)
    assert row["balance_vnd"] == 0
    assert row["status"] == "ACTIVE"
    assert row["account_type"] == "SAVINGS"
    path = PATH + "/accounts/" + row["id"]
    assert client.patch(path, headers=headers, json={"name": "Holiday"}).json()["name"] == "Holiday"
    assert (
        client.post(path + "/close", headers=headers, json={"confirmed": False}).status_code == 422
    )
    closed = client.post(path + "/close", headers=headers, json={"confirmed": True})
    assert closed.status_code == 200
    assert closed.json()["status"] == "CLOSED"
    assert closed.json()["closed_at"]
    assert (
        client.post(path + "/close", headers=headers, json={"confirmed": True}).status_code == 200
    )
    assert client.patch(path, headers=headers, json={"name": "Reopen"}).status_code == 409
    assert (
        send(client, headers, body={**BODY, "destination_account_id": row["id"]}).status_code == 409
    )
    assert db.scalar(select(func.count()).select_from(AuditEvent)) == 3
    assert_integrity(db)


@pytest.mark.parametrize(
    "extra",
    [{"balance_vnd": 9}, {"user_id": str(BOB)}, {"status": "ACTIVE"}, {"role": "OPERATIONS"}],
)
def test_account_mass_assignment_forbidden(client, headers, extra):
    result = client.post(
        PATH + "/accounts",
        headers=headers,
        json={"name": "Injected", "account_type": "CHECKING", **extra},
    )
    assert result.status_code == 422


def test_cross_user_lifecycle_and_nonempty_close(client, headers):
    assert (
        client.patch(f"{PATH}/accounts/{BOB}", headers=headers, json={"name": "Stolen"}).status_code
        == 404
    )
    assert (
        client.post(
            f"{PATH}/accounts/{BOB}/close", headers=headers, json={"confirmed": True}
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"{PATH}/accounts/{ALICE}/close", headers=headers, json={"confirmed": True}
        ).json()["error"]["code"]
        == "ACCOUNT_NOT_EMPTY"
    )


def test_role_enforcement_freeze_replay_and_incoming_policy(client, headers, db):
    first = send(client, headers)
    path = f"{PATH}/ops/accounts/{ALICE}"
    reason = {"reason": "RISK_REVIEW"}
    assert client.post(path + "/freeze", headers=headers, json=reason).status_code == 403
    operator = auth(client, "operator@example.test")
    assert client.post(path + "/freeze", headers=operator, json={}).status_code == 422
    assert client.post(path + "/freeze", headers=operator, json=reason).json()["status"] == "FROZEN"
    assert send(client, headers).json() == first.json()
    rejected = send(client, headers, "frozen-new-intent")
    assert rejected.json()["error"]["code"] == "ACCOUNT_NOT_ACTIVE"
    bob = auth(client, "bob@example.test")
    assert (
        send(
            client,
            bob,
            "frozen-can-receive",
            {**BODY, "source_account_id": str(BOB), "destination_account_id": str(ALICE)},
        ).status_code
        == 201
    )
    assert send(client, operator, "operator-no-transfer").status_code == 403
    assert client.post(path + "/unfreeze", headers=operator, json=reason).status_code == 200
    assert send(client, headers, "frozen-new-intent").json() == rejected.json()
    assert client.get(PATH + "/audit/events", headers=headers).status_code == 403
    auditor = auth(client, "auditor@example.test")
    events = client.get(PATH + "/audit/events", headers=auditor).json()
    assert {e["action"] for e in events} >= {
        "ACCOUNT_FROZEN",
        "ACCOUNT_UNFROZEN",
        "TRANSFER_POSTED",
    }
    assert all(e["request_id"] for e in events)
    assert "password" not in str(events)
    assert client.post(path + "/freeze", headers=auditor, json=reason).status_code == 403
    assert_integrity(db)


def test_daily_limit_is_serialized_and_rejection_replays(client, headers, db):
    response = client.patch(
        f"{PATH}/accounts/{ALICE}", headers=headers, json={"daily_outgoing_limit_vnd": 2000000}
    )
    assert response.status_code == 200
    results = parallel(
        headers, [{**BODY, "amount_vnd": 1000000}] * 8, [f"daily-limit-{i}" for i in range(8)]
    )
    assert [r.status_code for r in results].count(201) == 2
    assert [r.status_code for r in results].count(409) == 6
    assert {r.json()["error"]["code"] for r in results if r.status_code == 409} == {
        "TRANSFER_LIMIT_EXCEEDED"
    }
    assert balances(db) == [3000000, 5000000]
    assert_integrity(db)


@pytest.mark.parametrize("limit", [0, -1, True, 1.5, "100", 9007199254740992])
def test_daily_limit_validation(client, headers, limit):
    assert (
        client.patch(
            f"{PATH}/accounts/{ALICE}", headers=headers, json={"daily_outgoing_limit_vnd": limit}
        ).status_code
        == 422
    )


def test_audit_is_immutable(client, headers):
    opened(client, headers)
    with pytest.raises(DBAPIError), SessionLocal.begin() as session:
        session.execute(text("DELETE FROM audit_events"))
    with pytest.raises(DBAPIError), SessionLocal.begin() as session:
        session.execute(text("UPDATE audit_events SET action='changed'"))


def test_closure_racing_incoming_credit_is_serialized(client, headers, db):
    account = opened(client, headers)
    barrier = Barrier(2)

    def attempt(close):
        with TestClient(app, headers=ORIGIN) as peer:
            barrier.wait(timeout=15)
            if close:
                return peer.post(
                    f"{PATH}/accounts/{account['id']}/close",
                    headers=headers,
                    json={"confirmed": True},
                )
            return send(
                peer,
                headers,
                "close-racing-credit",
                {**BODY, "amount_vnd": 1, "destination_account_id": account["id"]},
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        closed, posted = list(pool.map(attempt, [True, False]))
    assert (closed.status_code, posted.status_code) in {(200, 409), (409, 201)}
    row = db.get(Account, uuid.UUID(account["id"]))
    assert (row.status, row.balance_vnd) in {("CLOSED", 0), ("ACTIVE", 1)}
    assert db.scalar(select(func.sum(Account.balance_vnd))) == 8000000
    assert db.scalar(select(func.count()).select_from(LedgerEntry)) == (
        2 if posted.status_code == 201 else 0
    )


def test_invalid_transfer_configuration_is_rejected():
    with pytest.raises(ValueError, match="Minimum transfer amount"):
        Settings(jwt_secret="x" * 32, transfer_min_vnd=100, transfer_max_vnd=99, _env_file=None)


def test_upgrade_preserves_seeded_v1_posting():
    # Dedicated throwaway DB: never downgrade/reset the interactive demo or pytest DB.
    database = "upgrade_" + uuid.uuid4().hex + "_test"
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
        admin.execute(text(f'CREATE DATABASE "{database}"'))
    upgrade_engine = create_engine(engine.url.set(database=database))
    config = Config("alembic.ini")
    try:
        with upgrade_engine.connect() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "001")
            connection.execute(
                text("""INSERT INTO users (id,email,password_hash,display_name)
                VALUES (:id,'v1@example.test','synthetic','V1')"""),
                {"id": ALICE},
            )
            connection.execute(
                text("""INSERT INTO accounts (id,user_id,account_number,name,balance_vnd)
                VALUES (:a,:a,'V1-A','Original',85), (:b,:a,'V1-B','Savings',15)"""),
                {"a": ALICE, "b": BOB},
            )
            transfer = uuid.uuid4()
            connection.execute(
                text("""INSERT INTO transfers
                (id,reference,initiated_by_user_id,source_account_id,destination_account_id,amount_vnd,status)
                VALUES (:id,'V1-REF',:a,:a,:b,15,'SUCCEEDED')"""),
                {"id": transfer, "a": ALICE, "b": BOB},
            )
            connection.execute(
                text("""INSERT INTO ledger_entries (id,transfer_id,account_id,direction,amount_vnd)
                VALUES (:x,:t,:a,'DEBIT',15), (:y,:t,:b,'CREDIT',15)"""),
                {"x": uuid.uuid4(), "y": uuid.uuid4(), "t": transfer, "a": ALICE, "b": BOB},
            )
            connection.commit()
            command.upgrade(config, "head")
            assert connection.scalar(text("SELECT count(*) FROM transfers")) == 1
            assert connection.scalar(text("SELECT count(*) FROM ledger_entries")) == 2
            assert list(
                connection.execute(
                    text("SELECT balance_vnd FROM accounts ORDER BY account_number")
                ).scalars()
            ) == [85, 15]
            assert connection.scalar(text("SELECT role FROM users")) == "CUSTOMER"
            assert connection.scalar(text("SELECT status FROM accounts LIMIT 1")) == "ACTIVE"
            assert list(
                connection.execute(
                    text("SELECT opening_balance_vnd FROM accounts ORDER BY account_number")
                ).scalars()
            ) == [100, 0]
    finally:
        upgrade_engine.dispose()
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as admin:
            admin.execute(text(f'DROP DATABASE "{database}" WITH (FORCE)'))


def test_database_unavailable_returns_safe_retryable_contract(client, headers, monkeypatch):
    from sqlalchemy.exc import OperationalError

    from app import repositories

    def unavailable(*args):
        raise OperationalError("PRIVATE SQL", {"secret": "hidden"}, Exception("credentials"))

    monkeypatch.setattr(repositories, "owned_accounts", unavailable)
    response = client.get(PATH + "/accounts", headers=headers)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SERVICE_UNAVAILABLE"
    assert response.headers["X-Request-ID"] == response.json()["error"]["request_id"]
    assert all(value not in response.text for value in ("PRIVATE", "secret", "credentials"))
