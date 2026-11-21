"""Fixtures des tests paie portés (S1).

Reprises à l'identique de ``tests/conftest.py`` de paie-bulletins@df7ff12 pour la partie
sans base de données (``ACTOR``, ``params``, ``ref_input``, ``money``). Les fixtures de base
(``db``, ``setup``, ``hired_january``, ``make_employee``) arrivent en S2 avec le stockage MySQL.
"""

from __future__ import annotations

from decimal import Decimal as D

import pytest

from app.paie.core.calculations.defaults import DEFAULT_PARAMETERS
from tests.paie.demo_reference import REFERENCE_INPUT

ACTOR = "test"


@pytest.fixture
def params():
    return DEFAULT_PARAMETERS


@pytest.fixture
def ref_input():
    """Saisie de septembre 2026 du classeur (Saisie!D21:D30)."""
    return REFERENCE_INPUT


def money(value: str) -> D:
    return D(value)
