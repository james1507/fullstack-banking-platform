import uuid

from sqlalchemy import func, select

from app.config import settings
from app.models import Beneficiary, IdempotencyRecord, Transfer
from app.seed import ALICE, BOB
from tests.conftest import auth
from tests.test_platform import BODY, PATH, assert_integrity, balances, send


def saved(client, headers):
    response = client.post(
        PATH + "/beneficiaries",
        headers=headers,
        json={"destination_account_id": str(BOB), "nickname": "Rent recipient"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_beneficiary_search_archive_restore_and_owner_scope(client, headers, db):
    row = saved(client, headers)
    url = PATH + "/beneficiaries/" + row["id"]
    bob = auth(client, "bob@example.test")
    assert client.patch(url, headers=bob, json={"nickname": "Stolen"}).status_code == 404
    assert client.delete(url, headers=bob).status_code == 404
    assert client.post(url + "/restore", headers=bob).status_code == 404
    assert client.get(PATH + "/beneficiaries", headers=bob).json() == []
    assert (
        client.get(PATH + "/beneficiaries?search=RENT", headers=headers).json()[0]["id"]
        == row["id"]
    )
    assert client.get(PATH + "/beneficiaries?search=%25", headers=headers).json() == []
    assert client.patch(url, headers=headers, json={"nickname": "Monthly plan"}).status_code == 200
    assert client.delete(url, headers=headers).json()["archived_at"]
    assert client.get(PATH + "/beneficiaries", headers=headers).json() == []
    assert (
        len(client.get(PATH + "/beneficiaries?include_archived=true", headers=headers).json()) == 1
    )
    assert client.post(url + "/restore", headers=headers).json()["archived_at"] is None
    assert send(client, headers).status_code == 201
    db.expire_all()
    assert db.get(Beneficiary, uuid.UUID(row["id"])).last_used_at is not None
    assert_integrity(db)


def test_beneficiary_duplicate_and_privacy_validation(client, headers, db):
    saved(client, headers)
    duplicate = client.post(
        PATH + "/beneficiaries",
        headers=headers,
        json={"destination_account_id": str(BOB), "nickname": "Another name"},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "BENEFICIARY_EXISTS"
    for extra in ({"user_id": str(ALICE)}, {"balance_vnd": 5}):
        assert (
            client.post(
                PATH + "/beneficiaries",
                headers=headers,
                json={"destination_account_id": str(BOB), "nickname": "Name", **extra},
            ).status_code
            == 422
        )
    unavailable = client.post(
        PATH + "/beneficiaries",
        headers=headers,
        json={"destination_account_id": str(uuid.uuid4()), "nickname": "Name"},
    )
    assert unavailable.status_code == 404
    assert "email" not in str(duplicate.json())
    assert db.scalar(select(func.count()).select_from(Transfer)) == 0


def test_preview_is_read_only_and_freeze_is_rechecked(client, headers, db):
    preview = client.post(PATH + "/transfers/preview", headers=headers, json=BODY)
    assert preview.status_code == 200
    assert preview.json()["destination_masked_number"] == "••••0001"
    assert preview.json()["estimated_balance_vnd"] == 4_850_000
    assert "bob@example.test" not in preview.text
    assert balances(db) == [5_000_000, 3_000_000]
    assert db.scalar(select(func.count()).select_from(IdempotencyRecord)) == 0
    operator = auth(client, "operator@example.test")
    assert (
        client.post(
            f"{PATH}/ops/accounts/{ALICE}/freeze", headers=operator, json={"reason": "RISK_REVIEW"}
        ).status_code
        == 200
    )
    assert send(client, headers).json()["error"]["code"] == "ACCOUNT_NOT_ACTIVE"
    assert client.post(PATH + "/transfers/preview", headers=headers, json=BODY).status_code == 409
    assert_integrity(db)


def test_preview_idor_limits_and_lookup_scope(client, headers, db, monkeypatch):
    assert (
        client.post(
            PATH + "/transfers/preview",
            headers=headers,
            json={**BODY, "source_account_id": str(BOB), "destination_account_id": str(ALICE)},
        ).status_code
        == 404
    )
    monkeypatch.setattr(settings(), "transfer_max_vnd", 100)
    assert (
        client.post(PATH + "/transfers/preview", headers=headers, json=BODY).json()["error"]["code"]
        == "TRANSFER_LIMIT_INVALID"
    )
    monkeypatch.setattr(settings(), "transfer_max_vnd", 9007199254740991)
    first = send(client, headers)
    own = client.get(PATH + "/transfers/lookup-by-key?key=test-key-0001", headers=headers)
    assert own.json() == {"status_code": 201, "response": first.json()}
    bob = auth(client, "bob@example.test")
    assert (
        client.get(PATH + "/transfers/lookup-by-key?key=test-key-0001", headers=bob).status_code
        == 404
    )
    assert (
        client.get(
            PATH + "/transfers/lookup-by-key?key=unknown-key-0001", headers=headers
        ).status_code
        == 404
    )
    assert (
        client.get(PATH + "/transfers/lookup-by-key?key=invalid%20key", headers=headers).status_code
        == 422
    )
    assert_integrity(db)


def test_recipient_lookup_throttling(client, headers):
    for _ in range(30):
        assert (
            client.post(PATH + "/transfers/preview", headers=headers, json=BODY).status_code == 200
        )
    assert client.post(PATH + "/transfers/preview", headers=headers, json=BODY).status_code == 429
