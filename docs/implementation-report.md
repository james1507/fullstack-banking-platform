# Implementation report

> **V1 baseline document.** Preserved for historical context. The [V2 addendum](v2/TEST_REPORT.md) and [current feature matrix](v2/FEATURE_MATRIX.md) describe this branch’s implemented behavior and verification.

Verified locally on 11 November 2026. Source repository: `fullstack-banking-platform`. Product name: Moneta. Banking simulation only.

## Implementation summary

- React/TypeScript/Vite/Tailwind frontend with protected routing, responsive shell, sign-in, dashboard, accounts, reviewed transfer, receipt, history filters and server pagination.
- TanStack Query cache invalidation, React Hook Form/Zod validation, runtime response contracts and centralized HTTP errors.
- Memory-only access token, startup session restoration, single-flight refresh, preserved original request key/payload for unknown-outcome transfer retries.
- Python 3.12/FastAPI, synchronous SQLAlchemy/psycopg, PostgreSQL 16, versioned Alembic schema and repeatable Alice/Bob seeds.
- Argon2id, signed issuer/audience/expiry-checked tokens, hashed opaque refresh credentials, rotation, family reuse detection, logout and Origin guards.
- Ownership-scoped reads, atomic balances, deterministic account locks, exact response replay, saved business rejections and immutable balanced ledger triggers.
- Real database concurrency/failure-injection tests, UI component tests, Chromium E2E journeys and 36 shared language-migration fixtures.
- Compose for local use, disposable isolated E2E project, Make targets, GitHub Actions, screenshots captured from a real isolated run and reviewer documentation.

## Verified checks

| Command / check | Result | Evidence / scope |
|---|---|---|
| `docker compose config --quiet` | PASS | local Compose configuration resolves |
| `docker compose up --build -d --wait` | PASS | native ARM64 backend/frontend built; DB/API ready; SPA served |
| Alembic upgrade on empty PostgreSQL 16 | PASS | initial E2E volume starts empty each run |
| Seed twice | PASS | repeatable-seed integration case; preserves balances |
| `make test-backend` | PASS | 70 tests, actual PostgreSQL 16; measured application line coverage 96% |
| `npm test --prefix frontend` | PASS | 59 Vitest tests across five files, including 36 shared fixtures and seven dropdown regression cases |
| `make parity` | PASS | 36 expected results; canonical Python/TypeScript JSONL matches byte for byte |
| `make lint` | PASS | Ruff lint/format, ESLint, Prettier, strict TypeScript |
| `npm --prefix frontend run build` | PASS | production build; also built in Docker's Node 22 stage |
| `make test-e2e` | PASS | five Chromium journeys, including dropdown keyboard behavior, dismissal, source details and mobile bounds; real API/DB |
| `CAPTURE_DEMO=1 make ci` | PASS | initial delivery orchestration exits 0; dropdown refinement separately rechecked frontend lint/build/unit/E2E |
| `npm audit --prefix frontend` | PASS | zero reported dependency vulnerabilities at verification time |
| Workflow YAML parse / structural checks | PASS | Ruby YAML parser; expected jobs and executable steps present |
| `git diff --check` and repository hygiene checks | PASS | whitespace, local documentation/assets, ignored env/build/test artifacts |
| GitHub Actions remote execution | NOT RUN | repository has no remote; publication belongs to the user |
| Native Linux amd64 build/run | NOT RUN | specified in Actions; local execution was ARM64 only |
| Public deployment | NOT RUN | intentionally outside scope |

Frontend count includes its 36 shared-vector cases; backend count includes the same cases in Python. The standalone parity comparison is additional validation, not 36 additional UI journeys.

Critical observed behavior: a 150,000 VND transfer produces 4,850,000/3,150,000 VND balances on a fresh seed. Twenty-four same-key parallel requests produce one transfer. Twelve distinct 1,000,000 VND spends produce five successes/seven conflicts. Sixteen opposing transfers complete and preserve balances. Injected ledger failure rolls back money, transfer and idempotency claim. Existing unrelated transactions are hidden from Bob in a three-user authorization case. Concurrent refresh reuse revokes the new token family.

## Architecture and tradeoffs

One synchronous service keeps transaction ownership auditable. PostgreSQL owns uniqueness and locking across processes. A single transaction covers the claim, balances, ledger and stored result; crashes cannot leave a committed PROCESSING claim. Deferred constraints require two matching ledger entries at commit. Reads use ownership-scoped queries.

Frontend validates at the HTTP boundary and formats integer VND only for display. The UI freezes an uncertain transfer until same-key retry resolves it. Invalidations refresh authoritative server state. The pure language migration documents safe integers, boolean semantics, Unicode length and deterministic errors.

## Known limitations

- Local simulation, published demo credentials and local-only secrets. No production banking or compliance claim.
- Logout revokes refresh sessions; issued access tokens expire naturally within 15 minutes.
- Refresh coordination is per tab. Concurrent tab restores can force sign-in.
- Reloading an unresolved transfer loses its in-memory request draft; inspect history before creating another transfer.
- Login rate limits are per process. Demo DB role owns schema and runtime writes. Production needs shared limits and separated least-privilege roles.
- Completed idempotency results are retained indefinitely. Opening balances come from seed, without opening-balance ledger entries.
- Backend image includes test tooling for reviewer convenience. No public deployment, real-money integration, MFA or onboarding.
- GitHub workflow has been defined and parsed, but has not run remotely. No green CI badge was added.
- Upstream informational warnings observed: Starlette test-adapter deprecation, Vite removing Zod annotation comments. Checks still exit successfully.

## How to start / test locally

```bash
cp .env.example .env
docker compose up --build -d --wait
# Open http://localhost:5173
# alice@example.test / DemoPass123!

cd frontend
npm ci
npx playwright install chromium
cd ..
make ci
```

For publication, follow the personal Git identity, initial commit and push commands in the root README. No Git remote was added and no source was published externally. The repository is initialized on main; commit under your chosen personal identity before pushing. After pushing, inspect the actual Actions run and report its real status. Use `docs/demo-script.md` for the interviewer walkthrough.

## Dropdown refinement verification

All three native OS dropdowns were replaced with a shared styled, accessible combobox. Menus use white surfaces, selected/active states, a checkmark, account balance descriptions and consistent spacing. Keyboard behavior includes arrows, Home/End, Enter/Space, Escape, Tab and label typeahead. Portaled menus avoid container clipping, reposition on scroll/resize and fit the viewport. Transfer source selection remains connected to React Hook Form and is disabled during review/submission.

Verified commands: `npm test --prefix frontend` (59 passed), `npm run lint --prefix frontend`, `npm run build --prefix frontend`, `docker compose up -d --build --no-deps frontend` and `make test-e2e` (five passed). Existing backend checks were not repeated for this frontend-only change. In-app browser inspection confirmed direction, account filter and source-account menus. Actual captures: `screenshots/dropdown-filters.jpg` and `screenshots/dropdown-account.jpg`. No dependencies added.
