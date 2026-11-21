"""Commandes d'administration HBN Paie.

Création du premier superadmin (mot de passe saisi au clavier, jamais par défaut ni en argument) :

    PAIE_DB_URL=… python -m app.socle.cli create-superadmin --username zak --name "Zakaria"
"""

from __future__ import annotations

import argparse
import getpass
import sys

from app.core.config import get_settings
from app.paie.repositories.db import Database
from app.paie.services.errors import PayrollError
from app.socle import users


def _database() -> Database:
    url = get_settings().db_url
    if url is None:
        raise SystemExit("PAIE_DB_URL n'est pas défini.")
    return Database(url.get_secret_value())


def create_superadmin(username: str, name: str) -> int:
    password = getpass.getpass("Mot de passe (10 caractères minimum) : ")
    if password != getpass.getpass("Confirmez le mot de passe : "):
        print("Les mots de passe ne correspondent pas.", file=sys.stderr)
        return 1
    try:
        user_id = users.create_user(_database(), "cli", username, name, users.ROLE_SUPERADMIN, password)
    except PayrollError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Superadmin créé (id {user_id}).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.socle.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("create-superadmin", help="créer un compte superadmin")
    p.add_argument("--username", required=True)
    p.add_argument("--name", default="")
    args = parser.parse_args(argv)
    if args.command == "create-superadmin":
        return create_superadmin(args.username, args.name)
    return 2


if __name__ == "__main__":
    sys.exit(main())
