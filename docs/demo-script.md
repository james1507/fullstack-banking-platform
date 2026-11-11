# Seven-minute interviewer walkthrough

1. **0:00–0:45** — README: simulation notice, architecture, test matrix. Start with `cp .env.example .env && make up`. Open localhost:5173.
2. **0:45–2:00** — Sign in as Alice. Show 5,000,000 VND on a fresh volume, account ID copy and Bob's public demo ID. Explain memory-only bearer token and rotating HttpOnly cookie. Reload to demonstrate restoration.
3. **2:00–3:00** — Send 150,000 VND to Bob with a memo. Review recipient and amount, confirm. Show receipt and 4,850,000 VND. Sign in as Bob to show 3,150,000 VND. These exact balances assume a fresh database and no prior transfers.
4. **3:00–4:15** — Open `backend/app/transfers.py`. Explain unique claim, sorted row locks, one commit and saved response. Show `test_success_and_exact_replay` and 24-way concurrency regression.
5. **4:15–5:15** — Run `make test-backend`. Explain injected failure rollback, authorization and ledger invariants. Show the actual output, not a screenshot of a pretend CI run.
6. **5:15–6:15** — Open shared fixtures and `docs/migration-parity.md`. Run `make parity`. Discuss Python bool/int and JavaScript safe-integer and Unicode differences.
7. **6:15–7:00** — Show real GitHub Actions status after pushing, or say it has not run yet. Show frontend/Playwright tests and honest limitations.

Suggested repository description:

> React + FastAPI + PostgreSQL simulated banking platform with atomic transfers, idempotency, rotating authentication, E2E tests and Python/TypeScript validation parity.

Suggested topics: `fullstack`, `react`, `typescript`, `fastapi`, `postgresql`, `docker`, `github-actions`, `playwright`, `idempotency`.

Interview summary to adapt to your own understanding:

> I built a full-stack simulated banking app and validated the parts that are easy to get subtly wrong: transaction boundaries, concurrent spending, idempotent retries and object authorization. The browser uses one typed API boundary; PostgreSQL owns concurrency. I can demonstrate failure rollback and explain the tradeoffs in the security and migration docs.

Review every design decision before presenting it. Describe AI assistance honestly if asked. Do not claim production banking experience or a GitHub CI pass that did not occur.
