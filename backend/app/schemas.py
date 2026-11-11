from datetime import datetime
from typing import Annotated
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


class UserOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    display_name: str


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
