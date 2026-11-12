from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from email_validator import validate_email
from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_AMOUNT = 9_007_199_254_740_991


class LoginInput(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        if not isinstance(value, str):
            raise ValueError("Enter a valid email address.")
        return validate_email(
            value.strip().lower(), check_deliverability=False, test_environment=True
        ).normalized


class TransferInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_account_id: UUID
    destination_account_id: UUID
    amount_vnd: Annotated[int, Field(strict=True, gt=0, le=MAX_AMOUNT)]
    memo: str | None = Field(default=None, max_length=200)

    @field_validator("memo")
    @classmethod
    def normalize_memo(cls, value):
        return value.strip() or None if value is not None else None


class AccountOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    account_number: str
    name: str
    currency: str
    balance_vnd: int
    account_type: Literal["CHECKING", "SAVINGS"]
    status: Literal["ACTIVE", "FROZEN", "CLOSED"]
    daily_outgoing_limit_vnd: int | None
    closed_at: datetime | None


class UserOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    display_name: str
    role: Literal["CUSTOMER", "OPERATIONS", "AUDITOR"]
    timezone: str
    locale: str


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    account_type: Literal["CHECKING", "SAVINGS"]


class AccountUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    daily_outgoing_limit_vnd: Annotated[int | None, Field(strict=True, gt=0, le=MAX_AMOUNT)] = None


class ConfirmAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmed: Literal[True]


class FreezeInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: Literal["CUSTOMER_REQUEST", "RISK_REVIEW", "TEST_INCIDENT"]


class AuditOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    actor_user_id: UUID | None
    action: str
    target_type: str
    target_id: UUID
    outcome: str
    request_id: str
    safe_metadata: dict
    created_at: datetime


class BeneficiaryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    destination_account_id: UUID
    nickname: str = Field(min_length=1, max_length=100)


class BeneficiaryUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    nickname: str = Field(min_length=1, max_length=100)


class BeneficiaryOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    destination_account_id: UUID
    nickname: str
    archived_at: datetime | None
    last_used_at: datetime | None
    created_at: datetime
    updated_at: datetime


class TransferPreview(BaseModel):
    source_account_id: UUID
    destination_account_id: UUID
    source_name: str
    source_number: str
    destination_masked_number: str
    amount_vnd: int
    fee_vnd: int = 0
    estimated_balance_vnd: int
    currency: str = "VND"
    checked_at: datetime


class CursorHistoryOutput(BaseModel):
    items: list[TransferOutput]
    next_cursor: str | None
    page_size: int


class StatementOutput(BaseModel):
    account_id: UUID
    account_number: str
    date_from: date
    date_to: date
    timezone: str
    effective_from: datetime | None
    money_encoding: Literal["decimal-string-vnd"] = "decimal-string-vnd"
    opening_balance_vnd: str
    closing_balance_vnd: str
    total_debit_vnd: str
    total_credit_vnd: str
    row_count: int


class TokenOutput(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TransferOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    reference: str
    status: str
    amount_vnd: int
    currency: str = "VND"
    source_account_id: UUID
    destination_account_id: UUID
    memo: str | None
    created_at: datetime


class ScheduleInput(TransferInput):
    timezone: str = Field(min_length=1, max_length=64)
    starts_local: datetime
    recurrence: Literal["ONCE", "WEEKLY", "MONTHLY"] = "ONCE"
    max_runs: Annotated[int, Field(strict=True, ge=1, le=120)] = 1

    @field_validator("starts_local")
    @classmethod
    def local_clock(cls, value):
        if value.tzinfo is not None:
            raise ValueError(
                "Use local wall time without a UTC offset; supply timezone separately."
            )
        return value

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, value):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Choose a valid IANA timezone.") from exc
        return value


class ScheduleEdit(ScheduleInput):
    version: Annotated[int, Field(strict=True, ge=1)]


class ScheduleAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Annotated[int, Field(strict=True, ge=1)]
    confirmed: Literal[True]


class ScheduleOutput(ScheduleInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    status: Literal["ACTIVE", "PAUSED", "CANCELLED", "COMPLETED"]
    next_run_at: datetime | None
    runs_completed: int
    version: int
    created_at: datetime


class OccurrenceOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    due_at: datetime
    state: str
    attempt_count: int
    transfer_id: UUID | None
    last_error_code: str | None
    request_id: str


class ScheduleDetail(BaseModel):
    schedule: ScheduleOutput
    occurrences: list[OccurrenceOutput]


class NotificationOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    kind: str
    entity_id: UUID
    title: str
    body: str
    read_at: datetime | None
    created_at: datetime


class InboxOutput(BaseModel):
    items: list[NotificationOutput]
    next_cursor: str | None
    unread_count: int
