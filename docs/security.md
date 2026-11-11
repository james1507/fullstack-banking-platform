# Security model

Simulation only. Do not expose this demo to public traffic with bundled credentials or local secrets.

## Threats and controls

| Threat | Control | Evidence |
|---|---|---|
| Password disclosure | Argon2id; no password/token request bodies in logs | login tests, `security.py` |
| Forged or expired bearer | HS256 algorithm allowlist; required issuer/audience/expiry/subject/issued-at/JTI | missing/invalid/expired/wrong-claims/unsigned-token tests |
| Stolen refresh/reuse | high-entropy opaque token; only SHA-256 hash stored; rotate per refresh; revoke family on reuse | sequential and concurrent refresh-reuse tests |
| CSRF/login CSRF | HttpOnly, SameSite=Strict, auth-path cookie; exact Origin allowlist on login/refresh/logout | Origin rejection tests |
| Object-level access | account owner checks; transfer visible only to either account owner; 404 for invisible objects | Alice/Bob/Carol isolation tests |
| Double debit/races | unique idempotency claim and globally ordered PostgreSQL row locks | 24-way same-key, 12-way spend, 16-way opposite-direction tests |
| Partial writes | one DB transaction, immutable balanced ledger constraints | injected-failure and deferred-constraint tests |
| Unsafe number input | strict positive integer and JSON-safe upper bound; runtime web contracts | API boundary, shared parity and frontend tests |
| SQL injection | bound SQLAlchemy statements; escaped reference search | repository query implementation |
| Information leakage | safe DTOs, sanitized errors, generated request IDs | generic-error regression test |
| Brute-force sign-in | 10 attempts per source IP per 60 seconds | rate-limit test |
| Browser content injection | React escaping, no raw HTML rendering; Nginx CSP and frame denial | application source and Nginx configuration |

Cookie endpoints require an `Origin` header even for CLI/API clients. CORS is an additional browser control, not the CSRF boundary. Cross-origin access is restricted to configured exact origins. Never configure arbitrary origins from untrusted input.

Refresh operations serialize by a transaction-scoped advisory lock on family ID and a session row lock. Reuse revocation commits before returning rejection. Logout revokes the whole active family. Already issued bearer tokens expire naturally within 15 minutes; logout does not instantly revoke an issued access token.

## Scope and limits

Single API process for the demo. Rate limits are in memory, reset on restart, and do not coordinate across workers. Use a shared gateway limit before scaling. Cross-tab refresh coordination is not implemented; simultaneous restores in different tabs can trigger conservative family revocation and require sign-in again.

Local HTTP uses `COOKIE_SECURE=false` and loopback-only published ports. Public hosting requires TLS, unique managed secrets, Secure cookies, narrowly configured origins, separate least-privilege DB roles, dependency maintenance, security monitoring and operational recovery procedures. The Compose DB user owns the schema for reproducible local migrations.

`/docs` and `/openapi.json` are intentionally enabled locally. Set `DOCS_ENABLED=false` for restricted deployments. No actual banking integrations, PII collection, onboarding, registration, password-reset, MFA, compliance claims or production guarantees.
