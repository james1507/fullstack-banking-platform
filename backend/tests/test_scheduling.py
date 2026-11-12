"""Deterministic clocks, independent workers and actual PostgreSQL recovery."""

import multiprocessing
import os
import uuid
from concurrent.futures import ProcessPoolExecutor
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import event, func, select, update

from app import worker
from app.db import SessionLocal, engine
from app.errors import APIError
from app.models import (
    Account,
    Notification,
    OutboxEvent,
    ScheduleOccurrence,
    Transfer,
    TransferSchedule,
)
from app.scheduling import local_instant, next_instant
from app.schemas import TransferInput
from app.seed import ALICE
from app.transfers import execute_transfer
from tests.conftest import auth
from tests.test_platform import BODY, PATH, assert_integrity, balances
from tests.test_recovery import start_together


def schedule(client, headers, **overrides):
    due = datetime.now(UTC) + timedelta(hours=1)
    payload = {
        **BODY,
        "timezone": "UTC",
        "starts_local": due.replace(tzinfo=None).isoformat(),
        "recurrence": "ONCE",
        "max_runs": 1,
        **overrides,
    }
    response = client.post(
        PATH + "/scheduled-transfers",
        headers={**headers, "Idempotency-Key": str(uuid.uuid4())},
        json=payload,
    )
    assert response.status_code == 201, response.text
    return response.json()


def clock(row):
    return datetime.fromisoformat(row["next_run_at"])


def detail(client, headers, row):
    response = client.get(f"{PATH}/scheduled-transfers/{row['id']}", headers=headers)
    assert response.status_code == 200
    return response.json()


def test_creation_no_debit_and_clock_boundary(client, headers, db):
    row = schedule(client, headers)
    assert balances(db) == [5000000, 3000000]
    assert not worker.tick(clock(row) - timedelta(microseconds=1))
    assert worker.tick(clock(row))
    assert worker.claim(ScheduleOccurrence, clock(row) + timedelta(seconds=1)) is None
    result = detail(client, headers, row)
    assert result["schedule"]["status"] == "COMPLETED"
    assert result["occurrences"][0]["state"] == "SUCCEEDED"
    db.expire_all()
    assert balances(db) == [4850000, 3150000]
    assert_integrity(db)


@pytest.mark.parametrize("local", ["2026-03-08T02:30:00", "2026-03-08T02:59:59"])
def test_nonexistent_clock_rejected(local):
    with pytest.raises(APIError, match="local time"):
        local_instant(datetime.fromisoformat(local), "America/New_York")


def test_recurrence_month_end_dst_and_coalescing():
    row = SimpleNamespace(
        starts_local=datetime(2026, 1, 31, 9), recurrence="MONTHLY", timezone="UTC"
    )
    assert next_instant(row, datetime(2026, 1, 31, 9, tzinfo=UTC)) == datetime(
        2026, 2, 28, 9, tzinfo=UTC
    )
    assert next_instant(row, datetime(2026, 2, 28, 9, tzinfo=UTC)) == datetime(
        2026, 3, 31, 9, tzinfo=UTC
    )
    assert next_instant(row, datetime(2026, 6, 1, tzinfo=UTC)) == datetime(
        2026, 6, 30, 9, tzinfo=UTC
    )
    row = SimpleNamespace(
        starts_local=datetime(2026, 3, 1, 2, 30), recurrence="WEEKLY", timezone="America/New_York"
    )
    assert next_instant(row, datetime(2026, 3, 2, tzinfo=UTC)) == datetime(
        2026, 3, 15, 6, 30, tzinfo=UTC
    )
    assert local_instant(datetime(2026, 11, 1, 1, 30), "America/New_York") == datetime(
        2026, 11, 1, 5, 30, tzinfo=UTC
    )


