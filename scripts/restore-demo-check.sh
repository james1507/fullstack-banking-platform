#!/usr/bin/env sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
archive=${1:?Usage: ./scripts/restore-demo-check.sh /absolute/path/to/moneta.dump}
test -r "$archive"
database="restore_$(date -u +%Y%m%d%H%M%S)_$$_test"
case "$database" in restore_*_test) ;; *) exit 2 ;; esac
docker compose exec -T db sh -c 'createdb -U "$POSTGRES_USER" "$1"' sh "$database"
cleanup() { docker compose exec -T db sh -c 'dropdb -U "$POSTGRES_USER" --if-exists "$1"' sh "$database"; }
trap cleanup EXIT
docker compose exec -T db sh -c 'pg_restore --exit-on-error --no-owner -U "$POSTGRES_USER" -d "$1"' sh "$database" < "$archive"
fingerprint() {
  docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$1" -At' sh "$database" <<'SQL'
SELECT md5(coalesce(string_agg(id::text || ':' || balance_vnd::text, ',' ORDER BY id),'')) FROM accounts;
SELECT count(*) FROM transfers;
SELECT count(*) FROM ledger_entries;
SQL
}
before=$(fingerprint)
docker compose run --rm --no-deps -v "$root/backend:/app:ro" -e RESTORE_DATABASE="$database" backend sh -c 'DATABASE_URL="${DATABASE_URL%/*}/$RESTORE_DATABASE" alembic upgrade head'
after=$(fingerprint)
if [ "$before" != "$after" ]; then
  printf 'FAIL: migration changed balances or posting counts in disposable restore.\n' >&2
  exit 1
fi
mismatches=$(docker compose exec -T db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$1" -At' sh "$database" <<'SQL'
SELECT count(*) FROM accounts a WHERE a.balance_vnd <> a.opening_balance_vnd + coalesce((
  SELECT sum(CASE WHEN direction='CREDIT' THEN amount_vnd ELSE -amount_vnd END)
  FROM ledger_entries WHERE account_id=a.id
),0);
SQL
)
test "$mismatches" = "0"
printf 'PASS: restored archive, upgraded schema, preserved balances/posting counts and reconciled baseline. Disposable DB will be removed.\n'
