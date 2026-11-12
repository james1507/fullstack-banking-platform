"""Timezone-aware schedules. All executions use the existing posting service."""

import calendar
import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.accounts import audit
from app.config import settings
from app.errors import APIError
from app.models import Account, IdempotencyRecord, ScheduleOccurrence, TransferSchedule, User
from app.schemas import ScheduleOutput
from app.transfers import request_hash


def local_instant(local, timezone):
    zone = ZoneInfo(timezone)
    # Ambiguous fall-back clocks use fold=0 (the first occurrence).
    try:
        instant = local.replace(tzinfo=zone, fold=0).astimezone(UTC)
    except (OverflowError, ValueError) as exc:
        raise APIError(
            422, "INVALID_LOCAL_TIME", "Choose a supported local calendar time."
        ) from exc
    if instant.astimezone(zone).replace(tzinfo=None) != local:
        raise APIError(
            422, "INVALID_LOCAL_TIME", "This local time does not exist in that timezone."
        )
    return instant


def next_instant(schedule, after):
    """Coalesce downtime: choose next future slot; never burst-post missed payments."""
    local = schedule.starts_local
    for index in range(1300):
        if schedule.recurrence == "ONCE" and index:
            return None
        if schedule.recurrence == "WEEKLY":
            candidate = local + timedelta(weeks=index)
        elif schedule.recurrence == "MONTHLY":
            month_index = local.year * 12 + local.month - 1 + index
            year, month = divmod(month_index, 12)
            month += 1
            candidate = local.replace(
                year=year, month=month, day=min(local.day, calendar.monthrange(year, month)[1])
            )
        else:
            candidate = local
        try:
            instant = local_instant(candidate, schedule.timezone)
        except APIError:
            continue  # Spring-forward gap: skip this recurring slot.
        if instant > after:
            return instant
    raise APIError(422, "SCHEDULE_RANGE", "Schedule start is too far in the past.")


def add_occurrence(db, schedule, due):
    schedule.next_run_at = due
    if due is None:
        schedule.status = "COMPLETED"
        return
    row_id = uuid.uuid4()
    db.add(
        ScheduleOccurrence(
            id=row_id,
            schedule_id=schedule.id,
            due_at=due,
            available_at=due,
            request_id=f"schedule:{row_id}",
        )
    )


def eligible_accounts(db, user_id, payload):
    rows = list(
        db.scalars(
            select(Account)
            .where(Account.id.in_([payload.source_account_id, payload.destination_account_id]))
            .order_by(Account.id)
            .with_for_update()
        )
    )
    by_id = {row.id: row for row in rows}
    source = by_id.get(payload.source_account_id)
    destination = by_id.get(payload.destination_account_id)
    if source is None or source.user_id != user_id:
        raise APIError(404, "ACCOUNT_NOT_FOUND", "Source account not found.")
    if destination is None:
        raise APIError(404, "ACCOUNT_NOT_FOUND", "Recipient account not found.")
    if source.id == destination.id:
        raise APIError(422, "SELF_TRANSFER", "Choose a different recipient account.")
    if source.status != "ACTIVE" or destination.status == "CLOSED":
        raise APIError(409, "ACCOUNT_NOT_ACTIVE", "Schedule requires eligible accounts.")
    if source.currency != destination.currency:
        raise APIError(422, "CURRENCY_MISMATCH", "Account currencies must match.")
    if not settings().transfer_min_vnd <= payload.amount_vnd <= settings().transfer_max_vnd:
        raise APIError(422, "TRANSFER_LIMIT_INVALID", "Amount is outside per-transfer limits.")


def validate_start(payload, now):
    due = local_instant(payload.starts_local, payload.timezone)
    if not now < due <= now + timedelta(days=366):
        raise APIError(422, "INVALID_SCHEDULE_START", "First run must be within the next 366 days.")
    if payload.recurrence == "ONCE" and payload.max_runs != 1:
        raise APIError(422, "INVALID_RECURRENCE", "One-time schedules must have exactly one run.")
    return due


