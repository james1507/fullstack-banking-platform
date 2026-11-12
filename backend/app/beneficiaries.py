from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.accounts import audit
from app.errors import APIError
from app.models import Account, Beneficiary


def recipient(db, destination_id):
    row = db.get(Account, destination_id)
    if row is None or row.status == "CLOSED":
        raise APIError(404, "RECIPIENT_UNAVAILABLE", "This fictional recipient is unavailable.")
    return row


def owned(db, owner_id, beneficiary_id):
    row = db.scalar(
        select(Beneficiary)
        .where(Beneficiary.id == beneficiary_id, Beneficiary.user_id == owner_id)
        .with_for_update()
    )
    if row is None:
        raise APIError(404, "BENEFICIARY_NOT_FOUND", "Saved recipient not found.")
    return row


def listing(db, user_id, search, include_archived):
    query = select(Beneficiary).where(Beneficiary.user_id == user_id)
    if not include_archived:
        query = query.where(Beneficiary.archived_at.is_(None))
    if search:
        query = query.where(Beneficiary.nickname.icontains(search, autoescape=True))
    return list(
        db.scalars(query.order_by(func.lower(Beneficiary.nickname), Beneficiary.id).limit(100))
    )


def create(db, user, payload, request_id):
    try:
        with db.begin():
            recipient(db, payload.destination_account_id)
            row = Beneficiary(user_id=user.id, **payload.model_dump())
            db.add(row)
            db.flush()
            audit(db, user.id, "BENEFICIARY_CREATED", "beneficiary", row.id, request_id)
        return row
    except IntegrityError as exc:
        raise APIError(
            409, "BENEFICIARY_EXISTS", "An active saved recipient already uses this account."
        ) from exc


def change(db, user, beneficiary_id, request_id, nickname=None, archived=None):
    try:
        with db.begin():
            row = owned(db, user.id, beneficiary_id)
            if archived is False:
                recipient(db, row.destination_account_id)
            if nickname is not None:
                row.nickname = nickname
            if archived is not None:
                row.archived_at = datetime.now(UTC) if archived else None
            audit(db, user.id, "BENEFICIARY_UPDATED", "beneficiary", row.id, request_id)
        return row
    except IntegrityError as exc:
        raise APIError(
            409, "BENEFICIARY_EXISTS", "An active saved recipient already uses this account."
        ) from exc
