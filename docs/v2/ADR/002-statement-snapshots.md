# ADR 002: Reconciled statements and exact aggregate transport

Accepted 12 November 2026.

Preserve the V1 integer JSON contract for individual balances and postings. Turnover across many transfers may exceed JavaScript's safe integer range even when each posting is valid. New statement aggregate fields use canonical decimal strings and `money_encoding: decimal-string-vnd`; React renders them through `BigInt` and `Intl.NumberFormat`.

Migration 004 backfills immutable `opening_balance_vnd = current balance - net ledger`. It rejects a negative or unsafe baseline. Synthetic seed funding becomes an explicit historical baseline, without inventing transfers. New accounts start at zero. Existing balances and entries are preserved.

Read account, opening movements and period entries in one PostgreSQL REPEATABLE READ transaction. A coordinated concurrent-commit test verifies that a statement cannot mix the old balance with new entries. Calendar dates are inclusive in a validated IANA timezone, converted to a half-open UTC interval. Periods entirely before account creation are zero; overlapping periods start at creation and include seed baseline as opening funding.

Statements are limited to 366 days and 5,000 entries. CSV uses a BOM, fixed safe filename, UTC/local timestamps, running balances and formula-cell protection. Every export is owner-scoped and audited. Larger exports need a separately bounded asynchronous export design.

Advanced search keeps the V1 page route and adds `(created_at DESC, id DESC)` keyset pagination. Its HMAC cursor is bound to user, filters and timezone. Signing-secret rotation invalidates cursors; clients restart search. Search supports newest-first order only.
