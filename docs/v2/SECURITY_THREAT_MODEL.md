# V2 security threat model

Portfolio simulation with public synthetic accounts. No real money/PII/payment integration. Trust boundaries: untrusted browser and request inputs → authenticated FastAPI services → PostgreSQL; worker uses trusted stored plans but revalidates actor/ownership/policy through posting. Database owner and host administrator remain privileged.

| Threat | Control and actual evidence | Remaining limit |
|---|---|---|
| IDOR / tenant leakage | Owner predicates on accounts, beneficiaries, schedules, inbox, export and visible transfers; cross-user tests in each module | Operations audit deliberately sees safe global audit metadata |
| Role escalation / mass assignment | Role from DB; server guards; `extra=forbid`; staff cannot submit transfers; worker checks active CUSTOMER again | No role-management API or separate privileged DB identity |
| Concurrent double spending | Ordered account locks, deferred paired-ledger constraints, atomic result, process-level tests | Tests cover tested interleavings, not formal proof |
| Duplicate request / redelivery | Unique actor/operation/key + canonical hash; occurrence UUID identity; unique inbox event ID | Retention/archival not implemented; public transfer keys cannot use reserved colon syntax |
| Stale worker / cancellation race | Lease tokens fenced under occurrence lock; schedule actions share schedule lock; version checks | No operator requeue UI or heartbeat yet |
| Session theft / refresh replay | Memory bearer, HttpOnly SameSite=Strict cookie, hashed refresh, rotating family and advisory lock | Local HTTP cookie not Secure; bearer expiry after logout remains up to 15 minutes; cross-tab rotation may force login |
| CSRF | Exact Origin guard on cookie-auth endpoints; explicit CORS; other writes require bearer header | Public hosting needs TLS/Secure cookies, strict trusted proxy setup |
| XSS / CSV formula injection | React text escaping, Nginx CSP; export cells protected even with leading whitespace/control characters | No independent comprehensive accessibility/security certification |
| Account enumeration | Recipient preview masked, no email/profile; same unavailable error for unknown/closed saved destination | Recipient UUID lookup remains authenticated; process-local throttling needs shared gateway at scale |
| Resource exhaustion | Search/page/export bounds; login and recipient throttles; bounded worker claims/retries | Schedule creation/inbox polling have no shared deployment-wide quota; no load-tested capacity claim |
| Secret leakage | Safe DTOs, no submitted values in validation errors; request logs omit auth/body; sanitized DB errors and worker codes | Local DB backup is sensitive operational data even with fictional fixtures; excluded from Git |
| History tampering | Immutable transfer/ledger/audit/opening-baseline triggers; no balance edit route | Owner-level DB credentials can bypass triggers; production privilege separation pending |

Negative control: a temporary source copy removed the account-owner predicate. Existing isolation test returned 200 instead of expected 404 and failed as intended. Canonical source stayed unchanged; see [test report](TEST_REPORT.md). This establishes one test's sensitivity, not complete security coverage.

Security settings, password change/session listing/revocation, nonsecurity opt-out, dev incident UI and threat-driven load testing remain pending. No external messages are sent. Do not expose these public demo credentials as production authentication.
