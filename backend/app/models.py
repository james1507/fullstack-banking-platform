import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class Identity:
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Updated:
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class User(Identity, Updated, Base):
    __tablename__ = "users"
    email: Mapped[str] = mapped_column(String(254), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)


class Account(Identity, Updated, Base):
    __tablename__ = "accounts"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    account_number: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    currency: Mapped[str] = mapped_column(String(3), default="VND")
    balance_vnd: Mapped[int] = mapped_column(BigInteger)


class Transfer(Identity, Base):
    __tablename__ = "transfers"
    reference: Mapped[str] = mapped_column(String(50), unique=True)
    initiated_by_user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    source_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    destination_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"), index=True)
    amount_vnd: Mapped[int] = mapped_column(BigInteger)
    memo: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="SUCCEEDED")


class LedgerEntry(Identity, Base):
    __tablename__ = "ledger_entries"
    transfer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transfers.id"), index=True)
    account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    direction: Mapped[str] = mapped_column(String(6))
    amount_vnd: Mapped[int] = mapped_column(BigInteger)


class IdempotencyRecord(Identity, Updated, Base):
    __tablename__ = "idempotency_records"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    operation: Mapped[str] = mapped_column(String(100))
    key: Mapped[str] = mapped_column(String(100))
    request_hash: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(20))
    response_status: Mapped[int | None]
    response_body: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    transfer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transfers.id"))


class RefreshSession(Identity, Base):
    __tablename__ = "refresh_sessions"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
