# Database and invariants

| Table | Purpose | Important constraints |
|---|---|---|
| users | Synthetic identities | unique lowercase email; Argon2id hash |
| accounts | Materialized VND balance | owner FK, unique display number, VND only, `0 <= balance <= 2^53-1` |
| transfers | Committed successful movements | distinct accounts, positive safe integer, unique reference, immutable rows |
| ledger_entries | Debit and credit audit trail | positive amount, one entry per transfer/direction, matching account/amount trigger, immutable rows |
| idempotency_records | Exact operation result | unique `(user_id, operation, key)`, canonical request hash, JSONB response |
| refresh_sessions | Rotating opaque credentials | unique SHA-256 token hash, family and user indexes, revocation/rotation timestamps |

UUID primary keys originate on the server. Timestamps use PostgreSQL `TIMESTAMPTZ` and UTC. Account/date indexes support stable descending transfer history. ORM balance updates and ledger writes share the same transaction.

A deferred constraint trigger checks that every inserted transfer has exactly one matching debit and one matching credit at commit. A second trigger validates each ledger insert. Triggers reject UPDATE and DELETE of committed transfers/ledger entries. Tests demonstrate missing-entry rollback and immutability. Privileged database owners can bypass triggers; production would require separate migration/runtime roles and restricted grants.

`PROCESSING` claims are never committed independently. A worker crash causes PostgreSQL rollback rather than a stuck claim. Completed key records are retained indefinitely in this demo. Production retention must exceed all supported retry windows and preserve deduplication tombstones during archival.

Seed IDs:

| Owner | Account ID | Number | Initial balance |
|---|---|---|---|
| Alice | `00000000-0000-4000-8000-000000000001` | `DEMO-100001` | 5,000,000 VND |
| Bob | `00000000-0000-4000-8000-000000000002` | `DEMO-200001` | 3,000,000 VND |

Running seed again preserves existing users, accounts, passwords and balances. No balance-edit endpoint exists. Tests use guarded databases ending in `_test`; interactive `banking` is never truncated by tests.
