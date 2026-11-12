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
    role: Mapped[str] = mapped_column(String(20), default="CUSTOMER", server_default="CUSTOMER")
    timezone: Mapped[str] = mapped_column(
        String(64), default="Asia/Ho_Chi_Minh", server_default="Asia/Ho_Chi_Minh"
    )
    locale: Mapped[str] = mapped_column(String(10), default="en", server_default="en")


class Account(Identity, Updated, Base):
    __tablename__ = "accounts"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    account_number: Mapped[str] = mapped_column(String(30), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    currency: Mapped[str] = mapped_column(String(3), default="VND")
    balance_vnd: Mapped[int] = mapped_column(BigInteger)
    opening_balance_vnd: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    account_type: Mapped[str] = mapped_column(
        String(10), default="CHECKING", server_default="CHECKING"
    )
    status: Mapped[str] = mapped_column(String(10), default="ACTIVE", server_default="ACTIVE")
    daily_outgoing_limit_vnd: Mapped[int | None] = mapped_column(BigInteger)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


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


class AuditEvent(Identity, Base):
    __tablename__ = "audit_events"
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(50))
    target_type: Mapped[str] = mapped_column(String(30))
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    outcome: Mapped[str] = mapped_column(String(20), default="SUCCEEDED")
    request_id: Mapped[str] = mapped_column(String(100))
    safe_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class Beneficiary(Identity, Updated, Base):
    __tablename__ = "beneficiaries"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    destination_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    nickname: Mapped[str] = mapped_column(String(100))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TransferSchedule(Identity, Updated, Base):
    __tablename__ = "transfer_schedules"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    source_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    destination_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("accounts.id"))
    amount_vnd: Mapped[int] = mapped_column(BigInteger)
    memo: Mapped[str | None] = mapped_column(String(200))
    timezone: Mapped[str] = mapped_column(String(64))
    starts_local: Mapped[datetime] = mapped_column(DateTime(timezone=False))
    recurrence: Mapped[str] = mapped_column(String(10))
    max_runs: Mapped[int]
    runs_completed: Mapped[int] = mapped_column(default=0)
    version: Mapped[int] = mapped_column(default=1)
    status: Mapped[str] = mapped_column(String(10), default="ACTIVE")
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ScheduleOccurrence(Identity, Base):
    __tablename__ = "schedule_occurrences"
    schedule_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transfer_schedules.id"))
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    state: Mapped[str] = mapped_column(String(20), default="SCHEDULED")
    attempt_count: Mapped[int] = mapped_column(default=0)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    transfer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("transfers.id"))
    last_error_code: Mapped[str | None] = mapped_column(String(50))
    request_id: Mapped[str] = mapped_column(String(100))


class OutboxEvent(Identity, Base):
    __tablename__ = "outbox_events"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    kind: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    request_id: Mapped[str] = mapped_column(String(100))
    state: Mapped[str] = mapped_column(String(20), default="PENDING")
    attempt_count: Mapped[int] = mapped_column(default=0)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    last_error_code: Mapped[str | None] = mapped_column(String(50))


class Notification(Identity, Base):
    __tablename__ = "notifications"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    event_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("outbox_events.id"), unique=True)
    kind: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    title: Mapped[str] = mapped_column(String(100))
    body: Mapped[str] = mapped_column(String(300))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
