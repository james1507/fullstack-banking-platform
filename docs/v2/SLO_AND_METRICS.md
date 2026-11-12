# SLO targets and instrumentation

No production deployment, production traffic, measured availability SLO or latency benchmark exists. Test timings in [TEST_REPORT.md](TEST_REPORT.md) are suite timings, not request-performance measurements.

| Signal | Current instrumentation | Target / interpretation |
|---|---|---|
| Request error/latency | Structured method, path, status, duration_ms and generated request_id; Compose logs | Future target: p95 interactive request <500ms under a declared local workload; unmeasured |
| API readiness | `/health/ready` checks DB connection + Alembic head; liveness separate | Must be ready before frontend/worker startup; no availability percentage claimed |
| Transfer integrity | Paired immutable ledger, account baseline reconciliation in restore/tests | No accepted imbalance; alert/reconciliation service pending |
| Occurrence queue | Due/available time, state, attempts, lease token/expiry, error code, correlation ID stored | Future target: due run starts within 5s on idle local stack; real E2E verifies eventual outcome within 25s, not p95 |
| Outbox/inbox | Durable event status, retry availability, dedupe and notification record | Future target: local delivery within 5s; no delivery-latency distribution measured |
| Worker logs | Job ID, table/stage, handled status; sanitized retry/unavailable codes | Relate ID to occurrence/event request ID in DB; no trace collector or worker heartbeat |

Use `docker compose logs --tail=100 backend worker` to inspect current logs. Do not log credentials, raw cookies, request bodies or SQL parameters. Completed-response replay links original saved result; HTTP request header still identifies each new attempt.

Prometheus/OpenTelemetry, metrics endpoint, alerting, queue dashboard, percentiles, production paging and load/performance reports are **not implemented**. They belong to M8/M10. Adding a chart or hardcoded zero would not establish observability.
