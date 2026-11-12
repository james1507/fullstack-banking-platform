import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, func, select, text, update
from sqlalchemy.exc import DBAPIError

from app.config import settings
from app.db import SessionLocal, engine
from app.main import app
from app.models import Account, IdempotencyRecord, LedgerEntry, RefreshSession, Transfer
from app.schemas import TransferInput
from app.security import COOKIE, COOKIE_PATH
from app.seed import ALICE, BOB, seed
from app.transfers import request_hash
from tests.conftest import ORIGIN, auth

PATH = "/api/v1"
BODY = {
    "source_account_id": str(ALICE),
    "destination_account_id": str(BOB),
    "amount_vnd": 150000,
    "memo": "Demo transfer",
}


def send(client, headers, key="test-key-0001", body=None):
    return client.post(
        PATH + "/transfers",
        json=BODY if body is None else body,
        headers={**headers, "Idempotency-Key": key},
    )


def balances(db):
    db.expire_all()
    return [db.get(Account, id).balance_vnd for id in [ALICE, BOB]]


def assert_integrity(db):
    db.expire_all()
    assert sum(balances(db)) == 8_000_000
    assert db.scalar(select(func.count()).select_from(Account).where(Account.balance_vnd < 0)) == 0
    transfers = list(db.scalars(select(Transfer)))
    for transfer in transfers:
        entries = list(
            db.scalars(select(LedgerEntry).where(LedgerEntry.transfer_id == transfer.id))
        )
        assert len(entries) == 2
        assert {e.direction for e in entries} == {"DEBIT", "CREDIT"}
        assert all(e.amount_vnd == transfer.amount_vnd for e in entries)
        assert (
            next(e.account_id for e in entries if e.direction == "DEBIT")
            == transfer.source_account_id
        )
        assert (
            next(e.account_id for e in entries if e.direction == "CREDIT")
            == transfer.destination_account_id
        )
    assert db.scalar(select(func.count()).select_from(LedgerEntry)) == len(transfers) * 2


def test_health_seed_is_repeatable(client, db):
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    seed()
    assert client.get("/health/live").status_code == 200
    assert (
        client.get("/health/ready").json()["migration"]
        == ScriptDirectory.from_config(Config("alembic.ini")).get_current_head()
    )
    assert db.scalar(select(func.count()).select_from(Account)) == 2
    assert balances(db) == [5_000_000, 3_000_000]


def test_login_profile_and_wrong_password(client, headers):
    assert client.get(PATH + "/auth/me", headers=headers).json()["email"] == "alice@example.test"
    bad = client.post(PATH + "/auth/login", json={"email": "alice@example.test", "password": "bad"})
    assert bad.status_code == 401
    assert "password" not in str(bad.json()["error"]["details"])
    assert (
        client.post(
            PATH + "/auth/login", json={"email": " ALICE@EXAMPLE.TEST ", "password": "DemoPass123!"}
        ).status_code
        == 200
    )


@pytest.mark.parametrize("variant", ["missing", "invalid", "expired", "audience", "issuer", "none"])
def test_access_tokens_rejected(client, variant):
    now = datetime.now(UTC)
    claims = {
        "sub": "10000000-0000-4000-8000-000000000001",
        "iat": now,
        "exp": now + timedelta(minutes=2),
        "iss": "banking-demo",
        "aud": "banking-web",
        "jti": str(uuid.uuid4()),
    }
    if variant == "expired":
        claims["exp"] = now - timedelta(seconds=1)
    if variant == "audience":
        claims["aud"] = "other"
    if variant == "issuer":
        claims["iss"] = "other"
    token = jwt.encode(claims, settings().jwt_secret, algorithm="HS256")
    if variant == "invalid":
        token = "bad"
    if variant == "none":
        token = jwt.encode(claims, key="", algorithm="none")
    headers = {} if variant == "missing" else {"Authorization": "Bearer " + token}
    assert client.get(PATH + "/accounts", headers=headers).status_code == 401