def test_business_failure_is_terminal_and_not_retried(client, headers, db):
    row = schedule(client, headers, amount_vnd=6000000)
    worker.tick(clock(row))
    result = detail(client, headers, row)
    assert result["occurrences"][0]["state"] == "FAILED_PERMANENT"
    assert result["occurrences"][0]["last_error_code"] == "INSUFFICIENT_FUNDS"
    worker.tick(clock(row) + timedelta(hours=1))
    assert db.scalar(select(func.count()).select_from(Transfer)) == 0
    assert balances(db) == [5000000, 3000000]


def test_scope_roles_mass_assignment_and_stale_edits(client, headers):
    row = schedule(client, headers)
    url = f"{PATH}/scheduled-transfers/{row['id']}"
    bob = auth(client, "bob@example.test")
    assert client.get(url, headers=bob).status_code == 404
    assert (
        client.post(
            url + "/cancel", headers=bob, json={"version": 1, "confirmed": True}
        ).status_code
        == 404
    )
    operator = auth(client, "operator@example.test")
    assert client.get(PATH + "/scheduled-transfers", headers=operator).status_code == 403
    assert (
        client.post(
            PATH + "/scheduled-transfers", headers=headers, json={**BODY, "user_id": str(ALICE)}
        ).status_code
        == 422
    )
    paused = client.post(url + "/pause", headers=headers, json={"version": 1, "confirmed": True})
    assert paused.status_code == 200
    assert (
        client.post(
            url + "/resume", headers=headers, json={"version": 1, "confirmed": True}
        ).json()["error"]["code"]
        == "STALE_VERSION"
    )
    assert (
        client.post(
            url + "/resume", headers=headers, json={"version": 2, "confirmed": True}
        ).status_code
        == 200
    )
    assert (
        client.post(
            url + "/cancel", headers=headers, json={"version": 3, "confirmed": True}
        ).status_code
        == 200
    )
    assert not worker.tick(clock(row))


def test_edit_only_future_cancelled_slot_and_claim_fence(client, headers, db):
    row = schedule(client, headers)
    url = f"{PATH}/scheduled-transfers/{row['id']}"
    payload = {
        key: row[key]
        for key in (*BODY.keys(), "timezone", "starts_local", "recurrence", "max_runs")
    }
    changed = client.patch(url, headers=headers, json={**payload, "amount_vnd": 100, "version": 1})
    assert changed.status_code == 200, changed.text
    lease = worker.claim(ScheduleOccurrence, clock(row))
    assert lease
    busy = client.patch(url, headers=headers, json={**payload, "version": 2})
    assert busy.json()["error"]["code"] == "SCHEDULE_BUSY"
    assert (
        client.post(
            url + "/cancel", headers=headers, json={"version": 2, "confirmed": True}
        ).status_code
        == 200
    )
    worker.execute_occurrence(*lease, clock(row))
    assert db.scalar(select(func.count()).select_from(Transfer)) == 0
    assert {item["state"] for item in detail(client, headers, row)["occurrences"]} == {"CANCELLED"}


def test_closure_requires_owned_schedules_cancelled(client, headers):
    account = client.post(
        PATH + "/accounts",
        headers=headers,
        json={"name": "Scheduled savings", "account_type": "SAVINGS"},
    ).json()
    row = schedule(client, headers, source_account_id=account["id"])
    url = f"{PATH}/accounts/{account['id']}/close"
    assert (
        client.post(url, headers=headers, json={"confirmed": True}).json()["error"]["code"]
        == "ACCOUNT_HAS_SCHEDULES"
    )
    client.post(
        f"{PATH}/scheduled-transfers/{row['id']}/cancel",
        headers=headers,
        json={"version": 1, "confirmed": True},
    )
    assert client.post(url, headers=headers, json={"confirmed": True}).status_code == 200


def parallel_tick(now):
    return worker.tick(now)


