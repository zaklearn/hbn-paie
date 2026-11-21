#!/usr/bin/env python3
"""Portage des dépôts et services de paie-bulletins vers backend/app (S2 / US-22, US-23, US-24).

Règle : logique IDENTIQUE. Chaque fichier porté = original + (1) table d'imports commune +
(2) remplacements spécifiques listés ci-dessous, chacun justifié (dialecte MySQL, verrou,
point d'extension). Rien d'autre. ``tests/paie/test_port_fidelity.py`` inverse ces
remplacements et vérifie l'égalité octet pour octet avec ``upstream/``.

Usage : python scripts/port_sources.py      (réécrit les fichiers portés depuis upstream/)
        python scripts/port_sources.py --table   (affiche la table des écarts, pour le rapport)
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_SRC = ROOT / "upstream/paie-bulletins@df7ff126fdbb3d3c0a509480507361eec6b2b842/src"
APP = ROOT / "backend/app"

# (1) Imports — appliqués EN PREMIER (et inversés en dernier).
IMPORT_MAP: list[tuple[str, str]] = [
    ("from src.repositories", "from app.paie.repositories"),
    ("from src.services", "from app.paie.services"),
    ("from src.", "from app.paie.core."),
]

LOCK_PAYSLIP = ("        repos.lock_payslip_employee(conn, payslip_id)  "
                "# portage MySQL : verrou salarié (remplace BEGIN IMMEDIATE)\n")

# (2) Remplacements spécifiques : (ancien, nouveau, nombre d'occurrences, justification).
SPECIFIC: dict[str, list[tuple[str, str, int, str]]] = {
    "repositories/repos.py": [
        ("traduction entre lignes SQLite et objets métier.",
         "traduction entre lignes MySQL et objets métier (portage HBN Paie).", 1,
         "docstring : moteur de base"),
        ("sqlite3.Connection", "Connection", 11, "annotation de type"),
        ("sqlite3.Row", "Row", 3, "annotation de type"),
        ("import sqlite3\n",
         "from app.paie.repositories.db import Connection, Row  # portage MySQL (au lieu de sqlite3)\n", 1,
         "types de connexion et de ligne de l'adaptateur MySQL"),
        ('updates = ", ".join(f"{f} = excluded.{f}" for f in COMPANY_FIELDS)',
         'updates = ", ".join(f"{f} = new.{f}" for f in COMPANY_FIELDS)', 1,
         "upsert : ON CONFLICT … excluded (SQLite) -> ON DUPLICATE KEY UPDATE … new (MySQL 8)"),
        ('f"VALUES (1, {placeholders}, ?) "\n'
         '        f"ON CONFLICT(id) DO UPDATE SET {updates}, updated_at = excluded.updated_at",',
         'f"VALUES (1, {placeholders}, ?) AS new "\n'
         '        f"ON DUPLICATE KEY UPDATE {updates}, updated_at = new.updated_at",', 1,
         "upsert : même effet (ligne unique id = 1)"),
        ('f"SELECT id FROM employees WHERE {field_name} = ? AND id IS NOT ?",',
         'f"SELECT id FROM employees WHERE {field_name} = ? AND NOT (id <=> ?)",', 1,
         "« IS NOT » de SQLite = inégalité sûre vis-à-vis de NULL : NOT (… <=> …)"),
        ('sql += " AND (matricule LIKE ? OR nom LIKE ? OR prenom LIKE ?)"',
         'sql += " AND (LOWER(matricule) LIKE LOWER(?) OR LOWER(nom) LIKE LOWER(?) OR LOWER(prenom) LIKE LOWER(?))"', 1,
         "LIKE insensible à la casse comme SQLite (colonnes en collation binaire)"),
        ('def delete_open_payslip(conn, payslip_id: int) -> None:\n'
         '    conn.execute("DELETE FROM payslips WHERE id = ? AND status IN (\'brouillon\', \'calculee\')",\n'
         '                 (payslip_id,))\n',
         'def delete_open_payslip(conn, payslip_id: int) -> None:\n'
         '    conn.execute("DELETE FROM payslips WHERE id = ? AND status IN (\'brouillon\', \'calculee\')",\n'
         '                 (payslip_id,))\n'
         '\n\n'
         'def lock_employee(conn, employee_id: int) -> None:\n'
         '    """Portage MySQL : verrou d\'écriture sur la ligne salarié (remplace BEGIN IMMEDIATE de SQLite).\n'
         '\n'
         '    Sérialise les opérations de paie d\'un même salarié (saisie, calcul, clôture, rectification).\n'
         '    """\n'
         '    conn.execute("SELECT id FROM employees WHERE id = ? FOR UPDATE", (employee_id,))\n'
         '\n\n'
         'def lock_payslip_employee(conn, payslip_id: int) -> None:\n'
         '    """Portage MySQL : même verrou, à partir d\'une paie (son salarié ne change jamais)."""\n'
         '    conn.execute("SELECT e.id FROM employees e JOIN payslips p ON p.employee_id = e.id "\n'
         '                 "WHERE p.id = ? FOR UPDATE OF e", (payslip_id,))\n', 1,
         "verrous FOR UPDATE (US-22) : remplacent BEGIN IMMEDIATE"),
    ],
    "services/master_data.py": [
        ("\"SELECT COUNT(*) AS n FROM payslips WHERE status = ? AND printf('%04d-%02d', year, month) >= ?\",",
         "\"SELECT COUNT(*) AS n FROM payslips WHERE status = ? \"\n"
         "            \"AND CONCAT(LPAD(year, 4, '0'), '-', LPAD(month, 2, '0')) >= ?\",", 1,
         "printf('%04d-%02d') (SQLite) -> CONCAT/LPAD (MySQL), même chaîne AAAA-MM"),
        ("\"AND printf('%04d-%02d', year, month) >= ?\", (*STATUTS_OUVERTS, period)).fetchone()[\"n\"]",
         "\"AND CONCAT(LPAD(year, 4, '0'), '-', LPAD(month, 2, '0')) >= ?\", "
         "(*STATUTS_OUVERTS, period)).fetchone()[\"n\"]", 1,
         "idem"),
    ],
    "services/payroll.py": [
        ('RECURRING_FIELDS = ("salaire_base", "jours_declares", "prime_panier", "indemnite_transport",\n'
         '                    "indemnite_representation", "conges_acquis")\n',
         'RECURRING_FIELDS = ("salaire_base", "jours_declares", "prime_panier", "indemnite_transport",\n'
         '                    "indemnite_representation", "conges_acquis")\n'
         '\n'
         '# Point d\'extension HBN Paie (S2, alimenté en S3 par le rapprochement trésorerie) : fonctions\n'
         '# (conn, paie) -> list[Issue]. Seuls les AVERTISSEMENTS sont retenus : jamais bloquants, ils ne\n'
         '# modifient ni le calcul, ni les données (R0.2). Vide par défaut.\n'
         'CLOSURE_WARNING_PROVIDERS: list = []\n', 1,
         "point d'extension unique de closure_checks (US-23)"),
        ('                            f"Cette clôture remplace la version précédente (motif : {slip.rectification_reason})."))\n'
         '    return issues\n',
         '                            f"Cette clôture remplace la version précédente (motif : {slip.rectification_reason})."))\n'
         '    for provider in CLOSURE_WARNING_PROVIDERS:  # point d\'extension HBN Paie (avertissements seuls)\n'
         '        issues += [i for i in provider(conn, slip) if i.level == AVERTISSEMENT]\n'
         '    return issues\n', 1,
         "appel du point d'extension (liste vide en S2 : comportement d'origine)"),
        ("    with db.transaction() as conn:\n"
         "        open_slip = repos.get_open_payslip(conn, employee_id, year, month)\n",
         "    with db.transaction() as conn:\n"
         "        repos.lock_employee(conn, employee_id)  # portage MySQL : verrou salarié (remplace BEGIN IMMEDIATE)\n"
         "        open_slip = repos.get_open_payslip(conn, employee_id, year, month)\n", 1,
         "save_draft : verrou salarié"),
        ("    with db.transaction() as conn:\n"
         "        slip = repos.get_payslip(conn, payslip_id)\n",
         "    with db.transaction() as conn:\n" + LOCK_PAYSLIP +
         "        slip = repos.get_payslip(conn, payslip_id)\n", 3,
         "calculate, open_rectification, delete_draft : verrou salarié"),
        ("    with db.transaction() as conn:\n"
         "        issues = _closure_checks(conn, payslip_id)\n",
         "    with db.transaction() as conn:\n" + LOCK_PAYSLIP +
         "        issues = _closure_checks(conn, payslip_id)\n", 1,
         "close : verrou salarié"),
    ],
    "services/reporting.py": [],
    "services/demo.py": [],
    "services/errors.py": [],
}

