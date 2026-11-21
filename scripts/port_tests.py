#!/usr/bin/env python3
"""Portage des tests d'origine de paie-bulletins vers backend/tests/paie/ (S1 / US-12, S2).

Règle (R0.3) : aucune valeur attendue ne change. Chaque fichier porté = original + table
d'imports commune + remplacements spécifiques listés ci-dessous (justifiés). Rien d'autre.
``tests/paie/test_port_fidelity.py`` inverse ces remplacements et compare octet pour octet.

Usage : python scripts/port_tests.py
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_TESTS = ROOT / "upstream/paie-bulletins@df7ff126fdbb3d3c0a509480507361eec6b2b842/tests"
DEST = ROOT / "backend/tests/paie"

# Appliqués EN PREMIER (inversés en dernier).
IMPORT_MAP: list[tuple[bytes, bytes]] = [
    (b"from src.repositories", b"from app.paie.repositories"),
    (b"from src.services", b"from app.paie.services"),
    (b"from src.", b"from app.paie.core."),
]

# Remplacements spécifiques : (ancien, nouveau, occurrences, justification).
SPECIFIC: dict[str, list[tuple[bytes, bytes, int, str]]] = {
    "conftest.py": [
        (b"from app.paie.repositories.db import Database",
         b"from tests.paie.mysql_db import Database  # portage MySQL : base de test neuve par chemin", 1,
         "fixture db : base MySQL 8.4 de test neuve au lieu d'un fichier SQLite"),
    ],
    "test_workflow.py": [
        (b"import sqlite3\n",
         b"from app.paie.repositories import db as sqlite3  # portage MySQL : sqlite3.IntegrityError -> db.IntegrityError\n", 1,
         "classe d'exception des violations d'intégrité (déclencheurs, UNIQUE)"),
        (b"from app.paie.repositories.db import Database",
         b"from tests.paie.mysql_db import Database  # portage MySQL : base de test neuve par chemin", 1,
         "Database(chemin) -> base MySQL de test (même chemin = même base, test de redémarrage)"),
    ],
    "test_services_misc.py": [
        (b"from app.paie.repositories.db import Database",
         b"from tests.paie.mysql_db import Database  # portage MySQL : base de test neuve par chemin", 1,
         "Database(chemin) -> base MySQL de test"),
        (b"from app.paie.services import auth, backup, demo, master_data, payroll, reporting",
         b"from app.paie.services import demo, master_data, payroll, reporting\n"
         b"from app.socle import auth\n"
         b"from tests.paie import backup_s5 as backup  # sauvegarde/restauration : portee en S5 (US-50)", 1,
         "auth.py est dans le socle ; backup.py (SQLite) est porté en S5 : ses 2 tests sont ignorés avec motif"),
    ],
}

FILES = [
    # S1
    "test_engine.py", "test_ecarts_pdf.py", "test_reference_excel.py", "test_non_regression.py",
    "golden_scenarios.py", "golden/results.json",
    # S2
    "conftest.py", "test_workflow.py", "test_services_misc.py", "test_pdf.py",
]


def _replace(data: bytes, old: bytes, new: bytes, count: int, where: str) -> bytes:
    found = data.count(old)
    if found != count:
        raise SystemExit(f"{where} : {old[:60]!r} trouvé {found} fois (attendu {count})")
    return data.replace(old, new)


def port(name: str, data: bytes) -> bytes:
    for old, new in IMPORT_MAP:
        data = data.replace(old, new)
    for old, new, count, _ in SPECIFIC.get(name, []):
        data = _replace(data, old, new, count, name)
    return data


def unport(name: str, data: bytes) -> bytes:
    for old, new, count, _ in reversed(SPECIFIC.get(name, [])):
        data = _replace(data, new, old, count, name)
    for old, new in reversed(IMPORT_MAP):
        data = data.replace(new, old)
    return data


def main() -> None:
    for name in FILES:
        src, dst = UPSTREAM_TESTS / name, DEST / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(port(name, src.read_bytes()))
        print(f"porté : {name}")


if __name__ == "__main__":
    main()
