# Tested incident reproductions

These are controlled local/test scenarios, not production outages. Fault hooks exist only in test processes; there is no shipping `/dev/incidents` endpoint. Full operator incident UI, metrics and six-scenario interactive catalog remain M8 work.

## Reproduction environment

Start the demo with `.env` and `make up`, then `./scripts/create-test-db.sh`. The following command runs all scenarios below against guarded `banking_test`; fixtures refuse a database name without `_test`. Interactive demo data is preserved.

```bash
docker compose run --rm --no-deps -v "$PWD/backend:/app" backend sh -c 'DATABASE_URL="${DATABASE_URL%/*}/banking_test" pytest tests/test_recovery.py tests/test_scheduling.py tests/test_platform.py tests/test_beneficiaries.py tests/test_accounts.py -q'
```

For individual investigation, replace the pytest file selection with the exact node ID in the table. Do not run two suites simultaneously against the same disposable database.

| Scenario / exact pytest node | Detection and triage | Expected behavior / mitigation | Cleanup |
|---|---|---|---|
| Duplicate processes: `tests/test_recovery.py::test_fifty_two_retries_across_four_processes` | Many same-key calls; inspect saved transfer IDs/counts | 52 calls, four processes, one effect. Unique DB claim is coordinator; retain original key | Fixture truncates only test DB |
| Concurrent overspend: `tests/test_recovery.py::test_distinct_keys_across_processes_cannot_overdraw` | 12 requests contend for 5,000,000 VND | Five successes/seven conflicts; sorted locked balances prevent overdraw | Test fixture |
| App death before commit: `tests/test_recovery.py::test_process_death_before_commit_rolls_back` | Child exits 86 during ledger insertion; response lost | No money/key survives; same-key retry completes. Avoid client-side balance restoration | Child joined; test fixture |
| Response lost after commit: `tests/test_recovery.py::test_process_death_after_commit_replays_saved_result` | Child exits 87 with no delivered receipt | Money remains posted once; original retry returns exact saved result. Inspect history/lookup if UI reloaded | Child joined; test fixture |
| Worker death/fencing: `tests/test_scheduling.py::test_process_death_reclaim_and_fenced_old_lease` | CLAIMED occurrence, expired lease; child exit before/after commit | Precommit rollback or saved atomic outcome. Reclaim after 60 seconds; same occurrence key and new token | Controlled test clock, no wall-time sleep; child joined |
| Inbox acknowledgment loss: `tests/test_scheduling.py::test_outbox_process_death_before_ack_recovers_without_duplicates` | Child exits 88 before outbox acknowledgment update | Inbox insert/ack rolls back together; reclaimed event delivers once. Never insert a second visible alert | Controlled clock; child joined |
| Stale review after freeze: `tests/test_beneficiaries.py::test_preview_is_read_only_and_freeze_is_rechecked` | Preview succeeded, subsequent commit sees frozen source | Commit rejects with ACCOUNT_NOT_ACTIVE; preview never guaranteed funds/status | Isolated fixture |
| Refresh reuse: `tests/test_platform.py::test_refresh_rotation_reuse_revokes_family` | Old cookie presented after rotation | Family revoked, later refresh rejected. Sign in again; do not disable reuse guard | Synthetic sessions reset by fixture |
| Temporary DB failure: `tests/test_accounts.py::test_database_unavailable_returns_safe_retryable_contract` | Injected connection failure, HTTP 503 + request ID | SERVICE_UNAVAILABLE; no SQL/credential leakage; retain original write key when outcome unknown | Monkeypatch auto-reverted |
| Paused/stale schedule: `tests/test_scheduling.py::test_pause_fences_claim_and_resume_skips_missed_slots` | Claim existed before pause, stale worker attempts to run | Schedule lock/token fence prevents posting. Resume selects next future slot, no burst catch-up | Controlled clock and fixture |

## Interactive triage

Inspect `docker compose ps`, `docker compose logs --tail=100 backend worker`, health readiness, own transfer history, schedule occurrence state/error/attempts and inbox. HTTP logs carry current request ID; schedule UI/API exposes the stable occurrence correlation ID. Worker logs identify job UUID, which links to stored request ID.

A completed transfer must never be edited/deleted to recover a UI timeout. Business rejection is terminal for that occurrence; fix the cause for future slots or create a deliberate new intent. A DEAD_LETTER outbox row means delivery exhausted; money is unaffected. Manual safe requeue UI is pending; do not invent a fresh transfer key to retry a completed occurrence.

## Actual issues found during this increment

- Adding navigation exposed mobile horizontal overflow and later a desktop sign-out control below a fixed sidebar. Native horizontal/vertical scrolling restored access; real browser journeys cover viewport bounds and logout.
- Expanded E2E suite made redundant login calls and hit the unchanged ten-per-minute protection. Tests now reuse the UI login response token; they read its JSON before navigating away. Production rate limits were not weakened.
- An early worker clock test treated legitimate pending outbox delivery as an unexpected schedule execution. The assertion now checks the occurrence queue directly and separately verifies postings.

Slow queries, deadlock retry under induced DB deadlock, burst load, connection-pool saturation under real concurrency, transient proxy failures, public deployment rollback and notification-backlog dashboards are pending; an injected 503 test does not prove their resolution.
