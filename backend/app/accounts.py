"""Account lifecycle uses the posting row locks; no balance-edit operation exists."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select

from app.errors import APIError
from app.models import Account, AuditEvent, TransferSchedule


def audit(db, actor_id, action, target_type, target_id, request_id, **metadata):
    db.add(
        AuditEvent(
            actor_user_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            request_id=request_id,
            safe_metadata=metadata,
        )
    )


def locked_account(db, account_id, owner_id=None):
    query = select(Account).where(Account.id == account_id)
    if owner_id is not None:
        query = query.where(Account.user_id == owner_id)
    row = db.scalar(query.with_for_update())
    if row is None:
        raise APIError(404, "ACCOUNT_NOT_FOUND", "Account not found.")
    return row


def open_account(db, user, payload, request_id):
    with db.begin():
        row = Account(
            id=uuid.uuid4(),
            user_id=user.id,
            account_number="DEMO-" + uuid.uuid4().hex[:20].upper(),
            name=payload.name,
            account_type=payload.account_type,
            balance_vnd=0,
        )
        db.add(row)
        db.flush()
        audit(db, user.id, "ACCOUNT_OPENED", "account", row.id, request_id)
    return row


def update_account(db, user, account_id, payload, request_id):
    with db.begin():
        row = locked_account(db, account_id, user.id)
        if row.status == "CLOSED":
            raise APIError(409, "ACCOUNT_NOT_ACTIVE", "Closed accounts cannot be changed.")
        if "name" in payload.model_fields_set:
            if payload.name is None:
                raise APIError(422, "INVALID_NAME", "Enter an account name.")
            row.name = payload.name
        if "daily_outgoing_limit_vnd" in payload.model_fields_set:
            row.daily_outgoing_limit_vnd = payload.daily_outgoing_limit_vnd
        audit(
            db,
            user.id,
            "ACCOUNT_UPDATED",
            "account",
            row.id,
            request_id,
            fields=sorted(payload.model_fields_set),
        )
    return row


def close_account(db, user, account_id, request_id):
    with db.begin():
        row = locked_account(db, account_id, user.id)
        if row.status == "CLOSED":
            return row
        if row.balance_vnd != 0:
            raise APIError(
                409, "ACCOUNT_NOT_EMPTY", "Move the remaining balance before closing this account."
            )
        pending = db.scalar(
            select(TransferSchedule.id)
            .where(
                TransferSchedule.user_id == user.id,
                (TransferSchedule.source_account_id == row.id)
                | (TransferSchedule.destination_account_id == row.id),
                TransferSchedule.status.in_(["ACTIVE", "PAUSED"]),
            )
            .limit(1)
        )
        if pending is not None:
            raise APIError(409, "ACCOUNT_HAS_SCHEDULES", "Cancel active or paused schedules first.")
        row.status, row.closed_at = "CLOSED", datetime.now(UTC)
        audit(db, user.id, "ACCOUNT_CLOSED", "account", row.id, request_id)
    return row


def freeze_account(db, user, account_id, frozen, reason, request_id):
    with db.begin():
        row = locked_account(db, account_id)
        if row.status == "CLOSED":
            raise APIError(409, "ACCOUNT_NOT_ACTIVE", "Closed accounts cannot be reopened.")
        target = "FROZEN" if frozen else "ACTIVE"
        if row.status != target:
            row.status = target
            audit(
                db,
                user.id,
                "ACCOUNT_FROZEN" if frozen else "ACCOUNT_UNFROZEN",
                "account",
                row.id,
                request_id,
                reason=reason,
            )
    return row
