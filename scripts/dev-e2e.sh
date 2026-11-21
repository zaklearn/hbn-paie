#!/usr/bin/env bash
# HBN Paie — e2e de DEV : construit la SPA, démarre MySQL 8.4 + API (projet hbn-paie-dev, réseau interne),
# initialise une base de démo fictive, lance Playwright (Chromium) puis arrête tout.
# Mots de passe aléatoires, éphémères, jamais affichés. Captures : docs/sprints/S4_captures/.
set -euo pipefail
cd "$(dirname "$0")/.."
rnd() { head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n'; }
export PAIE_DEV_DB_ROOT_PASSWORD="$(rnd)" E2E_ADMIN_PW="a-$(rnd)" E2E_USER_PW="u-$(rnd)"
COMPOSE=(docker compose -f docker-compose.dev.yml --profile e2e)
cleanup() { "${COMPOSE[@]}" down --remove-orphans >/dev/null 2>&1 || true; }
trap cleanup EXIT
docker run --rm -m 1g -v "$PWD/frontend":/app -w /app node:20-alpine sh -c 'npx vue-tsc --noEmit && npx vite build' >/dev/null
mkdir -p docs/sprints/S4_captures
"${COMPOSE[@]}" build -q test
"${COMPOSE[@]}" up -d --wait mysql
"${COMPOSE[@]}" run --rm -T --no-deps -w /work/backend -e PYTHONPATH=/work/backend api python /work/scripts/e2e_seed.py
"${COMPOSE[@]}" up -d --wait api
"${COMPOSE[@]}" run --rm -T e2e "$@"
