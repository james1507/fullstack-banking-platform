import hashlib
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.errors import APIError, envelope
from app.models import Account, IdempotencyRecord, LedgerEntry, Transfer
from app.schemas import MAX_AMOUNT, TransferInput, TransferOutput

OPERATION = "POST:/api/v1/transfers"


def request_hash(user_id: uuid.UUID, payload: TransferInput) -> str:
    canonical = {"owner": str(user_id), **payload.model_dump(mode="json")}
    return hashlib.sha256(
        json.dumps(canonical, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def execute_transfer(
    db: Session, user_id: uuid.UUID, payload: TransferInput, key: str, request_id: str
) -> tuple[int, dict, bool]:
    digest = request_hash(user_id, payload)
    with db.begin():
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

        # Global UUID order applies to every transfer, including opposite-direction requests.
        accounts = list(
            db.scalars(
                select(Account)
                .where(
                    Account.id.in_(
                        [
                            payload.source_account_id,
                            payload.destination_account_id,
                        ]
                    )
                )
                .order_by(Account.id)
                .with_for_update()
            )
        )
        by_id = {account.id: account for account in accounts}
        source = by_id.get(payload.source_account_id)
        destination = by_id.get(payload.destination_account_id)
        if source is None or source.user_id != user_id:
            return reject(404, "ACCOUNT_NOT_FOUND", "Source account not found.")
        if destination is None:
            return reject(404, "ACCOUNT_NOT_FOUND", "Recipient account not found.")
        if source.id == destination.id:
            return reject(422, "SELF_TRANSFER", "Choose a different recipient account.")
        if source.currency != destination.currency:
            return reject(422, "CURRENCY_MISMATCH", "Account currencies must match.")
        if source.balance_vnd < payload.amount_vnd:
            return reject(409, "INSUFFICIENT_FUNDS", "The source account has insufficient funds.")
        if destination.balance_vnd > MAX_AMOUNT - payload.amount_vnd:
            return reject(409, "BALANCE_LIMIT", "Recipient balance limit would be exceeded.")
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
    return 201, body, False
