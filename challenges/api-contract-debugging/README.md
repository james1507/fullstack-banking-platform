# Challenge C: a balance disappears; a conflict looks like success

## Symptoms

A client reads `response.balance` while the API sends `balance_vnd`. The dashboard renders `NaN`. Another client unconditionally reads `response.json()` and treats an insufficient-funds 409 as a successful receipt.

## Find the boundary

1. Compare the browser Network response to `/docs`; inspect the generated `X-Request-ID`.
2. Confirm `balance_vnd` is an integer, not a formatted string, and errors use `{error:{code,message,details,request_id}}`.
3. Check the shared web boundary schema and `response.ok` handling rather than patching individual pages.

## Fix

`frontend/src/lib/api.ts` parses successful responses through Zod and errors through a stable envelope. It preserves the status/code and never turns a 409 into transfer success. `formatVND` formats only a validated number at render time. React renders readable business errors while keeping entered values.

## Regression

`frontend/src/test/api.test.ts` deliberately supplies a renamed balance field and an unsafe integer. Both fail the account schema. Another test asserts a 409 preserves `INSUFFICIENT_FUNDS`, status and request ID. Component tests assert error rendering and unknown-outcome same-key retries. Browser tests exercise a successful real API transfer and a changed-input key conflict.

Run `make test-frontend` and `make test-e2e`. No broken fixture is imported by shipping code.
