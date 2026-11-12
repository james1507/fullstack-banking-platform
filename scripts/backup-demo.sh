#!/usr/bin/env sh
set -eu
umask 077
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$root"
destination=${1:-"$root/backups/moneta-$(date -u +%Y%m%dT%H%M%SZ).dump"}
if [ -e "$destination" ]; then
  printf 'Refusing to overwrite backup: %s\n' "$destination" >&2
  exit 2
fi
mkdir -p "$(dirname -- "$destination")"
temporary=$(mktemp "$(dirname -- "$destination")/.moneta-backup.XXXXXX")
trap 'rm -f "$temporary"' EXIT HUP INT TERM
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$temporary"
ln "$temporary" "$destination"
printf 'Local demo backup saved: %s\n' "$destination"
