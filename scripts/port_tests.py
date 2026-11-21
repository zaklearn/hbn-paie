#!/usr/bin/env python3
"""Portage des tests d'origine de paie-bulletins vers backend/tests/paie/ (US-12, puis S2).

Règle (R0.3 / S1) : seuls les imports changent. Le portage applique uniquement la table
``IMPORT_MAP`` ; ``tests/paie/test_port_fidelity.py`` vérifie, en inversant cette table,
que chaque fichier porté est octet pour octet identique à l'original.

Usage : python scripts/port_tests.py   (réécrit les fichiers portés depuis upstream/)
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UPSTREAM_TESTS = ROOT / "upstream/paie-bulletins@df7ff126fdbb3d3c0a509480507361eec6b2b842/tests"
DEST = ROOT / "backend/tests/paie"

# Ordre significatif : le plus spécifique d'abord.
IMPORT_MAP: list[tuple[bytes, bytes]] = [
    # S1 : demo.py dépend de SQLite et des services (portés en S2) ; ses 3 constantes
    # sont reprises à l'identique dans tests/paie/demo_reference.py (contrôlé).
    (b"from src.services.demo import", b"from tests.paie.demo_reference import"),
    (b"from src.", b"from app.paie.core."),
]

# Fichiers portés en S1 (sans Streamlit ni SQLite).
S1_FILES = [
    "test_engine.py",
    "test_ecarts_pdf.py",
    "test_reference_excel.py",
    "test_non_regression.py",
    "golden_scenarios.py",
    "golden/results.json",
]


def port(data: bytes) -> bytes:
    for old, new in IMPORT_MAP:
        data = data.replace(old, new)
    return data


def unport(data: bytes) -> bytes:
    for old, new in reversed(IMPORT_MAP):
        data = data.replace(new, old)
    return data


def main() -> None:
    for name in S1_FILES:
        src = UPSTREAM_TESTS / name
        dst = DEST / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(port(src.read_bytes()))
        print(f"porté : {name}")


if __name__ == "__main__":
    main()
