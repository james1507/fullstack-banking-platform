"""Additive routes; V1 URLs and saved transfer responses remain stable."""

import uuid
from datetime import UTC, date, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from app import accounts, beneficiaries, reporting
from app.db import get_db
from app.errors import APIError
from app.models import AuditEvent, IdempotencyRecord, User
from app.schemas import (
    MAX_AMOUNT,
    AccountCreate,
    AccountOutput,
    AccountUpdate,
    AuditOutput,
    BeneficiaryCreate,
    BeneficiaryOutput,
    BeneficiaryUpdate,
    ConfirmAction,
    CursorHistoryOutput,
    FreezeInput,
    StatementOutput,
    TransferInput,
    TransferPreview,
)
from app.security import limit_recipient_lookup, require_roles
from app.transfers import OPERATION, posting_accounts

router = APIRouter(prefix="/api/v1")
DB = Annotated[Session, Depends(get_db)]
Customer = Annotated[User, Depends(require_roles("CUSTOMER"))]
Operator = Annotated[User, Depends(require_roles("OPERATIONS"))]
Auditor = Annotated[User, Depends(require_roles("AUDITOR", "OPERATIONS"))]


@router.get("/transfers/search", response_model=CursorHistoryOutput)
def transfer_search(
    user: Customer,
    db: DB,
    page_size: int = Query(20, ge=1, le=50),
    cursor: str | None = Query(None, max_length=2048),
    account_id: uuid.UUID | None = None,
    direction: Literal["INCOMING", "OUTGOING"] | None = None,
    reference: str = Query("", max_length=50),
    date_from: date | None = None,
    date_to: date | None = None,
    min_amount: int | None = Query(None, ge=1, le=MAX_AMOUNT),
    max_amount: int | None = Query(None, ge=1, le=MAX_AMOUNT),
    status: Literal["SUCCEEDED"] | None = None,
):
    items, next_cursor = reporting.search(
        db,
        user,
        page_size,
        cursor,
        account_id,
        direction,
        reference,
        date_from,
        date_to,
        min_amount,
        max_amount,
    )
    return {"items": items, "next_cursor": next_cursor, "page_size": page_size}


@router.get("/accounts/{account_id}/statement/summary", response_model=StatementOutput)
def statement_summary(
    account_id: uuid.UUID,
    user: Customer,
    db: DB,
    request: Request,
    date_from: date,
    date_to: date,
    timezone: str | None = Query(None, max_length=64),
):
    summary, _ = reporting.statement(
        db,
        user,
        account_id,
        date_from,
        date_to,
        timezone or user.timezone,
        request.state.request_id,
    )
    return summary


@router.get(
    "/accounts/{account_id}/statement",
    response_class=Response,
    responses={200: {"content": {"text/csv": {}}}},
)
def statement_csv(
    account_id: uuid.UUID,
    user: Customer,
    db: DB,
    request: Request,
    date_from: date,
    date_to: date,
    timezone: str | None = Query(None, max_length=64),
):
    _, content = reporting.statement(
        db,
        user,
        account_id,
        date_from,
        date_to,
        timezone or user.timezone,
        request.state.request_id,
        export=True,
    )
    return Response(
        content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="moneta-{account_id}-{date_from}-{date_to}.csv"'
        },
    )


@router.get("/beneficiaries", response_model=list[BeneficiaryOutput])
def saved_recipients(
    user: Customer, db: DB, search: str = Query("", max_length=100), include_archived: bool = False
):
    return beneficiaries.listing(db, user.id, search, include_archived)


@router.post(
    "/beneficiaries",
    response_model=BeneficiaryOutput,
    status_code=201,
    dependencies=[Depends(limit_recipient_lookup)],
)
def save_recipient(payload: BeneficiaryCreate, user: Customer, db: DB, request: Request):
    return beneficiaries.create(db, user, payload, request.state.request_id)


@router.patch("/beneficiaries/{beneficiary_id}", response_model=BeneficiaryOutput)
def rename_recipient(
    beneficiary_id: uuid.UUID, payload: BeneficiaryUpdate, user: Customer, db: DB, request: Request
):
    return beneficiaries.change(
        db, user, beneficiary_id, request.state.request_id, nickname=payload.nickname
    )


