# V2 execution evidence

## Baseline — 12 November 2026

Starting commit: `ec70182`. Apple Silicon host, Docker PostgreSQL 16, Python 3.12 container, installed host Node/Chromium.

| Command | Result | Evidence |
|---|---|---|
| `make ci` before source changes | PASS, exit 0 | 70 backend (96% application lines), 59 frontend, five E2E, 36 parity cases; lint/build passed. `/tmp/moneta-v2-baseline.log` |
| `make test-backend` after M1 | PASS, exit 0 | 74 tests, 96% application line coverage, 19.27s; `/tmp/moneta-v2-core.log` |
| `make test-backend` after M2 | PASS, exit 0 | 90 tests, 96% application line coverage, 33.28s; `/tmp/moneta-v2-accounts.log` |
| `npm run lint && npm run build && npm test` after M2 | PASS, exit 0 | 62 tests in six files; strict TypeScript/production build passed |
| `make test-e2e` after M2 | PASS, exit 0 | Seven Chromium journeys, including account lifecycle, customer role denial and operator freeze/audit; `/tmp/moneta-v2-accounts-e2e.log` |
| `make test-backend` after M3 | PASS, exit 0 | 95 tests, 97% application line coverage, 36.60s; `/tmp/moneta-v2-beneficiaries.log` |
| Frontend lint/build/unit after M3 | PASS, exit 0 | 64 tests; server-preview rejection and inactive source selection covered |
| `CAPTURE_V2=1 make test-e2e` after M3 | PASS, exit 0 | Eight Chromium journeys, 7.4s. First run found mobile navigation overflow; fixed with native horizontal scrolling and reran all eight. `/tmp/moneta-v2-beneficiaries-e2e.log` |

M3 screenshots: `docs/screenshots/v2-beneficiaries.png`, `v2-receipt.png`, captured from the isolated real stack, not generated mockups.

M1 adds four independent-process tests: 52 same-key calls across four spawned processes; twelve distinct-key withdrawals across four processes; forced `os._exit` before commit; forced exit after commit and saved-result recovery. Actual PostgreSQL, synchronized process startup, no mocked locks. One upstream Starlette/AnyIO deprecation warning. This does not constitute a formal concurrency proof or load benchmark.

Remote GitHub Actions has not been executed by this local upgrade run. No new coverage, performance or availability claim is made without measured output.

## M4 — history and reconciled reporting

- `make test-backend`: 109 passed, 97% application line coverage, 38.88s, exit 0. Log `/tmp/moneta-v2-reporting.log`.
- Frontend lint/build/unit: 67 passed in seven files, exit 0. Log `/tmp/moneta-v2-web-tests.log`.
- `CAPTURE_V2=1 make test-e2e`: nine passed, 9.3s, exit 0. Log `/tmp/moneta-v2-reporting-e2e.log`. Actual CSV downloaded/read and mobile bounds checked; real screenshot saved.
- PostgreSQL test coordinates a statement read with a concurrent transfer commit and requires a consistent opening/closing snapshot. Leap dates, DST 23/25-hour days, pre-creation periods, row/date bounds, cursor ties/signature/filter/owner scope, immutable baseline and formula cells covered.

## M5 — scheduling, worker and in-app inbox

Targeted scheduling/account run: 39 passed, exit 0, 20.36s (`/tmp/moneta-v2-last-scheduler.log`). Later coverage is included in the integrated run below. Frontend run after adding uncertain-creation retry: 70 passed in eight files, 2.49s (`/tmp/moneta-v2-last-web.log`).

New evidence covers first-time schedule claims, unchanged/different creation keys, replay after due time, exact local clock boundaries, month-end, DST gap/overlap, one-time/recurring plans, future edits/version conflict, cancellation, pause fencing/resume, role/IDOR, closure guard, four worker processes, transient retry cap/backoff, expired-token fencing, business policy rechecks, and inbox scope/read/dedupe. Actual child processes exit before/after posting commit and between inbox insertion/ack; no mocked database locks.

## Recovery rehearsal and negative control

- `./scripts/backup-demo.sh /tmp/moneta-v1-before-v2-20261112.dump`: actual V1 archive created before interactive migration. Later final script variant (atomic no-overwrite hard link) exercised with `/tmp/moneta-before-schedules-20261112.dump`.
- `./scripts/restore-demo-check.sh /tmp/moneta-v1-before-v2-20261112.dump`: PASS, exit 0; repeated against head 005. Disposable DB restored/upgraded, same per-account balance fingerprint and posting counts; zero baseline reconciliation mismatches. `/tmp/moneta-v2-restore-head.log`.
- Interactive DB upgraded **001 → 005**; before/after account-balance fingerprint and counts match (**one pre-existing transfer, two ledger entries**); zero baseline reconciliation mismatches. No interactive reset or new demo transfer used. `/tmp/moneta-v2-interactive-before.txt` and `/tmp/moneta-v2-interactive-after.txt`.
- Negative control used a temporary source copy with account-owner predicate removed. `test_account_isolation_and_invisible_transfer` failed exactly `assert 200 == 404`, as intended; harness checked this failure and exited 0. Canonical source untouched, test DB only. `/tmp/moneta-v2-negative-control.log`.

## Failures found and fixed

