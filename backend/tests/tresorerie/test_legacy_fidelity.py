"""R1 — legacy ezzinecdi et ses tests : identiques à l'original, imports exceptés (octet pour octet)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
UPSTREAM = REPO / "upstream/ezzinecdi@85354c9c1f1d79d71d215f75dc8131186bafc054"
pytestmark = pytest.mark.skipif(not UPSTREAM.is_dir(), reason="upstream/ absent (hors dépôt)")

_spec = importlib.util.spec_from_file_location("port_tresorerie", REPO / "scripts" / "port_tresorerie.py")
port = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(port)


@pytest.mark.parametrize("name", port.SOURCES)
def test_legacy_source_identical(name):
    assert port.unport((REPO / "backend/app/tresorerie/legacy" / name).read_bytes()) == (UPSTREAM / name).read_bytes()


def test_legacy_tests_identical():
    ported = (Path(__file__).parent / "test_logic.py").read_bytes()
    assert port.unport(ported) == (UPSTREAM / "tests/test_logic.py").read_bytes()
