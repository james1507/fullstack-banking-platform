# Local upgrade and recovery checklist

This checklist is for the synthetic local demo. Production disaster recovery/HA is not implemented. Current head: 005; M0–M5 increment, not a completed V2 release.

1. Confirm target project, `.env`, available ports and database volume. Preserve working changes. Inspect `docker compose ps`, `git status` and `git diff`; do not reset the volume to apply a migration.
2. Run `./scripts/backup-demo.sh /absolute/private/path/moneta.dump`. Script uses pg_dump custom format, private file mode and refuses existing destinations. Keep archives out of Git.
3. Run `./scripts/restore-demo-check.sh /absolute/private/path/moneta.dump`. It restores into a fresh `restore_*_test` database, upgrades head, compares account-balance fingerprint/posting counts and checks baseline reconciliation. It removes only its own disposable database on exit.
4. Review migrations 002–005 and [ADRs](ADR/001-incremental-upgrade.md). They preserve V1 rows and add lifecycle/audit, beneficiaries, baseline and scheduling/outbox tables. Upgrade test constructs a V1 posting before migrating. Migration 004 refuses invalid historical baseline; investigate instead of rewriting money.
5. Stop worker before a schema-changing deployment with `docker compose stop worker`. Local startup applies migration once in backend before API starts; run only one migrator. Multiple production API replicas need a separate migration job, which is not configured here.
6. Run `docker compose up --build -d --wait`. Worker starts after API readiness. No balance reset; repeatable seed adds staff while preserving existing balances. Images share code but run distinct API/worker commands.
7. Check `curl --fail http://localhost:8000/health/ready`, `docker compose ps`, then backend/worker logs. Head must be 005; worker should stay running without error loop. No worker heartbeat healthcheck currently exists.
8. Compare balances and committed transfer/ledger counts with preflight. On a quiet interactive DB they must stay unchanged by migration. Exercise customer/role UI on the separate E2E stack: `CAPTURE_V2=1 make test-e2e`. `make ci` includes unit, PostgreSQL/process, migration, parity and browser checks.

## Observed rehearsal

On 12 November 2026 the existing V1 demo was backed up, restored into a disposable database and upgraded to current head. Per-account balance fingerprint, transfer count and ledger count were unchanged; account baseline reconciliation had zero mismatches. Logs/commands appear in [TEST_REPORT.md](TEST_REPORT.md). Backup file locations are local artifacts, not repository deliverables.

## Failure and rollback policy

If migration/readiness fails, stop worker/API and inspect sanitized logs. Do not run downgrade/drop/reset or alter ledger/balances to make checks green. Keep original volume and backup; rehearse a forward fix on a disposable restored DB first. Migrations explicitly reject downgrade because historical financial/audit data must be retained. An application rollback is allowed only after verifying old code understands the expanded schema and policy; this compatibility was not tested as a rolling deployment. Restoring an old snapshot can discard later committed postings and requires an explicit recovery decision, not an automated command here.

Separate migrator/runtime DB privileges, point-in-time recovery, off-host encryption, backup retention, restore-time objectives, worker heartbeat and public deployment remain pending. The local successful rehearsal is evidence only for the tested archive and upgrade path.
