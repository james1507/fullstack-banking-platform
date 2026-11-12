# V2 implementation status

Updated 12 November 2026. Current delivery: **M0–M5 increment**. Overall V2 remains **in progress**. Repository branch `feat/v2-expansion`; starting commit `ec70182`; implementation and publication commits are recorded in Git history.

## Milestone completed

- M0: actual V1 audit, risk/gap matrix and baseline run before application changes.
- M1: independent-process money/idempotency tests; forced death before/after commit.
- M2: account lifecycle, type/status, daily limits, roles, immutable audit and operator/auditor UI.
- M3: owner-scoped beneficiaries, masked server preview, commit revalidation, safe retry and receipt printing.
- M4: signed keyset history, timezone dates, immutable funding baseline and repeatable-read reconciled CSV statements with exact aggregate strings.
- M5: one-time/weekly/monthly plans, idempotent creation, versioned future edit/pause/resume/cancel, fenced worker leases, bounded retries, shared atomic posting, transactional outbox, deduplicated inbox/read state and real UI.

M7 inbox delivery was pulled forward because it completes schedule-outcome visibility. Remaining M7 settings/policies are not complete. G0/G1 passed; product evidence exists for these slices. Full G2/G3/G4 release gates are not claimed.

## Source code changes

Preserved V1 files/routes and existing dependency set. Added domain modules/pages/tests and additive migrations: 002 lifecycle/roles/audit; 003 beneficiaries; 004 immutable reporting baseline/index; 005 schedules/occurrences/outbox/inbox. New worker service shares the backend image. Backup/restore scripts use PostgreSQL tools and an isolated restore DB. [Architecture](ARCHITECTURE.md) and [ADRs](ADR/003-scheduled-posting-and-delivery.md) explain boundaries/policies.

## Verified checks

**134 backend tests, 70 frontend tests, ten Chromium E2E journeys and 36 parity cases passed. Backend application line coverage: 95%.** Integrated `CAPTURE_V2=1 make ci` exited 0; final UI and calendar-boundary follow-ups also passed. [TEST_REPORT.md](TEST_REPORT.md) distinguishes exact commands/results, previous failures and fixes. Final startup rebuilt current code, readiness at migration 005. Remote GitHub Actions: NOT RUN.

## Invariants and security evidence

Ordered account locks and shared posting preserve nonnegative balances, conservation, paired immutable entries and exact scoped replay. Worker and API both check active CUSTOMER/ownership/status/limits. Schedule lock and lease token serialize lifecycle/execution; money and occurrence acknowledgment commit atomically. Event ID deduplicates inbox delivery. Statements use one repeatable snapshot and immutable seed baseline. Object/role denial, CSV injection, V1 upgrade and actual backup restore have regression evidence. Tests are evidence for exercised cases, not formal proofs.

## Backward compatibility

Original auth, accounts, POST transfer, page history, receipt and summary routes retained. Saved historical transfer JSON not rewritten. Interactive database migrated additively; no reset or demo transfer was performed during upgrade. Seeds preserve existing balances. New aggregate statement contract uses strings; V1 unsafe aggregate now rejects instead of rounding.

## Known issues / tradeoffs

- M6 categories/analytics/budgets, remaining M7 profile/security/preferences, M8 job/requeue/incident dashboards/metrics, optional M9 and complete M10/M11 remain pending.
- Inbox currently delivers transfer/schedule events only; no notification preference opt-out yet.
- Schedule list latest 200, occurrence history latest 50; one overdue attempt then next future slot, no catch-up burst. First date within 366 days, up to 120 terminal runs.
- Login/recipient limits are process-local. Local runtime DB role is privileged; no production deployment, MFA or secret-management claim.
- Same-page transfer/schedule retry retains original intent. Reload can lose recovery draft; inspect server history/plans before creating another intent.
- No worker heartbeat, metrics endpoint, load-test report, PDF statement or full WCAG audit. Chromium/ARM64 only tested locally; remote Linux execution pending.
- One supplemental browser run showed an unexplained 231-second input-action stall; unchanged full rerun passed all ten. No timeout relaxation; evidence/limits recorded in test report.
- Upstream build/deprecation warnings documented in test report. No dependency update was mixed into the feature change.

## Next action

M6 vertical slice: add owner-scoped categories and transfer annotations, then an exact server-side month aggregate with explicit user/account perspective, excluding own-account movement from spending. Add a real analytics page and PostgreSQL/IDOR/BigInt tests before budgets. Budget threshold events must extend the existing outbox consumer before showing alerts. Run `make test-backend`, frontend lint/build/unit and real-stack E2E; update this matrix/report after the slice.
