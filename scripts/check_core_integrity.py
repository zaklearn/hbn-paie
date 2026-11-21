#!/usr/bin/env python3
"""Contrôle d'intégrité du noyau paie gelé (R0.1) — BLOQUANT.

Pour chaque fichier listé dans ``backend/app/paie/core/UPSTREAM.sha256`` :
1. lit la copie de ``backend/app/paie/core/`` ;
2. normalise la seule modification autorisée (``from app.paie.core.`` -> ``from src.``) ;
3. compare le SHA-256 obtenu à celui du commit gelé paie-bulletins@df7ff12.

Échoue aussi si le noyau contient un fichier .py non listé (hors ``__init__.py`` vides
des sous-paquets), si un fichier listé manque, ou — quand ``upstream/`` est présent —
si ``UPSTREAM.sha256`` ne correspond plus aux sources gelées.

Usage : python scripts/check_core_integrity.py [--root <racine du dépôt>]
Code retour : 0 si conforme, 1 sinon.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ALLOWED_PREFIX = b"from app.paie.core."
UPSTREAM_PREFIX = b"from src."
UPSTREAM_DIR = "upstream/paie-bulletins@df7ff126fdbb3d3c0a509480507361eec6b2b842/src"
CORE_DIR = "backend/app/paie/core"
# __init__.py autorisés : celui du paquet core (docstring) et ceux des sous-paquets (vides, comme l'original)
EMPTY_INITS = {"calculations/__init__.py", "models/__init__.py", "validation/__init__.py", "pdf/__init__.py"}
ROOT_INIT = "__init__.py"


def _expected(core: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in (core / "UPSTREAM.sha256").read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        digest, name = line.split(maxsplit=1)
        out[name.strip()] = digest
    return out


def check(root: Path) -> list[str]:
    core = root / CORE_DIR
    errors: list[str] = []
    expected = _expected(core)
    if len(expected) != 10:
        errors.append(f"UPSTREAM.sha256 doit lister 10 fichiers, il en liste {len(expected)}")

    for name, digest in sorted(expected.items()):
        path = core / name
        if not path.is_file():
            errors.append(f"fichier manquant : {name}")
            continue
        normalized = path.read_bytes().replace(ALLOWED_PREFIX, UPSTREAM_PREFIX)
        actual = hashlib.sha256(normalized).hexdigest()
        if actual != digest:
            errors.append(f"MODIFIÉ : {name} (attendu {digest[:12]}…, obtenu {actual[:12]}…)")

    present = {p.relative_to(core).as_posix() for p in core.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    allowed = set(expected) | EMPTY_INITS | {ROOT_INIT, "UPSTREAM.sha256"}
    for extra in sorted(present - allowed):
        errors.append(f"fichier non autorisé dans le noyau : {extra}")
    for init in sorted(EMPTY_INITS):
        p = core / init
        if not p.is_file():
            errors.append(f"fichier manquant : {init}")
        elif p.read_bytes() != b"":
            errors.append(f"MODIFIÉ : {init} (doit rester vide, comme l'original)")

    upstream = root / UPSTREAM_DIR
    if upstream.is_dir():
        for name, digest in sorted(expected.items()):
            src = upstream / name
            if not src.is_file() or hashlib.sha256(src.read_bytes()).hexdigest() != digest:
                errors.append(f"UPSTREAM.sha256 ne correspond pas à {UPSTREAM_DIR}/{name}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args(argv)
    errors = check(args.root)
    if errors:
        print("R0 — INTÉGRITÉ DU NOYAU : ÉCHEC", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("R0 — intégrité du noyau OK (10 fichiers)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
