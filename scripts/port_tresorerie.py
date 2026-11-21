#!/usr/bin/env python3
"""Portage du legacy ezzinecdi@85354c9 vers backend/app/tresorerie/legacy/ et de ses tests (S3 / US-30).

Règle (R1) : logiques reprises à l'IDENTIQUE. Seule modification : les imports entre modules
(modules de premier niveau à l'origine -> paquet ``app.tresorerie.legacy``), inévitable pour
les intégrer au backend. ``tests/tresorerie/test_legacy_fidelity.py`` vérifie, en inversant la
table, l'égalité octet pour octet avec ``upstream/``.

Usage : python scripts/port_tresorerie.py
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM = ROOT / "upstream/ezzinecdi@85354c9c1f1d79d71d215f75dc8131186bafc054"
LEGACY = ROOT / "backend/app/tresorerie/legacy"
TESTS = ROOT / "backend/tests/tresorerie"

IMPORT_MAP: list[tuple[bytes, bytes]] = [
    (b"\nimport db_gen\n", b"\nfrom app.tresorerie.legacy import db_gen\n"),
    (b"\nimport integrity\n", b"\nfrom app.tresorerie.legacy import integrity\n"),
    (b"\nimport rapport\n", b"\nfrom app.tresorerie.legacy import rapport\n"),
]

SOURCES = ["dates.py", "db_gen.py", "integrity.py", "rapport.py"]
TEST_FILES = ["tests/test_logic.py"]


def port(data: bytes) -> bytes:
    for old, new in IMPORT_MAP:
        data = data.replace(old, new)
    return data


def unport(data: bytes) -> bytes:
    for old, new in reversed(IMPORT_MAP):
        data = data.replace(new, old)
    return data


def main() -> None:
    LEGACY.mkdir(parents=True, exist_ok=True)
    TESTS.mkdir(parents=True, exist_ok=True)
    for name in SOURCES:
        (LEGACY / name).write_bytes(port((UPSTREAM / name).read_bytes()))
        print(f"porté : {name}")
    for name in TEST_FILES:
        (TESTS / Path(name).name).write_bytes(port((UPSTREAM / name).read_bytes()))
        print(f"porté : {name}")


if __name__ == "__main__":
    main()
