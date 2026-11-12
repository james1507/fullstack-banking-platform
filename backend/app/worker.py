"""One lightweight DB worker; run more instances without changing money semantics."""

import json
import logging
import random
import signal
import threading
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import DBAPIError

from app.accounts import audit
from app.db import SessionLocal
from app.errors import APIError
from app.models import Notification, OutboxEvent, ScheduleOccurrence, TransferSchedule
from app.scheduling import add_occurrence, next_instant
from app.schemas import TransferInput
from app.transfers import execute_transfer

logger = logging.getLogger("banking.worker")
LEASE_SECONDS = 60
MAX_ATTEMPTS = 5


def claim(model, now):
    ready_states = (
        ["SCHEDULED", "FAILED_RETRYABLE"]
        if model is ScheduleOccurrence
        else ["PENDING", "RETRYABLE"]
    )
    with SessionLocal.begin() as db:
        query = select(model).where(
            or_(
                and_(model.state.in_(ready_states), model.available_at <= now),
                and_(model.state == "CLAIMED", model.lease_until <= now),
            )
        )
        if model is ScheduleOccurrence:
            query = query.join(TransferSchedule).where(TransferSchedule.status == "ACTIVE")
        row = db.scalar(
            query.order_by(model.available_at, model.id)
            .limit(1)
            .with_for_update(skip_locked=True, of=model)
        )
        if row is None:
            return None
        if row.attempt_count >= MAX_ATTEMPTS:
            row.last_error_code = "RETRY_EXHAUSTED"
        else:
            row.attempt_count += 1
        row.state, row.lease_token = "CLAIMED", uuid.uuid4()
        row.lease_until = now + timedelta(seconds=LEASE_SECONDS)
        return row.id, row.lease_token


def clear_lease(row):
    row.lease_until = row.lease_token = None


def execute_occurrence(row_id, token, now):
    with SessionLocal.begin() as db:
        schedule_id = db.scalar(
            select(ScheduleOccurrence.schedule_id).where(ScheduleOccurrence.id == row_id)
        )
        if schedule_id is None:
            return
        # Lifecycle actions take the same schedule lock before the occurrence lock.
        schedule = db.scalar(
            select(TransferSchedule).where(TransferSchedule.id == schedule_id).with_for_update()
        )
        row = db.scalar(
            select(ScheduleOccurrence).where(ScheduleOccurrence.id == row_id).with_for_update()
        )
        if row.state != "CLAIMED" or row.lease_token != token:
            return  # Fenced stale worker; a newer lease owns execution.
        if schedule.status != "ACTIVE":
            row.state = "SCHEDULED" if schedule.status == "PAUSED" else "CANCELLED"
            clear_lease(row)
            return
        if row.last_error_code == "RETRY_EXHAUSTED":
            status, body = 503, {"error": {"code": "RETRY_EXHAUSTED"}}
        else:
            payload = TransferInput.model_validate(
                {
                    name: getattr(schedule, name)
                    for name in (
                        "source_account_id",
                        "destination_account_id",
                        "amount_vnd",
                        "memo",
                    )
                }
            )
            try:
                status, body, _ = execute_transfer(
                    db,
                    schedule.user_id,
                    payload,
                    f"schedule:{row.id}",
                    row.request_id,
                    own_transaction=False,
                )
            except APIError as error:
                status, body = error.status, {"error": {"code": error.code}}
        if status == 201:
            row.state, row.transfer_id, row.last_error_code = (
                "SUCCEEDED",
                uuid.UUID(body["id"]),
                None,
            )
        else:
            row.state, row.last_error_code = "FAILED_PERMANENT", body["error"]["code"]
        clear_lease(row)
        schedule.runs_completed += 1
        schedule.version += 1
        due = None if schedule.runs_completed >= schedule.max_runs else next_instant(schedule, now)
        add_occurrence(db, schedule, due)
        audit(
            db,
            schedule.user_id,
            "SCHEDULE_EXECUTED",
            "schedule",
            schedule.id,
            row.request_id,
            occurrence_id=str(row.id),
            state=row.state,
            error_code=row.last_error_code,
        )
        db.add(
            OutboxEvent(
                user_id=schedule.user_id,
                kind="SCHEDULE_OUTCOME",
                entity_id=row.id,
                request_id=row.request_id,
            )
        )
        # Money, saved idempotency, occurrence ack and event commit together.


def deliver_event(row_id, token, now):
    with SessionLocal.begin() as db:
        row = db.scalar(select(OutboxEvent).where(OutboxEvent.id == row_id).with_for_update())
        if row is None or row.state != "CLAIMED" or row.lease_token != token:
            return
        if row.last_error_code == "RETRY_EXHAUSTED":
            row.state = "DEAD_LETTER"
        else:
            title, body = (
                "Transfer posted",
                "An internal demo transfer was committed. View its receipt for details.",
            )
            if row.kind == "SCHEDULE_OUTCOME":
                occurrence = db.get(ScheduleOccurrence, row.entity_id)
                title = (
                    "Scheduled transfer succeeded"
                    if occurrence.state == "SUCCEEDED"
                    else "Scheduled transfer failed"
                )
                body = (
                    "View schedule execution history for the committed outcome or rejection reason."
                )
            db.execute(
                insert(Notification)
                .values(
                    id=uuid.uuid4(),
                    user_id=row.user_id,
                    event_id=row.id,
                    kind=row.kind,
                    entity_id=row.entity_id,
                    title=title,
                    body=body,
                )
                .on_conflict_do_nothing(index_elements=["event_id"])
            )
            row.state, row.last_error_code = "DELIVERED", None
        clear_lease(row)


def fail_claim(model, row_id, token, now):
    # No exception text: SQL/parameters may contain sensitive application data.
    with SessionLocal.begin() as db:
        row = db.scalar(select(model).where(model.id == row_id).with_for_update())
        if row is None or row.state != "CLAIMED" or row.lease_token != token:
            return
        clear_lease(row)
        row.last_error_code = "TEMPORARY_DATABASE_ERROR"
        row.state = "FAILED_RETRYABLE" if model is ScheduleOccurrence else "RETRYABLE"
        row.available_at = now + timedelta(
            seconds=min(300, 2**row.attempt_count) + random.uniform(0, 1)
        )
        if row.attempt_count >= MAX_ATTEMPTS:
            # A final fenced claim records terminal schedule outcome or outbox dead letter.
            row.last_error_code = "RETRY_EXHAUSTED"
    logger.warning(json.dumps({"job_id": str(row_id), "state": "RETRYABLE"}))


def tick(now=None):
    now = now or datetime.now(UTC)
    worked = False
    for model, handler in ((ScheduleOccurrence, execute_occurrence), (OutboxEvent, deliver_event)):
        lease = claim(model, now)
        if lease is None:
            continue
        worked = True
        try:
            handler(*lease, now)
            logger.info(
                json.dumps({"job_id": str(lease[0]), "stage": model.__tablename__, "handled": True})
            )
        except DBAPIError:
            fail_claim(model, *lease, now)
    return worked


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    stopped = threading.Event()
    for name in (signal.SIGTERM, signal.SIGINT):
        signal.signal(name, lambda *_: stopped.set())
    while not stopped.is_set():
        try:
            worked = tick()
        except DBAPIError:
            logger.error(json.dumps({"error_code": "WORKER_DATABASE_UNAVAILABLE"}))
            worked = False
        stopped.wait(0.1 if worked else 1)


if __name__ == "__main__":
    main()
