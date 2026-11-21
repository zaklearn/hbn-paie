"""Sauvegarde / restauration : portées en S5 (US-50). Le backup.py d'origine est propre à SQLite."""

from __future__ import annotations

import pytest

REASON = "Sauvegarde/restauration MySQL portée en S5 (US-50) : backup.py d'origine propre à SQLite"


def create_backup(*_args, **_kwargs):
    pytest.skip(REASON)


def restore_backup(*_args, **_kwargs):
    pytest.skip(REASON)


def list_backups(*_args, **_kwargs):
    pytest.skip(REASON)