def test_refresh_rotation_reuse_revokes_family(client, headers, db):
    old = client.cookies.get(COOKIE)
    rotated = client.post(PATH + "/auth/refresh")
    assert rotated.status_code == 200
    new = client.cookies.get(COOKIE)
    assert old != new
    assert "httponly" in rotated.headers["set-cookie"].lower()
    assert "samesite=strict" in rotated.headers["set-cookie"].lower()
    client.cookies.set(COOKIE, old, domain="testserver.local", path=COOKIE_PATH)
    assert client.post(PATH + "/auth/refresh").json()["error"]["code"] == "REFRESH_REUSED"
    client.cookies.set(COOKIE, new, domain="testserver.local", path=COOKIE_PATH)
    assert client.post(PATH + "/auth/refresh").status_code == 401
    assert all(s.token_hash not in {old, new} for s in db.scalars(select(RefreshSession)))


def test_refresh_expiry_logout_and_origin(client, headers, db):
    assert (
        client.post(PATH + "/auth/refresh", headers={"Origin": "https://evil.test"}).status_code
        == 403
    )
    assert (
        client.post(PATH + "/auth/logout", headers={"Origin": "https://evil.test"}).status_code
        == 403
    )
    db.execute(update(RefreshSession).values(expires_at=datetime.now(UTC) - timedelta(days=1)))
    db.commit()
    assert client.post(PATH + "/auth/refresh").status_code == 401
    auth(client)
    assert client.post(PATH + "/auth/logout").status_code == 204
    assert client.cookies.get(COOKIE) is None
    assert client.post(PATH + "/auth/refresh").status_code == 401


def test_rate_limit(client):
    for _ in range(10):
        assert (
            client.post(
                PATH + "/auth/login", json={"email": "nobody@example.test", "password": "bad"}
            ).status_code
            == 401
        )
    assert (
        client.post(
            PATH + "/auth/login", json={"email": "nobody@example.test", "password": "bad"}
        ).status_code
        == 429
    )


def test_account_isolation_and_invisible_transfer(client, headers):
    assert [a["id"] for a in client.get(PATH + "/accounts", headers=headers).json()] == [str(ALICE)]
    assert client.get(f"{PATH}/accounts/{BOB}", headers=headers).status_code == 404
    assert (
        send(
            client,
            headers,
            body={**BODY, "source_account_id": str(BOB), "destination_account_id": str(ALICE)},
        ).status_code
        == 404
    )
    assert client.get(f"{PATH}/transfers?account_id={BOB}", headers=headers).status_code == 404
    assert client.get(f"{PATH}/transfers/{uuid.uuid4()}", headers=headers).status_code == 404


def test_success_and_exact_replay(client, headers, db):
    first = send(client, headers)
    assert first.status_code == 201, first.text
    for _ in range(12):
        replay = send(client, headers)
        assert replay.status_code == 201
        assert replay.json() == first.json()
        assert replay.headers["X-Idempotency-Replayed"] == "true"
    assert balances(db) == [4_850_000, 3_150_000]
    assert db.scalar(select(func.count()).select_from(Transfer)) == 1
    assert_integrity(db)
    assert (
        send(client, headers, body={**BODY, "amount_vnd": 100}).json()["error"]["code"]
        == "IDEMPOTENCY_KEY_REUSED"
    )


def test_insufficient_funds_saved_even_after_balance_changes(client, headers, db):
    body = {**BODY, "amount_vnd": 6_000_000}
    first = send(client, headers, body=body)
    assert first.status_code == 409
    assert first.json()["error"]["code"] == "INSUFFICIENT_FUNDS"
    bob_headers = auth(client, "bob@example.test")
    assert (
        send(
            client,
            bob_headers,
            "fund-alice-0001",
            {
                **BODY,
                "source_account_id": str(BOB),
                "destination_account_id": str(ALICE),
                "amount_vnd": 2_000_000,
            },
        ).status_code
        == 201
    )
    assert send(client, headers, body=body).json() == first.json()
    assert balances(db) == [7_000_000, 1_000_000]
    assert_integrity(db)