def test_four_workers_one_money_effect(client, headers, db):
    row = schedule(client, headers)
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(
        max_workers=4,
        mp_context=context,
        initializer=start_together,
        initargs=(context.Barrier(4),),
    ) as pool:
        list(pool.map(parallel_tick, [clock(row)] * 8))
    assert db.scalar(select(func.count()).select_from(Transfer)) == 1
    assert balances(db) == [4850000, 3150000]
    assert_integrity(db)


def killed_worker(now, after_commit):
    lease = worker.claim(ScheduleOccurrence, now)
    if not after_commit:

        def crash(connection, cursor, statement, parameters, context, executemany):
            if statement.startswith("INSERT INTO ledger_entries"):
                os._exit(86)

        event.listen(engine, "before_cursor_execute", crash)
    worker.execute_occurrence(*lease, now)
    os._exit(87)


@pytest.mark.parametrize("after_commit", [False, True])
def test_process_death_reclaim_and_fenced_old_lease(client, headers, db, after_commit):
    row = schedule(client, headers)
    now = clock(row)
    process = multiprocessing.get_context("spawn").Process(
        target=killed_worker, args=(now, after_commit)
    )
    process.start()
    process.join(timeout=30)
    assert process.exitcode == (87 if after_commit else 86)
    assert balances(db) == ([4850000, 3150000] if after_commit else [5000000, 3000000])
    db.rollback()
    worker.tick(now + timedelta(seconds=61))
    assert db.scalar(select(func.count()).select_from(Transfer)) == 1
    assert balances(db) == [4850000, 3150000]
    assert_integrity(db)


def test_lease_fencing_replay_and_outbox_redelivery(client, headers, db):
    row = schedule(client, headers)
    now = clock(row)
    first = worker.claim(ScheduleOccurrence, now)
    second = worker.claim(ScheduleOccurrence, now + timedelta(seconds=61))
    assert first[0] == second[0] and first[1] != second[1]
    worker.execute_occurrence(*first, now)
    assert db.scalar(select(func.count()).select_from(Transfer)) == 0
    db.rollback()
    # Durable money result can be replayed even if an earlier worker never acknowledged it.
    with SessionLocal() as session:
        execute_transfer(
            session,
            uuid.UUID("10000000-0000-4000-8000-000000000001"),
            TransferInput(**BODY),
            f"schedule:{first[0]}",
            "lost-worker-ack",
        )
    worker.execute_occurrence(*second, now + timedelta(seconds=61))
    for _ in range(4):
        worker.tick(now + timedelta(seconds=62))
    assert db.scalar(select(func.count()).select_from(Transfer)) == 1
    notifications = db.scalar(select(func.count()).select_from(Notification))
    assert notifications == 3
    db.rollback()
    with SessionLocal.begin() as session:
        session.execute(update(OutboxEvent).values(state="PENDING", attempt_count=0))
    for _ in range(4):
        worker.tick(now + timedelta(seconds=63))
    assert db.scalar(select(func.count()).select_from(Notification)) == notifications
    assert_integrity(db)


def test_transient_backoff_bounded_and_business_policy_rechecked(client, headers, db):
    row = schedule(client, headers)
    now = clock(row)
    lease = worker.claim(ScheduleOccurrence, now)
    worker.fail_claim(ScheduleOccurrence, *lease, now)
    occurrence = db.get(ScheduleOccurrence, lease[0])
    assert now + timedelta(seconds=2) <= occurrence.available_at <= now + timedelta(seconds=3)
    assert worker.claim(ScheduleOccurrence, now) is None
    db.rollback()
    # Freeze after creation; execution must recheck, not rely on the original preview.
    with SessionLocal.begin() as session:
        session.get(Account, ALICE).status = "FROZEN"
    worker.tick(now + timedelta(seconds=4))
    assert detail(client, headers, row)["occurrences"][0]["last_error_code"] == "ACCOUNT_NOT_ACTIVE"
    assert db.scalar(select(func.count()).select_from(Transfer)) == 0


