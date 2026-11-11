#!/usr/bin/env sh
set -eu
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
docker compose run --rm --no-deps backend python /migration/python/runner.py > "$tmp/python.jsonl"
node --experimental-strip-types migration/typescript/runner.ts > "$tmp/typescript.jsonl"
diff -u "$tmp/python.jsonl" "$tmp/typescript.jsonl"
printf 'PASS: 36 shared validation results match byte for byte.\n'
