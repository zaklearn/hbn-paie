"""Configuration commune des tests HBN Paie (dev : hbn-paie-dev)."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _drop_test_databases():
    """Supprime les bases MySQL de test créées pendant le test (serveur de DEV éphémère)."""
    yield
    from tests.paie import mysql_db

    if not mysql_db.CREATED:
        return
    created, mysql_db.CREATED[:] = list(mysql_db.CREATED), []
    names = {d.name for d in created}
    for database in created:
        database.dispose()
    conn = mysql_db.admin_connection()
    try:
        with conn.cursor() as cur:
            for name in sorted(names):
                assert name.startswith(mysql_db.TEST_DB_PREFIX)
                cur.execute(f"DROP DATABASE IF EXISTS `{name}`")
    finally:
        conn.close()
