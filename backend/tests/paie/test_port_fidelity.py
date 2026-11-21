"""R0.3 — les tests portés sont identiques aux originaux, imports exceptés.

Inverse la table d'imports de ``scripts/port_tests.py`` et compare octet pour octet avec
``upstream/paie-bulletins@df7ff12/tests``. Vérifie aussi que les constantes de démonstration
et les fixtures reprises sont identiques à l'original. Ignoré si ``upstream/`` est absent
(image de production) ; toujours exécuté dans le dépôt.
"""

from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
UPSTREAM = REPO / "upstream/paie-bulletins@df7ff126fdbb3d3c0a509480507361eec6b2b842"
pytestmark = pytest.mark.skipif(not UPSTREAM.is_dir(), reason="upstream/ absent (hors dépôt)")

_spec = importlib.util.spec_from_file_location("port_tests", REPO / "scripts" / "port_tests.py")
port_tests = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(port_tests)
HERE = Path(__file__).parent


@pytest.mark.parametrize("name", port_tests.S1_FILES)
def test_ported_file_identical_except_imports(name):
    ported = (HERE / name).read_bytes()
    original = (UPSTREAM / "tests" / name).read_bytes()
    assert port_tests.unport(ported) == original


def _assignments(source: str, names: set[str]) -> dict[str, str]:
    tree = ast.parse(source)
    return {n.targets[0].id: ast.dump(n.value) for n in tree.body
            if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and n.targets[0].id in names}


def test_demo_constants_identical_to_original():
    names = {"DEMO_COMPANY", "DEMO_EMPLOYEE", "REFERENCE_INPUT"}
    ours = _assignments((HERE / "demo_reference.py").read_text(encoding="utf-8"), names)
    theirs = _assignments((UPSTREAM / "src/services/demo.py").read_text(encoding="utf-8"), names)
    assert set(ours) == names and ours == theirs


def _functions(source: str, names: set[str]) -> dict[str, str]:
    tree = ast.parse(source)
    out = {n.name: ast.dump(n) for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names}
    out.update(_assignments(source, names))
    return out


def test_fixtures_identical_to_original():
    names = {"params", "ref_input", "money", "ACTOR"}
    ours = _functions((HERE / "conftest.py").read_text(encoding="utf-8"), names)
    theirs = _functions((UPSTREAM / "tests/conftest.py").read_text(encoding="utf-8"), names)
    assert set(ours) == names and ours == theirs
