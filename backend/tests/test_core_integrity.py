"""R0.1 — test BLOQUANT : le noyau paie est identique au commit gelé paie-bulletins@df7ff12."""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("check_core_integrity", REPO / "scripts" / "check_core_integrity.py")
check_core_integrity = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_core_integrity)


def test_core_identical_to_frozen_upstream():
    errors = check_core_integrity.check(REPO)
    assert errors == [], "R0 — noyau modifié :\n" + "\n".join(errors)


def test_core_has_exactly_ten_frozen_files():
    expected = check_core_integrity._expected(REPO / check_core_integrity.CORE_DIR)
    assert sorted(expected) == sorted([
        "calculations/money.py", "calculations/engine.py", "calculations/cumuls.py",
        "calculations/defaults.py", "models/parameters.py", "models/payroll.py",
        "models/entities.py", "validation/validators.py", "pdf/bulletin.py", "formatting.py",
    ])


def test_core_imports():
    """Le noyau s'importe sous son nouveau préfixe (aucune dépendance hors noyau)."""
    from app.paie.core.calculations import cumuls, defaults, engine, money  # noqa: F401
    from app.paie.core.models import entities, parameters, payroll  # noqa: F401
    from app.paie.core.pdf import bulletin  # noqa: F401
    from app.paie.core.validation import validators  # noqa: F401
    from app.paie.core import formatting  # noqa: F401
