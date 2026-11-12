# HTTP contract

> **V1 baseline document.** Preserved for historical context. The [V2 addendum](v2/API_CONTRACTS.md) and [current feature matrix](v2/FEATURE_MATRIX.md) describe this branch’s implemented behavior and verification.

Interactive OpenAPI: `http://localhost:8000/docs`. Base: `/api/v1`. Amounts and balances are fictional, positive/nonnegative JSON-safe integer VND. Unknown transfer input fields are rejected.

| Method | Route | Success | Notes |
|---|---|---|---|
| POST | /auth/login | 200 token | email/password, exact Origin; sets HttpOnly cookie |
| POST | /auth/refresh | 200 token | cookie + exact Origin; rotates refresh session |
| POST | /auth/logout | 204 | cookie + Origin; revokes family and clears cookie |
| GET | /auth/me | 200 profile | bearer required |
| GET | /accounts | 200 array | owned accounts only |
| GET | /accounts/{id} | 200 account | invisible/missing account: 404 |
| POST | /transfers | 201 transfer | bearer + `Idempotency-Key` required |
| GET | /transfers | 200 page | page>=1; page_size 1–50; optional account_id, direction, reference |
| GET | /transfers/{id} | 200 transfer | either account owner only |
| GET | /dashboard/summary | 200 summary | total_balance_vnd, account_count, transfer_count, recent_transfers |
| GET | /health/live | 200 | process only |
| GET | /health/ready | 200/503 | migration revision and DB connectivity |

Transfer input:

```json
{"source_account_id":"00000000-0000-4000-8000-000000000001","destination_account_id":"00000000-0000-4000-8000-000000000002","amount_vnd":150000,"memo":"Demo transfer"}
```

Response includes `id`, `reference`, `status: "SUCCEEDED"`, `currency: "VND"`, source/destination IDs, integer amount, nullable memo and UTC creation timestamp. References use year plus a random UUID suffix to avoid sequence allocation races. Source/destination are public fictional account IDs; no counterparty email/profile is exposed.

History returns `{items,page,page_size,total,total_pages}` sorted by `created_at DESC, id DESC`. Direction means money out of/into owned accounts, or the selected owned account. An internal transfer can match both directions.

Idempotency keys contain 8–100 ASCII letters/digits/underscore/hyphen. Scope is authenticated user + operation. Same input replays the exact saved status/body; changed input returns 409. `X-Idempotency-Replayed` indicates a replay. Completed business-error bodies retain their original request ID; `X-Request-ID` identifies the current HTTP request.

Errors:

```json
{"error":{"code":"INSUFFICIENT_FUNDS","message":"The source account has insufficient funds.","details":{},"request_id":"generated-uuid"}}
```

| Code | Status |
|---|---|
| UNAUTHENTICATED, INVALID_CREDENTIALS, REFRESH_REUSED | 401 |
| ORIGIN_REJECTED | 403 |
| ACCOUNT_NOT_FOUND, TRANSFER_NOT_FOUND, NOT_FOUND | 404 |
| INSUFFICIENT_FUNDS, IDEMPOTENCY_KEY_REUSED, BALANCE_LIMIT, REQUEST_IN_PROGRESS | 409 |
| VALIDATION_ERROR, INVALID_IDEMPOTENCY_KEY, SELF_TRANSFER, CURRENCY_MISMATCH | 422 |
| RATE_LIMITED | 429 |
| INTERNAL_ERROR | 500 |
| NOT_READY | 503 |
| HTTP_ERROR | other framework HTTP errors |

`VALIDATION_ERROR.details.fields` is an array of `{field,message}` with no submitted input values. The web client also has local `NETWORK_ERROR`, `SERVER_ERROR` and `CONTRACT_ERROR` codes. Unknown network/5xx outcomes preserve the original transfer key and payload for explicit retry. Schema rejections and business conflicts preserve visible form values.
