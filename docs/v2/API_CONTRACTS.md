# V2 API contracts

All paths below start with `/api/v1`. Existing [V1 contracts](../api-contract.md) remain supported. Generated OpenAPI at `/docs` is the complete current schema. Money writes accept strict positive integer VND up to `9007199254740991`; strings, booleans, fractions and unknown input fields are rejected. Existing transfer response JSON is preserved for exact replay.

New customer routes require CUSTOMER and object ownership. Unknown/unowned object returns 404 where applicable. OPERATIONS may freeze/unfreeze; OPERATIONS/AUDITOR may read audit events. No request can assign role, ownership or balance.

| Method | Path | Actual behavior |
|---|---|---|
| POST | `/accounts` | Name + CHECKING/SAVINGS; zero-balance owned account, 201 |
| PATCH | `/accounts/{id}` | Name and/or nullable positive daily outgoing limit |
| POST | `/accounts/{id}/close` | `{ "confirmed": true }`; zero balance, no owner's active/paused linked plans |
| GET/POST | `/beneficiaries` | Search/include_archived (max 100 rows); add nickname + destination UUID |
| PATCH/DELETE | `/beneficiaries/{id}` | Rename / archive; returns saved record, no historical deletion |
| POST | `/beneficiaries/{id}/restore` | Revalidate destination and unique active owner/destination |
| POST | `/transfers/preview` | Same payload as transfer; validated estimate, masked destination; no claim/posting |
| GET | `/transfers/lookup-by-key?key=...` | Own completed `{status_code,response}`; absent result 404 means retry original safely |
| GET | `/transfers/search` | Fixed newest-first keyset search; existing page endpoint preserved |
| GET | `/accounts/{id}/statement/summary` | Reconciled totals and metadata; decimal-string VND |
| GET | `/accounts/{id}/statement` | Owner-scoped, audited UTF-8 CSV attachment |
| GET/POST | `/scheduled-transfers` | Latest 200 owned plans / create validated plan without debit, 201 |
| GET | `/scheduled-transfers/{id}` | Plan + latest 50 occurrence outcomes |
| PATCH | `/scheduled-transfers/{id}` | Full future definition plus current `version`; cannot edit claimed run |
| POST | `/scheduled-transfers/{id}/{pause,resume,cancel}` | `{ "version": 1, "confirmed": true }`; stale version 409 |
| GET | `/notifications` | Owner-only keyset inbox with unread count; `cursor`, `page_size` 1–50 |
| POST | `/notifications/{id}/read` | Idempotent mark-read; returns notification |
| POST | `/notifications/read-all` | Own unread rows only; returns `{updated: count}` |
| POST | `/ops/accounts/{id}/{freeze,unfreeze}` | OPERATIONS; reason CUSTOMER_REQUEST/RISK_REVIEW/TEST_INCIDENT; audited |
| GET | `/audit/events` | OPERATIONS/AUDITOR; limit 1–100, optional `before` event UUID |

## Search and statements

Search accepts `account_id`, `direction=INCOMING|OUTGOING`, `reference`, `date_from`, `date_to`, `min_amount`, `max_amount`, `status=SUCCEEDED`, `page_size`, `cursor`. A date range requires both dates. Cursor signature binds user, filters and timezone; changes require starting without a cursor. Response: `{items,next_cursor,page_size}`. No arbitrary column/order expression, category filter or destination search is currently exposed.

Statements require inclusive `date_from` and `date_to`; optional IANA `timezone` defaults to user setting. Maximum 366 days / 5,000 entries. New account dates earlier than creation are zero; overlapping dates use the effective account creation time. A statement summary has these fields (illustrative values, not a captured response):

```json
{
  "account_id": "00000000-0000-4000-8000-000000000001",
  "account_number": "DEMO-100001",
  "date_from": "2026-11-01", "date_to": "2026-11-12",
  "timezone": "Asia/Ho_Chi_Minh", "effective_from": "2026-11-12T00:00:00Z",
  "money_encoding": "decimal-string-vnd",
  "opening_balance_vnd": "5000000", "closing_balance_vnd": "4850000",
  "total_debit_vnd": "150000", "total_credit_vnd": "0", "row_count": 1
}
```

CSV includes ACCOUNT, PERIOD, OPENING, TRANSFER and CLOSING records with exact running balance and UTC/local timestamps. Frontend parses summary amounts with BigInt, never Number.

## Scheduling

Creation also requires `Idempotency-Key` (8–100 ASCII letters/digits/underscores/hyphens). Same user/key/input replays the original creation response, including after the first due time; changed input is 409. API and UI keep this key separate from the later occurrence posting key.

Actual request shape (choose a future local date within 366 days):

```json
{
  "source_account_id": "00000000-0000-4000-8000-000000000001",
  "destination_account_id": "00000000-0000-4000-8000-000000000002",
  "amount_vnd": 200000, "memo": "Monthly fictional plan",
  "timezone": "Asia/Ho_Chi_Minh", "starts_local": "2026-12-10T09:00:00",
  "recurrence": "MONTHLY", "max_runs": 12
}
```

`starts_local` must have no offset; timezone is separate. ONCE requires max_runs 1. First run is future/at most 366 days away; total attempted terminal runs 1–120. Funds are checked at execution, not reserved at creation. [ADR 003](ADR/003-scheduled-posting-and-delivery.md) defines DST, month-end, downtime and pause policies. Occurrences expose ID, due time, state, attempt count, transfer ID, sanitized last error and request ID. A FAILED_PERMANENT business outcome cannot later debit under the same occurrence identity. Cancellation preserves already posted transfers.

## Errors and compatibility

Envelope remains `{error:{code,message,details,request_id}}`. Header `X-Request-ID` is the current request; a replayed business-error body keeps the original ID.

New stable codes include `ACCOUNT_NOT_ACTIVE`, `ACCOUNT_NOT_EMPTY`, `ACCOUNT_HAS_SCHEDULES`, `TRANSFER_LIMIT_EXCEEDED`, `TRANSFER_LIMIT_INVALID`, `RECIPIENT_UNAVAILABLE`, `BENEFICIARY_EXISTS`, `INVALID_CURSOR`, `INVALID_LOCAL_TIME`, `INVALID_SCHEDULE_START`, `INVALID_RECURRENCE`, `STALE_VERSION`, `SCHEDULE_BUSY`, `SCHEDULE_TERMINAL`, `INVALID_SCHEDULE_STATE`, `SCHEDULE_NOT_FOUND`, `NOTIFICATION_NOT_FOUND`. See source for exact statement validation codes. Transient connection/pool failures return sanitized `503 SERVICE_UNAVAILABLE`. Unknown money outcomes must retain original key/payload; absence from lookup is not proof no in-flight commit exists.

Current limitations: inbox has no unread/kind filter or notification preferences; audit UI displays latest 50 although API supports `before`; schedule list/history are bounded rather than paginated; settings/analytics/operations-job APIs are not implemented. No alternate contracts are silently advertised as live.
