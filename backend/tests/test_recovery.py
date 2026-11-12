"""Real independent processes: PostgreSQL is the synchronization boundary."""

import multiprocessing
import os
import uuid
from concurrent.futures import ProcessPoolExecutor

from sqlalchemy import event, func, select

from app.db import SessionLocal, engine
from app.models import IdempotencyRecord, Transfer
from app.schemas import TransferInput
from app.transfers import execute_transfer
from tests.test_platform import BODY, assert_integrity, balances, send

ACTOR = uuid.UUID("10000000-0000-4000-8000-000000000001")


def start_together(barrier):
    barrier.wait(timeout=30)


def process_batch(args):
    same_key, worker = args
    results = []
    for index in range(13 if same_key else 3):
        payload = TransferInput(**{**BODY, "amount_vnd": 150000 if same_key else 1000000})
        key = "process-same-key" if same_key else f"process-{worker}-{index}"
        with SessionLocal() as session:
            status, body, replay = execute_transfer(session, ACTOR, payload, key, str(uuid.uuid4()))
            results.append((status, body.get("id"), replay))
    return results


def abrupt_exit(after_commit):
    if not after_commit:

        def crash(connection, cursor, statement, parameters, context, executemany):
            if statement.startswith("INSERT INTO ledger_entries"):
                os._exit(86)

        event.listen(engine, "before_cursor_execute", crash)
    with SessionLocal() as session:
        execute_transfer(
            session, ACTOR, TransferInput(**BODY), "crash-recovery-key", "child-request"
        )
    os._exit(87)


def run_parallel(same_key):
    context = multiprocessing.get_context("spawn")
    with ProcessPoolExecutor(
        max_workers=4,
        mp_context=context,
        initializer=start_together,
        initargs=(context.Barrier(4),),
    ) as pool:
        batches = pool.map(process_batch, [(same_key, i) for i in range(4)])
        return [result for batch in batches for result in batch]


def test_fifty_two_retries_across_four_processes(db):
    results = run_parallel(True)
    assert len(results) == 52
    assert {r[0] for r in results} == {201}
    assert len({r[1] for r in results}) == 1
    assert sum(not r[2] for r in results) == 1
    assert balances(db) == [4_850_000, 3_150_000]
    assert_integrity(db)


def test_distinct_keys_across_processes_cannot_overdraw(db):
    results = run_parallel(False)
    assert [r[0] for r in results].count(201) == 5
    assert [r[0] for r in results].count(409) == 7
    assert balances(db) == [0, 8_000_000]
    assert_integrity(db)


def test_process_death_before_commit_rolls_back(client, headers, db):
    process = multiprocessing.get_context("spawn").Process(target=abrupt_exit, args=(False,))
    process.start()
    process.join(timeout=30)
    assert process.exitcode == 86
    assert balances(db) == [5_000_000, 3_000_000]
    assert db.scalar(select(func.count()).select_from(IdempotencyRecord)) == 0
    db.rollback()
    assert send(client, headers, "crash-recovery-key").status_code == 201
    assert_integrity(db)


def test_process_death_after_commit_replays_saved_result(client, headers, db):
    process = multiprocessing.get_context("spawn").Process(target=abrupt_exit, args=(True,))
    process.start()
    process.join(timeout=30)
    assert process.exitcode == 87
    response = send(client, headers, "crash-recovery-key")
    assert response.status_code == 201
    assert response.headers["X-Idempotency-Replayed"] == "true"
    assert db.scalar(select(func.count()).select_from(Transfer)) == 1
    assert balances(db) == [4_850_000, 3_150_000]
    assert_integrity(db)
