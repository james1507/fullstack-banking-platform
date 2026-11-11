#!/usr/bin/env sh
set -eu
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = '\''banking_test'\''" | grep -q 1 || createdb -U "$POSTGRES_USER" banking_test'
