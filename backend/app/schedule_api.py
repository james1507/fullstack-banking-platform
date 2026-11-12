"""Owner-scoped scheduling routes; posting remains in the transfer service."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import scheduling
from app.db import get_db
from app.models import ScheduleOccurrence, TransferSchedule, User
from app.schemas import ScheduleAction, ScheduleDetail, ScheduleEdit, ScheduleInput, ScheduleOutput
from app.security import require_roles

router = APIRouter(prefix="/api/v1/scheduled-transfers", tags=["schedules"])
DB = Annotated[Session, Depends(get_db)]
Customer = Annotated[User, Depends(require_roles("CUSTOMER"))]


@router.get("", response_model=list[ScheduleOutput])
def list_schedules(user: Customer, db: DB):
    return list(
        db.scalars(
            select(TransferSchedule)
            .where(TransferSchedule.user_id == user.id)
            .order_by(TransferSchedule.created_at.desc(), TransferSchedule.id)
            .limit(200)
        )
    )


@router.post("", status_code=201, response_model=ScheduleOutput)
def create_schedule(
    payload: ScheduleInput,
    user: Customer,
    db: DB,
    request: Request,
    key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_-]+$"),
    ],
):
    return scheduling.create_schedule(db, user, payload, request.state.request_id, key)


@router.get("/{schedule_id}", response_model=ScheduleDetail)
def schedule_detail(schedule_id: uuid.UUID, user: Customer, db: DB):
    row = scheduling.owned_schedule(db, user.id, schedule_id)
    occurrences = list(
        db.scalars(
            select(ScheduleOccurrence)
            .where(ScheduleOccurrence.schedule_id == row.id)
            .order_by(ScheduleOccurrence.due_at.desc(), ScheduleOccurrence.id)
            .limit(50)
        )
    )
    return {"schedule": row, "occurrences": occurrences}


@router.patch("/{schedule_id}", response_model=ScheduleOutput)
def edit_schedule(
    schedule_id: uuid.UUID, payload: ScheduleEdit, user: Customer, db: DB, request: Request
):
    return scheduling.change_schedule(
        db, user, schedule_id, payload, "edit", request.state.request_id
    )


@router.post("/{schedule_id}/{action}", response_model=ScheduleOutput)
def schedule_action(
    schedule_id: uuid.UUID,
    action: Literal["pause", "resume", "cancel"],
    payload: ScheduleAction,
    user: Customer,
    db: DB,
    request: Request,
):
    return scheduling.change_schedule(
        db, user, schedule_id, payload, action, request.state.request_id
    )
