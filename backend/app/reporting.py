"""Bounded, repeatable-read statements; cursor history preserves V1's page API."""

import base64
import csv
import hashlib
import hmac
import io
import json
import uuid
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import case, func, select, text, tuple_

from app.accounts import audit
from app.config import settings
from app.errors import APIError
from app.models import LedgerEntry, Transfer
from app.repositories import owned_account, visible_query
from app.schemas import StatementOutput

MAX_EXPORT_ROWS = 5000


def timezone_for(name):
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise APIError(422, "INVALID_TIMEZONE", "Use a valid IANA timezone.") from exc


def period(date_from, date_to, timezone):
    if date_to < date_from or (date_to - date_from).days >= 366:
        raise APIError(422, "INVALID_PERIOD", "Choose an inclusive date range of at most 366 days.")
    zone = timezone_for(timezone)
    try:
        start = datetime.combine(date_from, time.min, zone).astimezone(UTC)
        end = datetime.combine(date_to + timedelta(days=1), time.min, zone).astimezone(UTC)
    except (OverflowError, ValueError) as exc:
        raise APIError(
            422, "INVALID_PERIOD", "Choose dates within the supported calendar."
        ) from exc
    return start, end, zone


def csv_cell(value):
    value = str(value)
    if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
        return "'" + value
    return value


def statement(
    db, user, account_id, date_from: date, date_to: date, timezone, request_id, export=False
):
    start, end, zone = period(date_from, date_to, timezone)
    with db.begin():
        # Account baseline and every ledger aggregate must see the same database snapshot.
        db.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
        account = owned_account(db, user.id, account_id)
        effective = max(start, account.created_at)
        signed = case(
            (LedgerEntry.direction == "CREDIT", LedgerEntry.amount_vnd),
            else_=-LedgerEntry.amount_vnd,
        )
        scope = LedgerEntry.account_id == account.id
        before = int(
            db.scalar(
                select(func.coalesce(func.sum(signed), 0)).where(
                    scope, LedgerEntry.created_at < effective
                )
            )
        )
        opening = account.opening_balance_vnd + before if end > account.created_at else 0
        rows_query = (
            select(LedgerEntry, Transfer)
            .join(Transfer, Transfer.id == LedgerEntry.transfer_id)
            .where(scope, Transfer.created_at >= effective, Transfer.created_at < end)
        )
        count, debit, credit = db.execute(
            select(
                func.count(LedgerEntry.id),
                func.coalesce(
                    func.sum(
                        case((LedgerEntry.direction == "DEBIT", LedgerEntry.amount_vnd), else_=0)
                    ),
                    0,
                ),
                func.coalesce(
                    func.sum(
                        case((LedgerEntry.direction == "CREDIT", LedgerEntry.amount_vnd), else_=0)
                    ),
                    0,
                ),
            ).where(scope, LedgerEntry.created_at >= effective, LedgerEntry.created_at < end)
        ).one()
        count, debit, credit = int(count), int(debit), int(credit)
        if count > MAX_EXPORT_ROWS:
            raise APIError(
                422,
                "EXPORT_LIMIT_EXCEEDED",
                "Choose a smaller period; statements are limited to 5,000 rows.",
            )
        summary = StatementOutput(
            account_id=account.id,
            account_number=account.account_number,
            date_from=date_from,
            date_to=date_to,
            timezone=timezone,
            effective_from=effective if effective < end else None,
            opening_balance_vnd=str(opening),
            closing_balance_vnd=str(opening + credit - debit),
            total_debit_vnd=str(debit),
            total_credit_vnd=str(credit),
            row_count=count,
        )
        content = None
        if export:
            buffer = io.StringIO(newline="")
            writer = csv.writer(buffer)
            writer.writerow(
                [
                    "record_type",
                    "reference",
                    "timestamp_utc",
                    "timestamp_local",
                    "description",
                    "debit_vnd",
                    "credit_vnd",
                    "balance_vnd",
                ]
            )
            writer.writerow(
                ["ACCOUNT", account.account_number, "", "", csv_cell(account.name), "", "", ""]
            )
            writer.writerow(
                [
                    "PERIOD",
                    "",
                    "",
                    "",
                    f"{date_from} to {date_to} inclusive; {timezone}",
                    "",
                    "",
                    "",
                ]
            )
            writer.writerow(
                [
                    "OPENING",
                    "",
                    "",
                    "",
                    "Synthetic opening baseline plus prior postings",
                    0,
                    0,
                    str(opening),
                ]
            )
            balance = opening
            for entry, transfer in db.execute(
                rows_query.order_by(Transfer.created_at, Transfer.id).limit(MAX_EXPORT_ROWS)
            ):
                is_credit = entry.direction == "CREDIT"
                balance += entry.amount_vnd if is_credit else -entry.amount_vnd
                writer.writerow(
                    [
                        "TRANSFER",
                        transfer.reference,
                        transfer.created_at.isoformat(),
                        transfer.created_at.astimezone(zone).isoformat(),
                        csv_cell(transfer.memo or "Internal demo transfer"),
                        0 if is_credit else entry.amount_vnd,
                        entry.amount_vnd if is_credit else 0,
                        balance,
                    ]
                )
            writer.writerow(["CLOSING", "", "", "", "Closing balance", debit, credit, str(balance)])
            content = "\ufeff" + buffer.getvalue()
            audit(
                db,
                user.id,
                "STATEMENT_EXPORTED",
                "account",
                account.id,
                request_id,
                date_from=str(date_from),
                date_to=str(date_to),
                row_count=count,
            )
    return summary, content