@router.delete("/beneficiaries/{beneficiary_id}", response_model=BeneficiaryOutput)
def archive_recipient(beneficiary_id: uuid.UUID, user: Customer, db: DB, request: Request):
    return beneficiaries.change(db, user, beneficiary_id, request.state.request_id, archived=True)


@router.post(
    "/beneficiaries/{beneficiary_id}/restore",
    response_model=BeneficiaryOutput,
    dependencies=[Depends(limit_recipient_lookup)],
)
def restore_recipient(beneficiary_id: uuid.UUID, user: Customer, db: DB, request: Request):
    return beneficiaries.change(db, user, beneficiary_id, request.state.request_id, archived=False)


@router.post(
    "/transfers/preview",
    response_model=TransferPreview,
    dependencies=[Depends(limit_recipient_lookup)],
)
def transfer_preview(payload: TransferInput, user: Customer, db: DB):
    with db.begin():
        source, destination = posting_accounts(db, user.id, payload)
        return TransferPreview(
            source_account_id=source.id,
            destination_account_id=destination.id,
            source_name=source.name,
            source_number=source.account_number,
            destination_masked_number="••••" + destination.account_number[-4:],
            amount_vnd=payload.amount_vnd,
            estimated_balance_vnd=source.balance_vnd - payload.amount_vnd,
            checked_at=datetime.now(UTC),
        )


@router.get("/transfers/lookup-by-key")
def lookup_by_key(
    user: Customer,
    db: DB,
    key: str = Query(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_-]+$"),
):
    row = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user.id,
            IdempotencyRecord.operation == OPERATION,
            IdempotencyRecord.key == key,
            IdempotencyRecord.state == "COMPLETED",
        )
    )
    if row is None:
        raise APIError(
            404,
            "TRANSFER_OUTCOME_NOT_FOUND",
            "No completed outcome is visible yet. Retry the original request safely.",
        )
    return {"status_code": row.response_status, "response": row.response_body}


@router.post("/accounts", response_model=AccountOutput, status_code=201)
def open_account(payload: AccountCreate, user: Customer, db: DB, request: Request):
    return accounts.open_account(db, user, payload, request.state.request_id)


@router.patch("/accounts/{account_id}", response_model=AccountOutput)
def update_account(
    account_id: uuid.UUID, payload: AccountUpdate, user: Customer, db: DB, request: Request
):
    return accounts.update_account(db, user, account_id, payload, request.state.request_id)


@router.post("/accounts/{account_id}/close", response_model=AccountOutput)
def close_account(
    account_id: uuid.UUID, payload: ConfirmAction, user: Customer, db: DB, request: Request
):
    return accounts.close_account(db, user, account_id, request.state.request_id)


@router.post("/ops/accounts/{account_id}/freeze", response_model=AccountOutput)
def freeze(account_id: uuid.UUID, payload: FreezeInput, user: Operator, db: DB, request: Request):
    return accounts.freeze_account(
        db, user, account_id, True, payload.reason, request.state.request_id
    )


@router.post("/ops/accounts/{account_id}/unfreeze", response_model=AccountOutput)
def unfreeze(account_id: uuid.UUID, payload: FreezeInput, user: Operator, db: DB, request: Request):
    return accounts.freeze_account(
        db, user, account_id, False, payload.reason, request.state.request_id
    )


@router.get("/audit/events", response_model=list[AuditOutput])
def audit_events(
    user: Auditor, db: DB, limit: int = Query(50, ge=1, le=100), before: uuid.UUID | None = None
):
    query = select(AuditEvent)
    if before is not None:
        anchor = db.get(AuditEvent, before)
        if anchor is None:
            raise APIError(400, "INVALID_CURSOR", "Audit cursor does not identify an event.")
        query = query.where(
            tuple_(AuditEvent.created_at, AuditEvent.id) < tuple_(anchor.created_at, anchor.id)
        )
    return list(
        db.scalars(query.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(limit))
    )