# Fichier d'origine -> fichier porté.
TARGETS = {
    "repositories/repos.py": "paie/repositories/repos.py",
    "services/errors.py": "paie/services/errors.py",
    "services/master_data.py": "paie/services/master_data.py",
    "services/payroll.py": "paie/services/payroll.py",
    "services/reporting.py": "paie/services/reporting.py",
    "services/demo.py": "paie/services/demo.py",
    "services/auth.py": "socle/auth.py",        # repris tel quel (aucun import src.)
}


def _replace(text: str, old: str, new: str, count: int, where: str) -> str:
    found = text.count(old)
    if found != count:
        raise SystemExit(f"{where} : « {old[:60]}… » trouvé {found} fois (attendu {count})")
    return text.replace(old, new)


def port(name: str, original: str) -> str:
    text = original
    for old, new in IMPORT_MAP:
        text = text.replace(old, new)
    for old, new, count, _ in SPECIFIC.get(name, []):
        text = _replace(text, old, new, count, name)
    return text


def unport(name: str, ported: str) -> str:
    text = ported
    for old, new, count, _ in reversed(SPECIFIC.get(name, [])):
        text = _replace(text, new, old, count, name)
    for old, new in reversed(IMPORT_MAP):
        text = text.replace(new, old)
    return text


def main(argv: list[str]) -> None:
    if "--table" in argv:
        for name, entries in SPECIFIC.items():
            for old, _new, count, why in entries:
                print(f"| `{name}` | {why} | {count} |")
        return
    for name, target in TARGETS.items():
        original = (UPSTREAM_SRC / name).read_text(encoding="utf-8")
        dest = APP / target
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(port(name, original), encoding="utf-8")
        print(f"porté : {name} -> backend/app/{target}")


if __name__ == "__main__":
    main(sys.argv[1:])
