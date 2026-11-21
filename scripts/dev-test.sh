#!/usr/bin/env bash
# HBN Paie — lance toute la suite de tests dans le projet compose de DEV « hbn-paie-dev »
# (Python 3.12 + MySQL 8.4 de test sur tmpfs), puis arrête l'environnement.
# Le mot de passe root du MySQL de test est aléatoire, éphémère et jamais affiché.
# Usage : scripts/dev-test.sh [arguments pytest]
set -euo pipefail
cd "$(dirname "$0")/.."
export PAIE_DEV_DB_ROOT_PASSWORD="$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
COMPOSE=(docker compose -f docker-compose.dev.yml)
cleanup() { "${COMPOSE[@]}" down --remove-orphans >/dev/null 2>&1 || true; }
trap cleanup EXIT
"${COMPOSE[@]}" build -q test
"${COMPOSE[@]}" run --rm -T test python -m pytest -q "$@"
