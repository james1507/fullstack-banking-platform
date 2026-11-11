.PHONY: up down migrate seed test-backend test-frontend test-e2e parity lint ci
up:
	docker compose up --build -d --wait

down:
	docker compose down

migrate:
	docker compose run --rm --no-deps backend alembic upgrade head

seed:
	docker compose run --rm --no-deps backend python -m app.seed

test-backend:
	./scripts/create-test-db.sh
	docker compose run --rm --no-deps -v "$(CURDIR)/backend:/app" backend sh -c 'DATABASE_URL="$${DATABASE_URL%/*}/banking_test" pytest --cov=app --cov-report=term-missing -q'

test-frontend:
	cd frontend && npm ci && npm test

test-e2e:
	./scripts/test-e2e.sh

parity:
	./scripts/check-parity.sh

lint:
	docker compose run --rm --no-deps -v "$(CURDIR)/backend:/app" backend sh -c 'ruff check --config pyproject.toml . /migration/python && ruff format --check --config pyproject.toml . /migration/python'
	cd frontend && npm run lint && npm run typecheck

ci: up
	$(MAKE) test-frontend
	$(MAKE) lint
	$(MAKE) test-backend
	$(MAKE) parity
	$(MAKE) test-e2e
