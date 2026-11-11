import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.errors import APIError
from app.models import Account, Transfer


def owned_accounts(db: Session, user_id: uuid.UUID):
    return list(
        db.scalars(
            select(Account).where(Account.user_id == user_id).order_by(Account.account_number)
        )
    )


def owned_account(db: Session, user_id: uuid.UUID, account_id: uuid.UUID):
    row = db.scalar(select(Account).where(Account.id == account_id, Account.user_id == user_id))
    if row is None:
        raise APIError(404, "ACCOUNT_NOT_FOUND", "Account not found.")
    return row


def visible_query(user_id: uuid.UUID, account_id=None, direction=None, reference=None):
    ids = select(Account.id).where(Account.user_id == user_id)
    sources = Transfer.source_account_id.in_(ids)
    destinations = Transfer.destination_account_id.in_(ids)
    query = select(Transfer).where(or_(sources, destinations))
    if account_id:
        query = query.where(
            or_(
                Transfer.source_account_id == account_id,
                Transfer.destination_account_id == account_id,
            )
        )
    if direction == "OUTGOING":
        query = query.where(Transfer.source_account_id == account_id if account_id else sources)
    if direction == "INCOMING":
        query = query.where(
            Transfer.destination_account_id == account_id if account_id else destinations
        )
    if reference:
        query = query.where(Transfer.reference.icontains(reference, autoescape=True))
    return query


def history(
    db: Session,
    user_id: uuid.UUID,
    page=1,
    page_size=20,
    account_id=None,
    direction=None,
    reference=None,
):
    if account_id:
        owned_account(db, user_id, account_id)
    query = visible_query(user_id, account_id, direction, reference)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    items = list(
        db.scalars(
            query.order_by(Transfer.created_at.desc(), Transfer.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    return items, total
