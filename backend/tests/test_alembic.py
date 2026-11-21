"""US-13 — ``alembic upgrade head`` sur une base MySQL 8.4 vide (dev : hbn-paie-dev)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

BACKEND = Path(__file__).resolve().parents[1]
TEST_DB_URL = os.environ.get("PAIE_TEST_DB_URL", "")
pytestmark = pytest.mark.skipif(not TEST_DB_URL, reason="PAIE_TEST_DB_URL non défini (MySQL de test absent)")


def test_mysql_version_is_8_4():
    with create_engine(TEST_DB_URL).connect() as conn:
        assert conn.execute(text("SELECT VERSION()")).scalar().startswith("8.4.")


def test_alembic_upgrade_head_on_empty_database():
    engine = create_engine(TEST_DB_URL)
    assert inspect(engine).get_table_names() == [], "la base de test doit être vide"
    env = {**os.environ, "PAIE_DB_URL": TEST_DB_URL}
    run = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=BACKEND, env=env,
                         capture_output=True, text=True)
    assert run.returncode == 0, run.stderr[-2000:].replace(TEST_DB_URL, "***")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar() == "0003"
        assert conn.execute(text("SELECT MAX(version) FROM schema_version")).scalar() == 1
        triggers = conn.execute(text(
            "SELECT TRIGGER_NAME FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA = DATABASE()")).scalars().all()
    assert sorted(triggers) == sorted([
        "trg_parameter_sets_immutable", "trg_payslips_closed_immutable", "trg_payslips_closed_nodelete",
        "trg_documents_immutable", "trg_documents_nodelete", "trg_audit_append_only"])
    assert set(inspect(engine).get_table_names()) == {
        "alembic_version", "schema_version", "company", "employees", "parameter_sets", "payslips",
        "documents", "audit_log", "users", "sessions"}
