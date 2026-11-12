import hashlib
import json
import uuid
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.accounts import audit
from app.config import settings
from app.errors import APIError, envelope
from app.models import (
    Account,
    Beneficiary,
    IdempotencyRecord,
    LedgerEntry,
    OutboxEvent,
    Transfer,
    User,
)
from app.schemas import MAX_AMOUNT, TransferInput, TransferOutput

OPERATION = "POST:/api/v1/transfers"


def posting_accounts(db: Session, user_id: uuid.UUID, payload: TransferInput):
    """Preview and commit share policy; both take the same globally ordered locks."""
    rows = list(
        db.scalars(
            select(Account)
            .where(Account.id.in_([payload.source_account_id, payload.destination_account_id]))
            .order_by(Account.id)
            .with_for_update()
        )
    )
    by_id = {row.id: row for row in rows}
    source, destination = (
        by_id.get(payload.source_account_id),
        by_id.get(payload.destination_account_id),
    )
    if source is None or source.user_id != user_id:
        raise APIError(404, "ACCOUNT_NOT_FOUND", "Source account not found.")
    if destination is None:
        raise APIError(404, "ACCOUNT_NOT_FOUND", "Recipient account not found.")
    if source.id == destination.id:
        raise APIError(422, "SELF_TRANSFER", "Choose a different recipient account.")
    if source.status != "ACTIVE" or destination.status == "CLOSED":
        raise APIError(
            409,
            "ACCOUNT_NOT_ACTIVE",
            "The source must be active and the recipient must not be closed.",
        )
    if source.currency != destination.currency:
        raise APIError(422, "CURRENCY_MISMATCH", "Account currencies must match.")
    if not settings().transfer_min_vnd <= payload.amount_vnd <= settings().transfer_max_vnd:
        raise APIError(
            422, "TRANSFER_LIMIT_INVALID", "Amount is outside the configured per-transfer limits."
        )
    if source.balance_vnd < payload.amount_vnd:
        raise APIError(409, "INSUFFICIENT_FUNDS", "The source account has insufficient funds.")
    if source.daily_outgoing_limit_vnd is not None:
        now = db.scalar(select(func.now())).astimezone(UTC)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        spent = db.scalar(
            select(func.coalesce(func.sum(Transfer.amount_vnd), 0)).where(
                Transfer.source_account_id == source.id,
                Transfer.created_at >= start,
                Transfer.created_at < start + timedelta(days=1),
            )
        )
        if spent + payload.amount_vnd > source.daily_outgoing_limit_vnd:
            raise APIError(
                409, "TRANSFER_LIMIT_EXCEEDED", "The daily transfer limit has been reached."
            )
    if destination.balance_vnd > MAX_AMOUNT - payload.amount_vnd:
        raise APIError(409, "BALANCE_LIMIT", "Recipient balance limit would be exceeded.")
    return source, destination


def request_hash(user_id: uuid.UUID, payload: TransferInput) -> str:
    canonical = {"owner": str(user_id), **payload.model_dump(mode="json")}
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def execute_transfer(
    db: Session,
    user_id: uuid.UUID,
    payload: TransferInput,
    key: str,
    request_id: str,
    *,
    own_transaction: bool = True,
) -> tuple[int, dict, bool]:
    digest = request_hash(user_id, payload)
    with db.begin() if own_transaction else nullcontext():
        actor = db.get(User, user_id)
        if actor is None or not actor.is_active or actor.role != "CUSTOMER":
            raise APIError(403, "FORBIDDEN", "Only active customers can initiate transfers.")
        # ON CONFLICT waits for the other transaction. A fresh READ COMMITTED SELECT sees its result.
        claimed = db.scalar(
            insert(IdempotencyRecord)
            .values(
                id=uuid.uuid4(),
                user_id=user_id,
                operation=OPERATION,
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
                IdempotencyRecord.user_id == user_id,
                IdempotencyRecord.operation == OPERATION,
                IdempotencyRecord.key == key,
            )
            .with_for_update()
        )
        if claimed is None:
            if record.request_hash != digest:
                raise APIError(
                    409, "IDEMPOTENCY_KEY_REUSED", "This key was used with a different request."
                )
            if record.state != "COMPLETED":
                raise APIError(
                    409, "REQUEST_IN_PROGRESS", "Request is processing. Retry with the same key."
                )
            return record.response_status, record.response_body, True

        def reject(status, code, message):
            record.state = "COMPLETED"
            record.response_status = status
            record.response_body = envelope(code, message, request_id)
            return status, record.response_body, False

        try:
            source, destination = posting_accounts(db, user_id, payload)
        except APIError as error:
            return reject(error.status, error.code, error.message)
        transfer = Transfer(
            id=uuid.uuid4(),
            reference=f"TXN-{datetime.now(UTC):%Y}-" + uuid.uuid4().hex.upper(),
            initiated_by_user_id=user_id,
            source_account_id=source.id,
            destination_account_id=destination.id,
            amount_vnd=payload.amount_vnd,
            memo=payload.memo,
            status="SUCCEEDED",
        )
        source.balance_vnd -= payload.amount_vnd
        destination.balance_vnd += payload.amount_vnd
        db.add(transfer)
        db.flush()
        db.add_all(
            [
                LedgerEntry(
                    transfer_id=transfer.id,
                    account_id=source.id,
                    direction="DEBIT",
                    amount_vnd=payload.amount_vnd,
                ),
                LedgerEntry(
                    transfer_id=transfer.id,
                    account_id=destination.id,
                    direction="CREDIT",
                    amount_vnd=payload.amount_vnd,
                ),
            ]
        )
        record.state, record.response_status, record.transfer_id = "COMPLETED", 201, transfer.id
        record.response_body = TransferOutput.model_validate(transfer).model_dump(mode="json")
        body = record.response_body
        audit(db, user_id, "TRANSFER_POSTED", "transfer", transfer.id, request_id)
        for owner_id in {source.user_id, destination.user_id}:
            db.add(
                OutboxEvent(
                    user_id=owner_id,
                    kind="TRANSFER_POSTED",
                    entity_id=transfer.id,
                    request_id=request_id,
                )
            )
        saved = db.scalar(
            select(Beneficiary).where(
                Beneficiary.user_id == user_id,
                Beneficiary.destination_account_id == destination.id,
                Beneficiary.archived_at.is_(None),
            )
        )
        if saved is not None:
            saved.last_used_at = datetime.now(UTC)
    return 201, body, False
