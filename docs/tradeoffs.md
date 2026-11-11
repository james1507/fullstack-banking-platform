# Tradeoffs and next steps

- **One synchronous service:** clear transaction ownership and easy row-lock auditing. Async/microservices would add coordination without improving this demo.
- **Materialized balances plus ledger:** fast reads, immutable audit entries, transactional updates. There are no opening-balance ledger entries; seed establishes balances directly. A production ledger would model opening balances and reconciliation explicitly.
- **READ COMMITTED:** PostgreSQL's unique insert contention plus subsequent statement visibility is sufficient for the claim algorithm. This implementation must be reviewed before changing transaction isolation.
- **One transaction for claims:** no recovery worker or leases. Failed processes leave no committed PROCESSING claim. Completed results never expire in this demo.
- **No automatic side-effect retries:** UI waits for explicit same-key retry on uncertain results. Reloading during an unresolved transfer loses its in-memory attempt; history should be checked before initiating a new transfer. Persisted cross-reload drafts would need an explicit recovery design.
- **Access tokens expire naturally:** logout revokes refresh family, but an issued access token remains valid for at most 15 minutes.
- **Conservative token-family revocation:** replay may force reauthentication after two tabs rotate the same cookie concurrently. Browser single-flight coordinates within one tab only.
- **No status filter:** all committed transfers are SUCCEEDED, so a status filter would offer no useful choice. Failed business attempts are saved as idempotency results, not successful history rows.
- **Simple interface:** dashboard, readable tables, server filters and pagination. No invented spending analytics or decorative data. Green/ivory palette uses original Moneta branding; no real-bank branding or remote assets.
- **Demo images:** backend image includes test tooling to let reviewers run checks without local Python. A production image should install runtime dependencies only and use separate migration/runtime DB credentials.
- **Local networking:** loopback-only ports, HTTP dev cookie, explicit localhost origins. Not a public deployment configuration.
- **Dependencies:** direct Python dependencies are pinned, frontend lock committed. Minimatch override uses the patched version required to remove a transitive development-tool advisory. Revisit override when typescript-eslint updates its dependency.
- **Future scope:** shared rate limits, least-privilege DB roles, TLS/secrets management, cross-tab and cross-reload retry recovery, monitoring, backups and retention policy. No real-money deployment is claimed.
