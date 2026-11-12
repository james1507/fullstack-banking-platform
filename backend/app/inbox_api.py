"""Owner-scoped in-app inbox; delivery happens exclusively through the outbox."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, tuple_, update
from sqlalchemy.orm import Session

from app.db import get_db
from app.errors import APIError
from app.models import Notification, User
from app.schemas import InboxOutput, NotificationOutput
from app.security import require_roles

router = APIRouter(prefix="/api/v1/notifications", tags=["inbox"])
DB = Annotated[Session, Depends(get_db)]
Customer = Annotated[User, Depends(require_roles("CUSTOMER"))]


def owned_notification(db, owner, notification_id):
    row = db.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == owner
        )
    )
    if row is None:
        raise APIError(404, "NOTIFICATION_NOT_FOUND", "Notification not found.")
    return row


@router.get("", response_model=InboxOutput)
def inbox(
    user: Customer,
    db: DB,
    cursor: str = Query("", max_length=36),
    page_size: int = Query(20, ge=1, le=50),
):
    query = select(Notification).where(Notification.user_id == user.id)
    if cursor:
        try:
            cursor_id = uuid.UUID(cursor)
        except ValueError as exc:
            raise APIError(400, "INVALID_CURSOR", "Invalid notification cursor.") from exc
        anchor = owned_notification(db, user.id, cursor_id)
        query = query.where(
            tuple_(Notification.created_at, Notification.id) < (anchor.created_at, anchor.id)
        )
    rows = list(
        db.scalars(
            query.order_by(Notification.created_at.desc(), Notification.id.desc()).limit(
                page_size + 1
            )
        )
    )
    unread = db.scalar(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
    )
    return {
        "items": rows[:page_size],
        "next_cursor": str(rows[page_size - 1].id) if len(rows) > page_size else None,
        "unread_count": unread,
    }


@router.post("/read-all")
def read_all(user: Customer, db: DB):
    result = db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    db.commit()
    return {"updated": result.rowcount}


@router.post("/{notification_id}/read", response_model=NotificationOutput)
def read_one(notification_id: uuid.UUID, user: Customer, db: DB):
    row = owned_notification(db, user.id, notification_id)
    db.execute(
        update(Notification)
        .where(Notification.id == row.id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
    db.commit()
    db.refresh(row)
    return row
