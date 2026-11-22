"""Commandes de sauvegarde et de restauration de la base ``paie`` (S5 / US-50).

    python -m app.socle.backup_cli backup [--label manuelle]
    python -m app.socle.backup_cli list
    python -m app.socle.backup_cli validate FICHIER
    python -m app.socle.backup_cli restore FICHIER [--yes]

Connexion : ``PAIE_DB_URL`` ; dossier : ``PAIE_BACKUP_DIR`` ; rétention : ``PAIE_BACKUP_RETENTION``.
La restauration remplace TOUTE la base : elle demande une confirmation explicite (« RESTAURER ») sauf ``--yes``,
et crée d'abord une sauvegarde automatique de sécurité.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.core.config import get_settings
from app.paie.repositories.db import Database
from app.paie.services.errors import PayrollError
from app.socle import backup


def _db() -> Database:
    url = get_settings().db_url
    if url is None:
        raise SystemExit("PAIE_DB_URL n'est pas défini.")
    return Database(url.get_secret_value(), pooled=False)


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(prog="paie-backup")
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("backup")
    b.add_argument("--label", default="manuelle")
    sub.add_parser("list")
    v = sub.add_parser("validate")
    v.add_argument("file", type=Path)
    r = sub.add_parser("restore")
    r.add_argument("file", type=Path)
    r.add_argument("--yes", action="store_true", help="ne pas demander de confirmation")
    args = parser.parse_args(argv)
    directory = Path(settings.backup_dir)
    try:
        if args.cmd == "backup":
            path = backup.create_backup(_db(), directory, "cli", args.label, settings.backup_retention)
            print(f"Sauvegarde créée : {path}")
        elif args.cmd == "list":
            for path in backup.list_backups(directory):
                print(f"{path.name}\t{path.stat().st_size} octets")
        elif args.cmd == "validate":
            manifest = backup.validate_backup_file(args.file)
            counts = ", ".join(f"{t} {m['rows']}" for t, m in manifest["tables"].items())
            print(f"Sauvegarde valide (révision {manifest['alembic_revision']}) : {counts}")
        elif args.cmd == "restore":
            backup.validate_backup_file(args.file)
            if not args.yes and input("Remplacer TOUTE la base par cette sauvegarde ? Tapez RESTAURER : ") != "RESTAURER":
                print("Restauration annulée : aucune donnée modifiée.")
                return 2
            safety = backup.restore_backup(_db(), args.file.read_bytes(), directory, "cli")
            print(f"Base restaurée. Sauvegarde de sécurité : {safety}")
    except PayrollError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