def test_exhausted_lease_has_terminal_outcome(client, headers, db):
    row = schedule(client, headers)
    now = clock(row)
    for _ in range(5):
        lease = worker.claim(ScheduleOccurrence, now)
        worker.fail_claim(ScheduleOccurrence, *lease, now)
        now += timedelta(minutes=10)
    worker.tick(now)
    assert detail(client, headers, row)["occurrences"][0]["last_error_code"] == "RETRY_EXHAUSTED"
    assert db.scalar(select(func.count()).select_from(Transfer)) == 0


def test_notifications_scope_cursor_and_idempotent_read(client, headers, db):
    row = schedule(client, headers)
    for _ in range(4):
        worker.tick(clock(row))
    inbox = client.get(PATH + "/notifications?page_size=1", headers=headers).json()
    assert inbox["unread_count"] == 2 and len(inbox["items"]) == 1
    other = client.get(
        PATH + "/notifications?page_size=1&cursor=" + inbox["next_cursor"], headers=headers
    ).json()
    assert other["items"][0]["id"] != inbox["items"][0]["id"]
    bob = auth(client, "bob@example.test")
    url = f"{PATH}/notifications/{inbox['items'][0]['id']}/read"
    assert client.post(url, headers=bob).status_code == 404
    assert (
        client.get(PATH + "/notifications?cursor=" + inbox["next_cursor"], headers=bob).status_code
        == 404
    )
    read = client.post(url, headers=headers)
    assert read.status_code == 200 and read.json()["read_at"]
    assert client.post(url, headers=headers).json()["read_at"] == read.json()["read_at"]
    assert client.post(PATH + "/notifications/read-all", headers=headers).json() == {"updated": 1}
    assert client.post(PATH + "/notifications/read-all", headers=headers).json() == {"updated": 0}
    assert client.get(PATH + "/notifications?cursor=bad", headers=headers).status_code == 400


def test_pause_fences_claim_and_resume_skips_missed_slots(client, headers, db):
    row = schedule(client, headers, recurrence="WEEKLY", max_runs=3)
    now = clock(row)
    lease = worker.claim(ScheduleOccurrence, now)
    url = f"{PATH}/scheduled-transfers/{row['id']}"
    paused = client.post(url + "/pause", headers=headers, json={"version": 1, "confirmed": True})
    assert paused.status_code == 200
    worker.execute_occurrence(*lease, now)
    assert db.scalar(select(func.count()).select_from(Transfer)) == 0
    db.rollback()
    # Controlled service clock for a resumed schedule after downtime.
    from app.models import User
    from app.scheduling import change_schedule
    from app.schemas import ScheduleAction

    with SessionLocal() as session:
        owner = session.get(User, uuid.UUID("10000000-0000-4000-8000-000000000001"))
        session.expunge(owner)
        session.rollback()
        resumed = change_schedule(
            session,
            owner,
            uuid.UUID(row["id"]),
            ScheduleAction(version=2, confirmed=True),
            "resume",
            "resume-clock",
            now=now + timedelta(days=15),
        )
    assert resumed.next_run_at == now + timedelta(days=21)
    assert not worker.tick(now + timedelta(days=15))
    assert worker.tick(now + timedelta(days=21))
    assert db.scalar(select(func.count()).select_from(Transfer)) == 1
    assert_integrity(db)