def create_schedule(db, user, payload, request_id, key, now=None):
    now = now or datetime.now(UTC)
    with db.begin():
        actor = db.get(User, user.id)
        if actor is None or not actor.is_active or actor.role != "CUSTOMER":
            raise APIError(403, "FORBIDDEN", "Only active customers can create schedules.")
        digest = request_hash(user.id, payload)
        operation = "POST:/api/v1/scheduled-transfers"
        claimed = db.scalar(
            insert(IdempotencyRecord)
            .values(
                id=uuid.uuid4(),
                user_id=user.id,
                operation=operation,
                key=key,
                request_hash=digest,
                state="PROCESSING",
            )
            .on_conflict_do_nothing(index_elements=["user_id", "operation", "key"])
            .returning(IdempotencyRecord.id)
        )
        record = db.scalar(
            select(IdempotencyRecord)
            .where(
                IdempotencyRecord.user_id == user.id,
                IdempotencyRecord.operation == operation,
                IdempotencyRecord.key == key,
            )
            .with_for_update()
        )
        if claimed is None:
            if record.request_hash != digest:
                raise APIError(
                    409, "IDEMPOTENCY_KEY_REUSED", "This key was used with a different request."
                )
            return record.response_body
        due = validate_start(payload, now)
        eligible_accounts(db, user.id, payload)
        row = TransferSchedule(id=uuid.uuid4(), user_id=user.id, **payload.model_dump())
        db.add(row)
        db.flush()
        add_occurrence(db, row, due)
        audit(db, user.id, "SCHEDULE_CREATED", "schedule", row.id, request_id)
        body = ScheduleOutput.model_validate(row).model_dump(mode="json")
        record.state, record.response_status, record.response_body = "COMPLETED", 201, body
    return body


def owned_schedule(db, user_id, schedule_id, lock=False):
    query = select(TransferSchedule).where(
        TransferSchedule.id == schedule_id, TransferSchedule.user_id == user_id
    )
    row = db.scalar(query.with_for_update() if lock else query)
    if row is None:
        raise APIError(404, "SCHEDULE_NOT_FOUND", "Schedule not found.")
    return row


def change_schedule(db, user, schedule_id, payload, action, request_id, now=None):
    now = now or datetime.now(UTC)
    with db.begin():
        row = owned_schedule(db, user.id, schedule_id, lock=True)
        if payload.version != row.version:
            raise APIError(409, "STALE_VERSION", "Schedule changed. Refresh before editing.")
        if row.status in ("CANCELLED", "COMPLETED"):
            raise APIError(409, "SCHEDULE_TERMINAL", "This schedule is already terminal.")
        pending = list(
            db.scalars(
                select(ScheduleOccurrence)
                .where(
                    ScheduleOccurrence.schedule_id == row.id,
                    ScheduleOccurrence.state.in_(["SCHEDULED", "CLAIMED", "FAILED_RETRYABLE"]),
                )
                .with_for_update()
            )
        )
        if action == "edit":
            if any(item.state == "CLAIMED" for item in pending):
                raise APIError(409, "SCHEDULE_BUSY", "A run is claimed. Pause and try again later.")
            due = validate_start(payload, now)
            if payload.max_runs <= row.runs_completed:
                raise APIError(
                    422, "INVALID_RECURRENCE", "Maximum runs must exceed completed runs."
                )
            eligible_accounts(db, user.id, payload)
            for item in pending:
                item.state = "CANCELLED"
            db.flush()
            for key, value in payload.model_dump(exclude={"version"}).items():
                setattr(row, key, value)
            add_occurrence(db, row, due)
        elif action == "cancel":
            row.status, row.next_run_at = "CANCELLED", None
            for item in pending:
                item.state, item.lease_until, item.lease_token = "CANCELLED", None, None
        elif action == "pause":
            if row.status != "ACTIVE":
                raise APIError(
                    409, "INVALID_SCHEDULE_STATE", "Only active schedules can be paused."
                )
            row.status = "PAUSED"
            for item in pending:
                if item.state == "CLAIMED":
                    item.state, item.lease_until, item.lease_token = "SCHEDULED", None, None
        else:
            if row.status != "PAUSED":
                raise APIError(409, "INVALID_SCHEDULE_STATE", "Only paused schedules can resume.")
            eligible_accounts(db, user.id, row)
            # Retain the same future slot; cancel overdue claims before creating a new future slot.
            for item in pending:
                if item.due_at <= now or item.state == "CLAIMED":
                    item.state, item.lease_until, item.lease_token = "CANCELLED", None, None
            db.flush()
            future = [item for item in pending if item.state != "CANCELLED"]
            row.status = "ACTIVE"
            if not future:
                add_occurrence(db, row, next_instant(row, now))
        row.version += 1
        audit(
            db,
            user.id,
            f"SCHEDULE_{action.upper()}",
            "schedule",
            row.id,
            request_id,
            version=row.version,
        )
    return row
