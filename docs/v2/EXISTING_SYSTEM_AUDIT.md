# V2 existing-system audit

Audited 12 November 2026, starting from `ec70182` on `feat/v2-expansion`.
This is an incremental upgrade of a fictional banking simulation.

## Verified source inventory

- React 19 / TypeScript 5.9 / Vite 7 / Tailwind 4; React Router 7, TanStack Query 5, React Hook Form, Zod 4. Dependencies locked in `frontend/package-lock.json`.
- Python 3.12 / FastAPI 0.121 / synchronous SQLAlchemy 2 / psycopg 3 / PostgreSQL 16. Direct dependencies pinned in `backend/pyproject.toml`; no dependency changes required for initial slices.
- `frontend/src/main.tsx`: `/login`, `/`, `/accounts`, `/transfers/new`, `/transfers`, `/transfers/:id`, `/about`, authenticated not-found route.
- `AppShell`, `Select`, shared UI, `TransferForm`, auth provider and typed runtime-validated HTTP client already work. Preserve existing green/cream visual tokens and keyboard dropdowns.
- `backend/app/main.py`: login/refresh/logout/me, owned account list/detail, transfer create/list/detail, dashboard summary, liveness/readiness.
- Migration `001`: users, accounts, transfers, paired ledger entries, idempotency records, refresh sessions. Database triggers reject transfer/ledger mutation and defer balanced-pair verification until commit.
- Transfer service: scoped unique claim, canonical hash, exact response storage, globally ordered account row locks, single transaction. Business rejections are saved; unexpected failures roll back the claim.
- Argon2id passwords, memory-only bearer token, 15-minute access TTL, seven-day rotating HttpOnly refresh cookies, reuse family revocation, exact Origin guard, process-local sign-in limit. No role model yet.
- Compose: PostgreSQL, API, Nginx frontend. Backend entrypoint migrates/seeds; readiness hardcodes revision `001` and must evolve before adding migrations.
- CI: real PostgreSQL quality job and separate Compose/Chromium E2E job; remote execution not assumed from workflow presence.

## Baseline checks

`make ci` launched before source changes, output `/tmp/moneta-v2-baseline.log`.
Final results recorded in [TEST_REPORT.md](TEST_REPORT.md). V1 evidence from 11 November: 70 backend, 59 frontend, five browser tests; 36 shared parity cases; 96% application line coverage. Historical counts are not a new V2 pass.

Tests live in `backend/tests`, `frontend/src/test`, `frontend/e2e`. Commands: `make test-backend`, `make test-frontend`, `make parity`, `make lint`, `make test-e2e`, `make ci`. Backend fixtures guard the `_test` suffix. E2E uses project `moneta-e2e`; interactive data must survive.

## Gaps and risks

| Risk | Mitigation / migration sequence |
|---|---|
| No account lifecycle, roles, limits or durable audit | Add columns with defaults/backfill; lock same account rows as posting for lifecycle actions. Reject supplied balance/owner/role fields. |
| V1 tests prove thread concurrency, not independent processes | Add PostgreSQL multi-process replay/overspend tests and post-commit recovery evidence before product expansion. |
| No beneficiary resolution or server preview | Add owner-scoped address book, minimal recipient preview, bounded/rate-limited lookup. Recheck eligibility at posting. |
| Opening balances not represented in ledger | Preserve V1 history; backfill immutable opening baseline from current balance minus net ledger movement before statements/reconciliation. |
| Sum of individually safe accounts may exceed JS safe integer | Explicitly reject unsafe aggregate transport or adopt a versioned string contract; never round. |
| No worker/outbox/schedules | Defer until account and transfer guards have regression evidence. Add stable occurrence identity before any background posting. |
| Existing refresh concurrency is per tab | Keep conservative reuse behavior; record cross-tab limit. |
| Startup migration concurrency / shared local DB role | Keep demo startup compatible; document single migrator and forward-fix policy. |

## Proposed delivery order

1. M0 audit and baseline; M1 process-level core/recovery tests.
2. M2 additive account lifecycle, RBAC, audit, profile metadata, race-safe daily limits, actual UI.
3. M3 beneficiaries, server preview, same-key lookup, printable receipts.
4. M4 advanced history and reconciled CSV statements.
5. M5–M8 worker/outbox/schedules, analytics/budgets, settings/inbox, operations and controlled incidents.
6. M10 consolidated CI/docs and real screenshots; P2 only after essential slices pass.

No public deployment, destructive reset, commit or push is part of this upgrade run.
