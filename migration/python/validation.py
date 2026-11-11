"""Pure, deterministic transfer validation. No database, clock or network."""

import math
import re

MAX_AMOUNT = 9_007_199_254_740_991
UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
FIELDS = {"source_account_id", "destination_account_id", "amount_vnd", "memo"}


def validate(payload):
    def fail(code, field):
        return {"ok": False, "code": code, "field": field}

    if not isinstance(payload, dict):
        return fail("INVALID_PAYLOAD", "payload")
    if set(payload) - FIELDS:
        return fail("UNKNOWN_FIELD", "payload")
    for field in ("source_account_id", "destination_account_id", "amount_vnd"):
        if field not in payload:
            return fail("REQUIRED", field)
    for field in ("source_account_id", "destination_account_id"):
        if not isinstance(payload[field], str) or not UUID_PATTERN.fullmatch(payload[field]):
            return fail("INVALID_ACCOUNT_ID", field)
    source, destination = (
        payload["source_account_id"].lower(),
        payload["destination_account_id"].lower(),
    )
    if source == destination:
        return fail("SELF_TRANSFER", "destination_account_id")
    amount = payload["amount_vnd"]
    if (
        isinstance(amount, bool)
        or not isinstance(amount, (int, float))
        or not math.isfinite(amount)
        or int(amount) != amount
    ):
        return fail("INVALID_AMOUNT", "amount_vnd")
    if amount <= 0:
        return fail("AMOUNT_NOT_POSITIVE", "amount_vnd")
    if amount > MAX_AMOUNT:
        return fail("AMOUNT_TOO_LARGE", "amount_vnd")
    memo = payload.get("memo")
    if memo is not None:
        if not isinstance(memo, str):
            return fail("INVALID_MEMO", "memo")
        if len(memo) > 200:
            return fail("MEMO_TOO_LONG", "memo")
        memo = memo.strip(" \t\n\r\f\v") or None
    return {
        "ok": True,
        "value": {
            "source_account_id": source,
            "destination_account_id": destination,
            "amount_vnd": int(amount),
            "memo": memo,
        },
    }
