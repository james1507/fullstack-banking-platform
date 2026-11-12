# V2 feature matrix

Updated 12 November 2026. Status reflects executable implementation and tests, not planned filenames. This delivery is the M0–M5 increment; full V2 is **in progress**.

| Feature | Status | Priority | Owner module | Milestone | Evidence / remaining work |
|---|---|---|---|---|---|
| Atomic posting, immutable balanced ledger | EXISTS | P0 | transfers / migration 001 | M1 | `test_platform.py`; conservation, paired entries, rollback and mutation rejection |
| Exact idempotency, uncertain-outcome retry | EXISTS | P0 | transfers / typed client | M1/M3 | Same/changed key, terminal saved rejection, timeout UI; same-page retry retains key/payload |
| Auth, refresh rotation, ownership | EXISTS | P0 | security | M1 | Expiry, family reuse/concurrent refresh, Origin/IDOR tests; memory bearer |
| Multi-process posting/recovery | EXISTS | P0 | recovery tests | M1 | Four processes, 52 same-key requests, distinct-key overspend, forced pre/post-commit exit |
| Account lifecycle/type/status/daily limits | EXISTS | P1 | accounts | M2/M5 | Open zero/rename/close, freeze, concurrent limits/closure, own linked schedule guard, real UI |
| Roles and append-only audit | EXISTS | P1 | identity / operations | M2 | Server guards, mass assignment/IDOR, immutable audit, operator controls, auditor read-only UI |
| Beneficiaries | EXISTS | P1 | beneficiaries | M3 | Search/add/rename/archive/restore/duplicate guard; real browser add/use/archive/restore |
| Server review and printable receipt | EXISTS | P1 | transfer UI | M3 | Shared preview/posting checks, masked destination, estimate; stale freeze rechecked |
| Advanced history | EXISTS | P1 | reporting | M4 | Signed user/filter-bound keyset cursor, tie ordering, date/direction/reference/amount/account filters; V1 page API preserved |
| Reconciled CSV statements | EXISTS | P1 | reporting | M4 | Snapshot concurrency, immutable baseline, inclusive timezone dates, formula protection, BigInt-safe totals, actual download |
| Scheduled/recurring transfers and UI | EXISTS | P1 | scheduling | M5 | One-time/weekly/monthly, timezone/DST/month-end, maximum runs, versioned future edit/pause/resume/cancel; idempotent creation |
| Reliable worker | EXISTS | P1 | worker | M5 | SKIP LOCKED lease, token fencing, capped jittered retry, terminal business errors, shared posting; process-death tests |
| Transactional outbox / inbox | EXISTS | P1 | worker / inbox | M5/M7 | Money-transaction event creation, unique event dedupe, crash/redelivery tests, owner cursor/read states and real UI |
| Complete notification policy | PARTIAL | P1 | notifications | M7 | Transfer and schedule notifications work; preferences, freeze/budget/security kinds and kind/unread filters pending |
| Profile preferences / security settings | PARTIAL | P1 | identity | M7 | Validated stored timezone/locale and role exist; profile editing, password change, session list/revoke missing |
| Dashboard | PARTIAL | P1 | pages / summary | M6 | Actual owned balances/counts/recent transfers; trends, period aggregate charts and pending schedule KPI missing |
| Categories, analytics and budgets | MISSING | P1 | analytics | M6 | Owner annotations, internal-vs-external perspective, exact aggregates and threshold events next |
| Operations center / incident UI | PARTIAL | P1 | operations | M8 | Account freeze/audit work; queue/requeue/reconciliation dashboards, dev incident UI and metrics missing |
| Incident regression evidence | PARTIAL | P1 | tests / runbooks | M1/M5/M8 | Actual process crash, duplication, overspend, refresh, stale review and delivery failure tests; full M8 catalog pending |
| Savings goals/templates/support/reconciliation UI | MISSING | P2 | optional modules | M9 | Deferred until P1 gates; no placeholder routes |
| Migration/backup rehearsal | EXISTS | P0 | Alembic / scripts | M2/M4/M5 | Seeded V1 upgrade test and actual disposable restore preserve balances/posting counts |
| Local CI / screenshots / engineering docs | PARTIAL | P0 | delivery | M10 | Real checks/captures and current docs; remote Actions, contract drift automation, performance/accessibility breadth pending |

`EXISTS` does not imply production certification, all possible interleavings, or implementation of adjacent backlog items. [Status](IMPLEMENTATION_STATUS.md), [test evidence](TEST_REPORT.md), [ADRs](ADR/001-incremental-upgrade.md).
