#!/usr/bin/env bash
# HBN Paie — génère /opt/hbnfactory/platforms/paie/.env (0600) : secrets forts, JAMAIS affichés.
# Refuse d'écraser un .env existant. Usage : scripts/gen-env.sh <dossier> <PAIE_IMAGE> <DB_IMAGE>
set -euo pipefail
dir=${1:?dossier cible}; paie_image=${2:?image paie}; db_image=${3:?image mysql}
env_file="$dir/.env"
if [[ -e "$env_file" ]]; then echo "REFUS : $env_file existe déjà (aucune modification)." >&2; exit 1; fi
rnd() { head -c "$1" /dev/urandom | od -An -tx1 | tr -d ' \n'; }
umask 077
{
  echo "# HBN Paie — généré le $(date -u +%Y-%m-%dT%H:%M:%SZ) par scripts/gen-env.sh — NE PAS VERSIONNER"
  echo "PAIE_IMAGE=$paie_image"
  echo "DB_IMAGE=$db_image"
  echo "PAIE_ROUTE_ENABLED=false"
  echo "PAIE_BACKUP_RETENTION=0"
  echo "MYSQL_ROOT_PASSWORD=$(rnd 32)"
  echo "PAIE_DB_PASSWORD=$(rnd 32)"
  echo "PAIE_SECRET_KEY=$(rnd 48)"
} > "$env_file"
chmod 600 "$env_file"
echo "$env_file créé (0600) : $(grep -c '=' "$env_file") variables, valeurs non affichées."
