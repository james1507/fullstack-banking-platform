# ADR 003: Durable schedules, fenced claims and transactional inbox

Accepted 12 November 2026.

Use one additional process from the same Python image. PostgreSQL remains the coordinator; no queue service or new dependency. Compose starts worker only after API readiness/migrations.

Schedule creation has its own scoped idempotency claim and saved response, preventing an uncertain creation retry from installing two future payment plans. Browser freezes its original key/payload on unknown creation outcome. A schedule has one next occurrence. Its server-generated UUID is the durable occurrence identity and derives the internal key `schedule:<occurrence-id>`. Queue claims use `FOR UPDATE SKIP LOCKED`, a random lease token, 60-second lease and at most five attempts. An expired lease may be reclaimed; execution verifies the token under row lock, fencing the stale worker.

Execution locks schedule, then occurrence, then enters the existing transfer service with the worker-owned transaction. Actor role/activity, ownership, ordered account locks, balance and daily limits remain authoritative. Money, ledger, saved response, occurrence outcome, next occurrence, audit and outbox events commit together. This removes a separate posting/ack crash window. Tests also replay a separately committed original key to demonstrate safe recovery of a lost acknowledgment.

Transient database failures retry with bounded exponential backoff plus jitter. Business rejection is terminal for that occurrence; the next recurring slot remains eligible. Pausing/cancelling uses the schedule lock, fences claimed work and preserves history. Changes require a matching version. Editing replaces only future unclaimed slots. Closure checks the owner's active/paused linked schedules under the posting account lock. Another customer's incoming schedule cannot hold an account open; it fails normally if destination closes.

A one-time run or weekly/monthly series uses an explicit IANA zone and naive local wall time. First run must lie within the next 366 days; maximum 120 attempted terminal runs. Ambiguous DST time uses fold 0; nonexistent first local time is rejected; subsequent gap slots are skipped. Monthly dates clamp to the final day, retaining the original anchor (Jan 31 → Feb 28 → Mar 31). After downtime, execute the single existing overdue occurrence, then select the next future slot; never burst-post missed periods. Resume after pause cancels missed slots and selects the next future slot. Missed one-time plans complete without posting on resume.

Transfer events are inserted in the money transaction for involved owners, with a unique `(user_id, kind, entity_id)`. Schedule outcomes have their own event. Worker inserts inbox row with unique event ID and marks delivered in one transaction. Redelivery is safe; no external email/SMS call. Retry exhaustion becomes a dead letter. Notification preferences and operator requeue UI remain pending, explicitly tracked in the feature matrix.