def cursor_token(data):
    body = (
        base64.urlsafe_b64encode(json.dumps(data, sort_keys=True, separators=(",", ":")).encode())
        .decode()
        .rstrip("=")
    )
    signature = hmac.new(settings().jwt_secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return body + "." + signature


def decode_cursor(token, fingerprint):
    try:
        body, signature = token.split(".")
        expected = hmac.new(
            settings().jwt_secret.encode(), body.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Invalid signature")
        data = json.loads(
            base64.b64decode(body + "=" * (-len(body) % 4), altchars=b"-_", validate=True)
        )
        if data["scope"] != fingerprint:
            raise ValueError("Cursor filter mismatch")
        timestamp = datetime.fromisoformat(data["at"])
        if timestamp.tzinfo is None:
            raise ValueError("Timezone required")
        return timestamp, uuid.UUID(data["id"])
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        raise APIError(
            400,
            "INVALID_CURSOR",
            "Restart this search; its cursor is invalid or belongs to different filters.",
        ) from exc


def search(
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
):
    if account_id is not None:
        owned_account(db, user.id, account_id)
    query = visible_query(user.id, account_id, direction, reference)
    if min_amount is not None and max_amount is not None and max_amount < min_amount:
        raise APIError(422, "INVALID_AMOUNT_RANGE", "Maximum amount must be at least the minimum.")
    if date_from or date_to:
        if not date_from or not date_to:
            raise APIError(422, "INVALID_PERIOD", "Provide both start and end dates.")
        start, end, _ = period(date_from, date_to, user.timezone)
        query = query.where(Transfer.created_at >= start, Transfer.created_at < end)
    if min_amount is not None:
        query = query.where(Transfer.amount_vnd >= min_amount)
    if max_amount is not None:
        query = query.where(Transfer.amount_vnd <= max_amount)
    scope = hashlib.sha256(
        json.dumps(
            [
                str(user.id),
                str(account_id),
                direction,
                reference,
                str(date_from),
                str(date_to),
                min_amount,
                max_amount,
                user.timezone,
            ]
        ).encode()
    ).hexdigest()
    if cursor:
        at, transfer_id = decode_cursor(cursor, scope)
        query = query.where(tuple_(Transfer.created_at, Transfer.id) < tuple_(at, transfer_id))
    rows = list(
        db.scalars(
            query.order_by(Transfer.created_at.desc(), Transfer.id.desc()).limit(page_size + 1)
        )
    )
    items = rows[:page_size]
    next_cursor = (
        cursor_token(
            {"at": items[-1].created_at.isoformat(), "id": str(items[-1].id), "scope": scope}
        )
        if len(rows) > page_size
        else None
    )
    return items, next_cursor