@pytest.mark.parametrize(
    "changes,status",
    [
        ({"amount_vnd": 0}, 422),
        ({"amount_vnd": -1}, 422),
        ({"amount_vnd": True}, 422),
        ({"amount_vnd": 1.1}, 422),
        ({"amount_vnd": "10"}, 422),
        ({"amount_vnd": 9007199254740992}, 422),
        ({"memo": "x" * 201}, 422),
        ({"destination_account_id": "bad"}, 422),
        ({"destination_account_id": str(ALICE)}, 422),
        ({"destination_account_id": str(uuid.UUID(int=55))}, 404),
    ],
)
def test_invalid_transfer(client, headers, db, changes, status):
    assert send(client, headers, body={**BODY, **changes}).status_code == status
    assert balances(db) == [5_000_000, 3_000_000]
    assert_integrity(db)


def test_missing_fields_key_and_unknown_fields(client, headers):
    assert client.post(PATH + "/transfers", headers=headers, json=BODY).status_code == 422
    assert send(client, headers, key="contains space").status_code == 422
    assert send(client, headers, body={"amount_vnd": 5}).status_code == 422
    assert send(client, headers, body={**BODY, "balance_vnd": 0}).status_code == 422


def parallel(headers, bodies, keys):
    barrier = Barrier(len(keys))

    def worker(args):
        body, key, actor = args
        with TestClient(app, headers=ORIGIN) as c:
            barrier.wait(timeout=20)
            return send(c, actor, key, body)

    actors = headers if isinstance(headers, list) else [headers] * len(keys)
    with ThreadPoolExecutor(max_workers=len(keys)) as pool:
        return list(pool.map(worker, zip(bodies, keys, actors, strict=True)))


def test_twenty_four_parallel_same_key(client, headers, db):
    results = parallel(headers, [BODY] * 24, ["parallel-same-0001"] * 24)
    assert {r.status_code for r in results} == {201}
    assert len({r.json()["id"] for r in results}) == 1
    assert balances(db) == [4_850_000, 3_150_000]
    assert_integrity(db)


def test_parallel_distinct_keys_cannot_overdraw(client, headers, db):
    results = parallel(
        headers, [{**BODY, "amount_vnd": 1_000_000}] * 12, [f"distinct-key-{i}" for i in range(12)]
    )
    assert [r.status_code for r in results].count(201) == 5
    assert [r.status_code for r in results].count(409) == 7
    assert balances(db) == [0, 8_000_000]
    assert_integrity(db)


def test_opposite_direction_no_deadlock(client, headers, db):
    bob_headers = auth(client, "bob@example.test")
    incoming = {**BODY, "source_account_id": str(BOB), "destination_account_id": str(ALICE)}
    results = parallel(
        [headers, bob_headers] * 8, [BODY, incoming] * 8, [f"opposite-key-{i}" for i in range(16)]
    )
    assert {r.status_code for r in results} == {201}
    assert balances(db) == [5_000_000, 3_000_000]
    assert_integrity(db)


def test_injected_failure_rolls_back_everything(client, headers, db):
    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO ledger_entries"):
            raise RuntimeError("injected failure")

    event.listen(engine, "before_cursor_execute", fail)
    try:
        response = send(client, headers)
    finally:
        event.remove(engine, "before_cursor_execute", fail)
    assert response.status_code == 500
    assert "injected" not in response.text
    assert balances(db) == [5_000_000, 3_000_000]
    assert db.scalar(select(func.count()).select_from(IdempotencyRecord)) == 0
    assert_integrity(db)
    db.rollback()
    assert send(client, headers).status_code == 201


def test_database_ledger_immutable_and_balanced(client, headers, db):
    assert send(client, headers).status_code == 201
    with pytest.raises(DBAPIError), SessionLocal.begin() as s:
        s.execute(text("UPDATE ledger_entries SET amount_vnd = 1"))
    with pytest.raises(DBAPIError), SessionLocal.begin() as s:
        s.execute(text("DELETE FROM ledger_entries"))
    with pytest.raises(DBAPIError), SessionLocal.begin() as s:
        s.add(
            Transfer(
                id=uuid.uuid4(),
                reference="unbalanced",
                initiated_by_user_id=uuid.UUID("10000000-0000-4000-8000-000000000001"),
                source_account_id=ALICE,
                destination_account_id=BOB,
                amount_vnd=1,
                status="SUCCEEDED",
            )
        )
    assert_integrity(db)


