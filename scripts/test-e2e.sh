#!/usr/bin/env sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
compose() { docker compose -p moneta-e2e -f "$root/docker-compose.yml" -f "$root/docker-compose.e2e.yml" "$@"; }
cleanup() {
  status=$?
  if [ "$status" -ne 0 ]; then
    mkdir -p "$root/frontend/test-results"
    compose logs --no-color > "$root/frontend/test-results/stack.log" 2>&1 || true
  fi
  compose down -v > /dev/null 2>&1 || true
  exit "$status"
}
trap cleanup EXIT
# This named project and volume contain only disposable E2E data.
compose down -v > /dev/null 2>&1 || true
compose up --build -d --wait
cd "$root/frontend"
BASE_URL=http://localhost:5174 npm run test:e2e
