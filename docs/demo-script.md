# Eight-minute interviewer walkthrough

Current demo covers the M0–M5 increment. Use public synthetic accounts only. [Feature matrix](v2/FEATURE_MATRIX.md) states pending V2 work; do not present unimplemented analytics/settings/operations pages.

1. **0:00–0:45** — README: simulation notice, current verification and [architecture](v2/ARCHITECTURE.md). Start with `cp .env.example .env` (first setup only), then `make up`. Show API/DB/frontend/worker in Compose. Open localhost:5173.
2. **0:45–1:30** — Sign in as Alice. Explain API-owned balances, memory-only bearer and rotating HttpOnly refresh. Reload. On a fresh volume seed is 5,000,000 VND; existing data may differ.
3. **1:30–2:30** — Save Bob as recipient, use it for a 150,000 VND transfer. Show server preview, masked destination, zero fee and estimated balance; confirm and open printable receipt. Explain original key/payload recovery for uncertain outcomes.
4. **2:30–3:15** — Open an empty savings account, rename and configure daily outgoing limit. Show ACTIVE/FROZEN/CLOSED rules. Creating an account never creates money.
5. **3:15–4:00** — Search history with amount/date/account filters; open Statements. Download actual CSV. Explain immutable funding baseline, REPEATABLE READ and `opening + credits - debits = closing`, including BigInt-safe totals.
6. **4:00–5:30** — Create a one-time plan at a near-future local clock, review/confirm. Show no debit at creation, then real worker outcome/receipt and inbox. Explain fixed occurrence key, lease token, shared posting transaction and deduped delivery. If timing is inconvenient, show the actual E2E screenshot and runnable test; do not pretend a future plan has already executed.
7. **5:30–6:15** — Sign out and use `operator@example.test` to freeze/unfreeze with reason. Use Auditor or Operations to view immutable audit. Customer cannot access those writes, even with a forged API request.
8. **6:15–7:15** — Open `backend/app/transfers.py` and `backend/tests/test_recovery.py`. Run `make test-backend` or show current genuine output. Discuss process death before/after commit, worker recovery and concurrent statement snapshot. [Runbooks](v2/INCIDENT_RUNBOOKS.md) contain exact reproductions.
9. **7:15–8:00** — Show verification, V1-upgrade/backup rehearsal and limitations. Remote GitHub Actions is unverified until actually pushed/run. Explain next M6 categories/analytics/budgets work; no production reliability/certification claim.

Suggested repository description:

> React + FastAPI + PostgreSQL banking simulation with atomic transfers, idempotent retries, scheduled payments, a durable worker, reconciled CSV statements and real-process recovery tests.

Topics: `fullstack`, `react`, `typescript`, `fastapi`, `postgresql`, `docker`, `github-actions`, `playwright`, `idempotency`, `transactional-outbox`.

Understand each demonstrated decision and describe AI assistance honestly if asked. Local portfolio checks do not imply production banking experience.
