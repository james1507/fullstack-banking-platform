# Challenge B: stale credentials and broken object authorization

Symptoms: a stolen rotated refresh cookie continues to work, or changing an account ID reveals another user's balance.

Unsafe historical pattern: validate only that a bearer token exists, then run `db.get(Account, supplied_id)`. This authenticates a caller but does not authorize the object.

Fix: verify signed token issuer/audience/expiry and active user; scope every account query by owner; scope transfer reads to either account owner. Refresh tokens rotate and reuse revokes the entire family under a PostgreSQL advisory lock. Revocation commits before returning 401.

Regression: `make test-backend` covers invalid/expired/unsigned tokens, sequential and concurrent refresh reuse, logout, expiry, Origin rejection and Alice/Bob/Carol resource isolation. `make test-frontend` covers protected-route redirection, restoration and session expiry. `docs/security.md` records access-token expiry and cross-tab tradeoffs.