def killed_delivery(event_id, now):
    lease = worker.claim(OutboxEvent, now)
    assert lease[0] == event_id

    def crash(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE outbox_events"):
            os._exit(88)

    event.listen(engine, "before_cursor_execute", crash)
    worker.deliver_event(*lease, now)


def test_outbox_process_death_before_ack_recovers_without_duplicates(client, headers, db):
    from tests.test_platform import send

    assert send(client, headers).status_code == 201
    now = datetime.now(UTC) + timedelta(seconds=1)
    event_id = db.scalar(
        select(OutboxEvent.id).order_by(OutboxEvent.available_at, OutboxEvent.id).limit(1)
    )
    process = multiprocessing.get_context("spawn").Process(
        target=killed_delivery, args=(event_id, now)
    )
    process.start()
    process.join(timeout=30)
    assert process.exitcode == 88
    assert db.scalar(select(func.count()).select_from(Notification)) == 0
    db.rollback()
    for _ in range(3):
        worker.tick(now + timedelta(seconds=61))
    assert db.scalar(select(func.count()).select_from(Notification)) == 2
    assert db.scalar(select(func.count()).select_from(Transfer)) == 1
    assert_integrity(db)


def test_worker_cannot_bypass_current_actor_role(client, headers, db):
    from app.models import User

    row = schedule(client, headers)
    with SessionLocal.begin() as session:
        session.get(User, uuid.UUID("10000000-0000-4000-8000-000000000001")).role = "OPERATIONS"
    worker.tick(clock(row))
    assert db.scalar(select(func.count()).select_from(Transfer)) == 0
    occurrence = db.scalar(
        select(ScheduleOccurrence).where(ScheduleOccurrence.schedule_id == uuid.UUID(row["id"]))
    )
    assert occurrence.last_error_code == "FORBIDDEN" and occurrence.state == "FAILED_PERMANENT"


def test_schedule_creation_retry_after_due_preserves_one_plan(client, headers, db):
    row = schedule(client, headers)
    payload = {
        key: row[key]
        for key in (*BODY.keys(), "timezone", "starts_local", "recurrence", "max_runs")
    }
    from app.models import IdempotencyRecord, User
    from app.scheduling import create_schedule
    from app.schemas import ScheduleInput

    record = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.operation == "POST:/api/v1/scheduled-transfers"
        )
    )
    key = record.key
    owner = db.get(User, uuid.UUID("10000000-0000-4000-8000-000000000001"))
    db.expunge(owner)
    db.rollback()
    with SessionLocal() as session:
        replay = create_schedule(
            session,
            owner,
            ScheduleInput(**payload),
            "retry-after-due",
            key,
            now=clock(row) + timedelta(days=1),
        )
    assert replay == row
    conflict = client.post(
        PATH + "/scheduled-transfers",
        headers={**headers, "Idempotency-Key": key},
        json={**payload, "amount_vnd": 1},
    )
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
    assert db.scalar(select(func.count()).select_from(TransferSchedule)) == 1
    assert db.scalar(select(func.count()).select_from(ScheduleOccurrence)) == 1


def test_parallel_schedule_creation_claims_single_plan(headers, db):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from fastapi.testclient import TestClient

    from app.main import app
    from tests.conftest import ORIGIN

    barrier = Barrier(8)
    payload = {
        **BODY,
        "timezone": "UTC",
        "starts_local": (datetime.now(UTC) + timedelta(hours=1)).replace(tzinfo=None).isoformat(),
        "recurrence": "ONCE",
        "max_runs": 1,
    }

    def create(_):
        with TestClient(app, headers=ORIGIN) as peer:
            barrier.wait(timeout=15)
            return peer.post(
                PATH + "/scheduled-transfers",
                headers={**headers, "Idempotency-Key": "parallel-schedule-intent"},
                json=payload,
            )

    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(create, range(8)))
    assert {response.status_code for response in responses} == {201}
    assert len({response.json()["id"] for response in responses}) == 1
    assert db.scalar(select(func.count()).select_from(TransferSchedule)) == 1
    assert db.scalar(select(func.count()).select_from(ScheduleOccurrence)) == 1
    assert balances(db) == [5000000, 3000000]


@pytest.mark.parametrize(
    "local,zone",
    [
        (datetime.min, "Asia/Ho_Chi_Minh"),
        (datetime.max, "America/New_York"),
    ],
)
def test_local_calendar_overflow_rejected(local, zone):
    with pytest.raises(APIError) as caught:
        local_instant(local, zone)
    assert caught.value.status == 422