Initial integrated M5 run: backend 127 passed / frontend 69 passed; E2E eight passed, two failed. Desktop sidebar length hid sign-out below the fixed viewport; redundant E2E logins hit the unchanged ten-per-minute throttle. Added native sidebar scrolling and reused the UI login token.

Second integrated run: backend 130 passed, 95% line coverage / frontend 69 passed; E2E nine passed, one failed because a test read login response JSON after navigating away. Test now reads response JSON immediately. No production authentication control was relaxed.

Earlier focused checks found TypeScript mutation-result union and EmptyState prop mismatches; corrected before integration. A clock assertion confused remaining outbox delivery with another schedule posting; it now checks occurrence queue and financial rows separately. These failures are not recorded as passing runs.

## Scope of evidence

Host: Apple Silicon `arm64`, Node `v24.20.0`; PostgreSQL 16 and Python 3.12.16 containers; Chromium Playwright. Backend coverage includes application lines, including worker loop/CLI branches that are not all exercised. Suite durations are not request performance benchmarks. Shared 36 fixture cases appear in language test counts; parity comparison does not add 36 UI journeys.

Warnings observed: upstream Starlette/AnyIO deprecation, Zod Rollup comment annotations, Vite entry chunk over 500 kB, npm ESLint deprecation/install-script notices. No dependency updates or warning suppression mixed into this change; build/tests succeed when reported as PASS. No actual load benchmark, full WCAG/contrast audit, public deployment, Linux amd64 execution or remote GitHub Actions run performed.

Local `/tmp` logs are session evidence paths; they are not shipped repository artifacts. Reproduce with documented Make commands. Final integrated/supplemental results below are authoritative for this increment.

## Final verified increment — 12 November 2026

| Execution | Exit | Actual result |
|---|---|---|
| `CAPTURE_V2=1 make ci` | 0 | 132 backend, 95% application line coverage, 44.96s; 70 frontend/eight files, 2.08s; 36 parity cases matched; Ruff/ESLint/Prettier/TypeScript/Compose build; ten E2E, 18.6s. `/tmp/moneta-v2-complete-increment-ci.log` |
| UI spacing/breadcrumb/capture follow-up: `make up`, frontend lint/build/test, `CAPTURE_V2=1 make test-e2e` | 0 | 70 frontend, eight files; ten E2E, 24.1s. Real captures refreshed; desktop cards and top-of-page statement image visually inspected. `/tmp/moneta-v2-ui-final.log` |
| Synchronized worker-start follow-up: backend Ruff + full PostgreSQL suite | 0 | 132 backend, 95%, 41.66s; four worker processes start together using a barrier before racing claims. `/tmp/moneta-v2-synchronized-workers.log` |
| Final calendar-boundary guard: backend Ruff + full PostgreSQL suite | 0 | **134 backend, 95%, 45.18s**; minimum/maximum datetime UTC conversion overflow maps to validated 422. `/tmp/moneta-v2-final-backend.log` |
| Final `make up` | 0 | API/frontend/worker running, DB healthy, current code rebuilt, readiness migration 005. `/tmp/moneta-v2-final-startup.log` |
| Delivery hygiene | 0 | `git diff --check`, shell syntax, Compose config and 15 local documentation link sets checked; five V2 screenshots inspected |

Latest verified totals: **134 backend / 70 frontend / ten Chromium E2E / 36 parity cases; 95% backend application line coverage**. Backend total increased by two after the integrated CI run; the final guard changed only rejected out-of-calendar input, followed by a full backend rerun and startup rebuild. Frontend and browser follow-up ran after the final UI changes. Those final executions passed without skips; the later cache follow-up and an unreproduced browser timing stall are documented below.

Actual V2 screenshots: `v2-beneficiaries.png`, `v2-receipt.png`, `v2-statements.png`, `v2-schedule.png`, `v2-inbox.png`. They show real committed test-stack outcomes; historical screenshot identifiers/times vary per run. Remote Actions remains **NOT RUN**.

## Final cache-coherence follow-up

Visual review found the recipient's last-used label still served from a fresh query cache immediately after posting. Transfer success now invalidates account detail, statements, beneficiaries and inbox as well as existing balance/history queries. E2E explicitly requires `Last used` after returning to the saved recipient.

- Frontend format/lint/build/unit: PASS, exit 0; 70 tests (`/tmp/moneta-v2-cache-ui.log`).
- First supplemental E2E execution: nine passed, one timeout in account lifecycle (4.3m total). Decoded Playwright trace showed input-fill call `umus@604` spanning **231,467.734ms**, followed by a snapshot containing the expected account and zero-balance heading. Root cause is **not established**; no production fix or timeout relaxation is attributed to this stall. Trace summary retained locally in `/tmp/moneta-v2-browser-stall-evidence.txt`.
- Unchanged full `CAPTURE_V2=1 make test-e2e` rerun: **ten passed, 23.5s, exit 0** (`/tmp/moneta-v2-cache-e2e-rerun.log`). Includes the new last-used cache assertion, real worker delivery, CSV download and refreshed actual screenshots. This is the latest browser execution.

The isolated timing stall remains a documented test-environment reliability limitation despite the successful unchanged rerun. Earlier successful integrated and final backend results remain valid; no backend code changed in this cache follow-up. Local documentation file links were checked across all 24 Markdown documents.