def test_history_filters_pagination_and_summary(client, headers):
    references = [
        send(client, headers, f"history-key-{i}", {**BODY, "memo": f"Transfer {i}"}).json()[
            "reference"
        ]
        for i in range(3)
    ]
    result = client.get(PATH + "/transfers?page_size=2", headers=headers).json()
    assert result["total"] == 3 and result["total_pages"] == 2 and len(result["items"]) == 2
    second = client.get(PATH + "/transfers?page=2&page_size=2", headers=headers).json()
    assert len(second["items"]) == 1
    assert not {t["id"] for t in result["items"]} & {t["id"] for t in second["items"]}
    assert client.get(PATH + "/transfers?direction=INCOMING", headers=headers).json()["total"] == 0
    assert client.get(PATH + "/transfers?direction=OUTGOING", headers=headers).json()["total"] == 3
    assert (
        client.get(PATH + "/transfers?reference=" + references[0], headers=headers).json()["total"]
        == 1
    )
    summary = client.get(PATH + "/dashboard/summary", headers=headers).json()
    assert summary["total_balance_vnd"] == 4_550_000 and summary["transfer_count"] == 3
    bob_headers = auth(client, "bob@example.test")
    assert (
        client.get(PATH + "/transfers?direction=INCOMING", headers=bob_headers).json()["total"] == 3
    )


def test_hash_normalizes_memo_and_separates_owner():
    a = TransferInput(**{**BODY, "memo": " rent "})
    b = TransferInput(**{**BODY, "memo": "rent"})
    assert request_hash(ALICE, a) == request_hash(ALICE, b)
    assert request_hash(ALICE, a) != request_hash(BOB, b)


def test_existing_transfer_hidden_from_unrelated_user(client, headers, db):
    from app.models import User
    from app.security import password_hasher

    carol_id, carol_account_id = uuid.uuid4(), uuid.uuid4()
    db.add(
        User(
            id=carol_id,
            email="carol@example.test",
            display_name="Carol",
            password_hash=password_hasher.hash("DemoPass123!"),
            is_active=True,
        )
    )
    db.flush()
    db.add(
        Account(
            id=carol_account_id,
            user_id=carol_id,
            account_number="DEMO-300001",
            name="Everyday account",
            balance_vnd=0,
            currency="VND",
        )
    )
    db.commit()
    transfer = send(
        client,
        headers,
        "visibility-key-01",
        {**BODY, "destination_account_id": str(carol_account_id)},
    ).json()
    bob = auth(client, "bob@example.test")
    assert client.get(f"{PATH}/transfers/{transfer['id']}", headers=bob).status_code == 404
    assert client.get(PATH + "/transfers", headers=bob).json()["total"] == 0
    carol = auth(client, "carol@example.test")
    assert client.get(f"{PATH}/transfers/{transfer['id']}", headers=carol).status_code == 200
    assert client.get(PATH + "/transfers?direction=INCOMING", headers=carol).json()["total"] == 1


def test_concurrent_refresh_reuse_revokes_new_token(client, headers):
    raw = client.cookies.get(COOKIE)
    barrier = Barrier(2)

    def rotate(_):
        with TestClient(app, headers=ORIGIN) as c:
            c.cookies.set(COOKIE, raw, domain="testserver.local", path=COOKIE_PATH)
            barrier.wait(timeout=10)
            response = c.post(PATH + "/auth/refresh")
            return response, c.cookies.get(COOKIE)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(rotate, range(2)))
    assert sorted(response.status_code for response, _ in results) == [200, 401]
    new_raw = next(raw for response, raw in results if response.status_code == 200)
    client.cookies.set(COOKIE, new_raw, domain="testserver.local", path=COOKIE_PATH)
    assert client.post(PATH + "/auth/refresh").status_code == 401
