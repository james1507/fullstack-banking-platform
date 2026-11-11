# Testing and CI

## Prerequisites and lifecycle

Docker Compose 2.24.4+ is required for the E2E port overrides. Host Node 22.18+ supports the TypeScript parity runner without adding a transpiler dependency. No host Python is required for Make targets.

`make ci` starts the normal stack, installs frontend packages with `npm ci`, runs frontend tests, lint/typecheck, backend tests with coverage, cross-language parity, then builds/runs the isolated E2E stack. Install Chromium once with `cd frontend && npx playwright install chromium`.

`make test-backend` creates `banking_test` if missing. Pytest refuses database names without the `_test` suffix before destructive operations. It applies Alembic, truncates only test tables per case and reseeds synthetic users. No SQLite substitution, mocked row locks or sleeps are used.

`make test-e2e` creates a separate Compose project `moneta-e2e`, DB `banking_e2e_test`, independent volume and separate ports. Its cleanup removes only the named disposable test stack and volume. A fresh seed makes runs repeatable. Failure artifacts include Playwright traces/screenshots/report and Compose logs under `frontend/test-results`.

## Test evidence

- Backend tests exercise actual PostgreSQL transactions through FastAPI's HTTP test adapter. The barrier-synchronized workers execute separate requests and DB sessions concurrently.
- 24 same-key submissions must all return one transfer ID, one transfer effect and exactly two ledger entries.
- 12 different keys, each spending 1,000,000 VND, must produce five successes and seven insufficient-funds rejections from Alice's 5,000,000 VND.
- 16 opposite-direction transfers must complete without deadlock and preserve both balances.
- An injected exception during ledger insertion must roll back all financial writes and the key claim; retry must succeed.
- Two refresh requests using the same old token must yield one success and one reuse rejection; the newly issued token must then be revoked.
- Alice/Bob/Carol isolation proves existing unrelated objects remain inaccessible, rather than testing only unknown IDs.
- Vitest also verifies dropdown selection, disabled state, ARIA descriptions, keyboard/typeahead behavior, outside dismissal and tab navigation.
- Vitest covers form validation, duplicate-click guards, same-key network retry, centralized error mapping, runtime field contracts, coordinated refresh and auth route restoration/expiry.
- Playwright checks dropdown keyboard selection, Escape/outside dismissal, source account details and menu bounds on mobile.
- Playwright drives sign-in, invalid amount, reviewed transfer, receipt, updated balances, history, reload restoration, logout, API replay/conflict and mobile navigation.
- 36 fixtures are checked by both languages against expected values. Standalone runners also compare serialized output byte for byte.

Screenshots can be regenerated from the isolated real browser journey:

```bash
CAPTURE_DEMO=1 make test-e2e
```

They capture login, reviewed transfer, successful receipt, updated dashboard and mobile view. They are real application output, not a test-status badge.

## GitHub workflow

`quality` uses a PostgreSQL 16 service, Python 3.12 and Node 22. It runs Ruff, backend tests/coverage, npm CI install, ESLint/Prettier, TypeScript/build, Vitest and language parity.

`compose-and-e2e` validates Compose configuration, installs Chromium dependencies, builds native Linux images and runs the isolated browser stack. Jobs run on push to main, pull request and manual dispatch with read-only repository permissions. Failure reports upload as Actions artifacts. There are no deployment steps or embedded credentials beyond explicit test-only values.

Remote Actions execution is only possible after pushing. A valid local workflow file is not proof of a successful remote run. Local command results and unexecuted platform checks are recorded in `docs/implementation-report.md`.
