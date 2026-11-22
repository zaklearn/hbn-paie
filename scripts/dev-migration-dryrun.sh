#!/usr/bin/env bash
# Essai à blanc de la migration sur le MySQL 8.4 de DEV (hbn-paie-dev), à partir de COPIES des sources.
# Usage : scripts/dev-migration-dryrun.sh [--sources /chemin] [--matricule 0001]
set -euo pipefail
cd "$(dirname "$0")/.."
export PAIE_DEV_DB_ROOT_PASSWORD="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
COMPOSE=(docker compose -f docker-compose.dev.yml)
cleanup() { "${COMPOSE[@]}" down --remove-orphans >/dev/null 2>&1 || true; }
trap cleanup EXIT
"${COMPOSE[@]}" build -q test
EXTRA=()
if [[ " $* " == *" --sources "* ]]; then
  SRC="$(echo " $* " | sed -E 's/.* --sources ([^ ]+) .*/\1/')"
  EXTRA=(-v "$SRC:/sources:ro")
  set -- $(echo " $* " | sed -E "s# --sources [^ ]+ # --sources /sources #")
fi
docker compose -f docker-compose.dev.yml run --rm -T "${EXTRA[@]}" -v "$PWD/docs/sprints:/out" -e PYTHONPATH=/work/backend \
  -w /work/backend test python /work/scripts/dev_migration_dryrun.py --out /out/S5_MIGRATION_DRYRUN.md "$@"
