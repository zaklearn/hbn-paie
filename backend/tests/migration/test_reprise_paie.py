"""Reprise par reclôture (décision du 22/11/2026) : clôtures par la procédure d'origine, comparaison aux références."""

from __future__ import annotations

import pytest

from app.migration import paie_bulletins as pb
from app.migration import reprise_paie
from app.paie.services import payroll
from app.paie.services.errors import PayrollError
from tests.migration.sources import UPSTREAM_PAIE, make_paie_db
from tests.paie.mysql_db import Database

pytestmark = pytest.mark.skipif(not UPSTREAM_PAIE.is_dir(), reason="upstream/ absent (hors dépôt)")


@pytest.fixture
def imported(tmp_path):
    db = Database(tmp_path / "cible.db")
    db.migrate()
    pb.run(make_paie_db(tmp_path), db, dry_run=False)
    return db


def test_reclose_open_month_and_create_missing_one(imported, tmp_path):
    steps = reprise_paie.reclose(imported, "0001", 2026, [10, 11], {11: 9})
    assert [s["action"].split(",")[-1].strip() for s in steps] == ["clôturée", "clôturée"]
    assert steps[1]["action"].startswith("créée (saisie de 2026-09)")
    oct_slip = payroll.list_payslips(imported, year=2026, month=10)[0]
    assert oct_slip.status == "cloturee" and payroll.get_document(imported, oct_slip.id)
    # Référence = le bulletin d'origine de septembre v2 produit par l'application d'origine (même texte)
    sept = [s for s in payroll.list_payslips(imported, year=2026, month=9) if s.status == "cloturee"][0]
    ref = tmp_path / "bulletin_2026-09_0001.pdf"
    ref.write_bytes(payroll.get_document(imported, sept.id).content)
    assert reprise_paie.compare_with_references(imported, "0001", 2026, [ref])[0]["identique"] is True


def test_reclose_refuses_missing_month_without_designated_input(imported):
    with pytest.raises(PayrollError, match="aucune saisie désignée"):
        reprise_paie.reclose(imported, "0001", 2026, [12], {})
