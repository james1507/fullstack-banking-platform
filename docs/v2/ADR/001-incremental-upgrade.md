# ADR 001: Preserve the V1 posting boundary

Accepted 12 November 2026.

Keep the synchronous modular monolith, existing files/routes, integer VND transport, immutable transfer facts and paired ledger. Add domain modules as needed without directory churn or new infrastructure.

New lifecycle operations lock the same account row as posting. A frozen source rejects new outgoing movement but may receive; closed accounts reject both directions. Idempotent replay precedes current policy checks so an already committed result remains stable after freeze/closure. Daily limits are UTC calendar-day limits, include own-account movement, and are evaluated under the locked source row.

Backfill opening balances as `current balance - credits + debits` when reporting is introduced, preserving historical seed funding without manufacturing new transfers. No generic balance setter.

Roles are stored server-side, default CUSTOMER for existing users. OPERATIONS can freeze/unfreeze with a reason; AUDITOR reads audit only. Customer writes cannot assign roles. Explicit synthetic operator/auditor seeds have no funded accounts.

New response metadata is additive; historical saved transfer JSON is never rewritten. New resource inputs forbid unknown fields. Live readiness follows Alembic head rather than a hardcoded V1 revision. Prefer forward fixes; do not downgrade financial history.

Scheduling/outbox will use one worker and PostgreSQL, only after core policy is verified. No Kafka/Redis/microservices or new client state framework is required.
