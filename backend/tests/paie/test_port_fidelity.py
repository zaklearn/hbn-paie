"""R0.3 / US-23 — tests et sources portés identiques aux originaux, écarts listés exceptés.

Inverse les tables de ``scripts/port_tests.py`` et ``scripts/port_sources.py`` et compare octet
pour octet avec ``upstream/paie-bulletins@df7ff12``. Ignoré si ``upstream/`` est absent (image de
production) ; toujours exécuté dans le dépôt.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
UPSTREAM = REPO / "upstream/paie-bulletins@df7ff126fdbb3d3c0a509480507361eec6b2b842"
pytestmark = pytest.mark.skipif(not UPSTREAM.is_dir(), reason="upstream/ absent (hors dépôt)")


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


port_tests = _load("port_tests")
port_sources = _load("port_sources")
HERE = Path(__file__).parent


@pytest.mark.parametrize("name", port_tests.FILES)
def test_ported_test_identical_except_listed_changes(name):
    ported = (HERE / name).read_bytes()
    original = (UPSTREAM / "tests" / name).read_bytes()
    assert port_tests.unport(name, ported) == original


@pytest.mark.parametrize("name", sorted(port_sources.TARGETS))
def test_ported_source_identical_except_listed_changes(name):
    ported = (REPO / "backend/app" / port_sources.TARGETS[name]).read_text(encoding="utf-8")
    original = (UPSTREAM / "src" / name).read_text(encoding="utf-8")
    assert port_sources.unport(name, ported) == original
