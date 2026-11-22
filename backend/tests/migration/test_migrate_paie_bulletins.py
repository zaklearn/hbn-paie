"""US-51 / US-53 — migration paie-bulletins : recopie à l'identique, R0.3 en lecture seule, refus des cibles non vides."""

from __future__ import annotations

import json
import shutil
import sqlite3

import pytest

from app.migration import paie_bulletins as mig
from app.paie.repositories.db import IntegrityError
from app.paie.services import master_data, payroll
from app.paie.services.errors import PayrollError
from app.socle import users
from tests.migration.sources import UPSTREAM_PAIE, make_paie_db
from tests.paie.mysql_db import Database

pytestmark = pytest.mark.skipif(not UPSTREAM_PAIE.is_dir(), reason="upstream/ absent (hors dépôt)")


@pytest.fixture(scope="module")
def source_db(tmp_path_factory):
    return make_paie_db(tmp_path_factory.mktemp("sources"))


@pytest.fixture
def target(tmp_path):
    db = Database(tmp_path / "cible.db")
    db.migrate()
    return db


def _counts(db):
    conn = db.connect()
    try:
        return {t: conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"] for t in mig.SOURCE_TABLES}
    finally:
        conn.close()


def test_source_read_only_and_checks(source_db):
    sha = mig.sha256_file(source_db)
    src = mig.read_source(source_db)
    assert {t: len(r) for t, r in src.tables.items()}["payslips"] == 6     # 3 + v2 + 0002 + brouillon
    assert mig.sha256_file(source_db) == sha
    r0 = mig.recalc_check(src)
    assert r0["paies_verifiees"] == 5 and r0["ecarts"] == []                # 4 clôturées + 1 remplacée
    assert mig.pdf_check(src)["empreintes_differentes"] == []


def test_dry_run_writes_nothing_and_is_replayable(source_db, target):
    before = _counts(target)
    first = mig.run(source_db, target, dry_run=True)
    second = mig.run(source_db, target, dry_run=True)
    assert _counts(target) == before
    assert json.dumps(first, default=str, sort_keys=True) == json.dumps(second, default=str, sort_keys=True)
    sept = next(m for m in first["totaux_par_mois"] if m["periode"] == "2026-09")
    assert sept["statuts"] == {"cloturee": 1, "remplacee": 1}


def test_import_copies_exactly_and_keeps_protections(source_db, target):
    report = mig.run(source_db, target, dry_run=False)
    assert report["ecarts_cible_source"] == {} and report["protections_verifiees"]
    assert report["r0_recalcul"]["ecarts"] == []
    src = mig.read_source(source_db)
    for row in src.tables["payslips"]:                                       # services portés lisent les données
        slip = payroll.get_payslip(target, row["id"])
        assert slip.status == row["status"] and slip.replaces_id == row["replaces_id"]
        if row["result"]:
            assert json.dumps(slip.result.to_dict()) == row["result"]
    for doc in src.tables["documents"]:
        assert payroll.get_document(target, doc["payslip_id"]).content == bytes(doc["content"])
    conn = target.connect()
    try:
        with pytest.raises(IntegrityError):
            conn.execute("UPDATE payslips SET inputs = '{}' WHERE status = 'cloturee'")
    finally:
        conn.close()
    with pytest.raises(PayrollError, match="non vide"):                       # rejouer sur la même cible : refus
        mig.run(source_db, target, dry_run=False)


def test_bootstrap_target_is_accepted(source_db, target):
    """Cible déjà démarrée par l'application (paramètres initiaux, superadmin) : version initiale remplacée."""
    master_data.ensure_initial_parameters(target)
    users.create_user(target, "cli", "admin", "Admin", users.ROLE_SUPERADMIN, "motdepasse-solide")
    report = mig.run(source_db, target, dry_run=False)
    assert report["import"]["version_initiale_remplacee"] and report["import"]["journal_renumerote"]
    assert report["ecarts_cible_source"] == {}
    assert [ps.valid_from for ps in master_data.list_parameter_sets(target)] == ["2000-01"]


def test_target_with_business_data_is_refused(source_db, target):
    master_data.ensure_initial_parameters(target)
    from dataclasses import replace

    from app.paie.services.demo import DEMO_EMPLOYEE
    master_data.create_employee(target, "x", replace(DEMO_EMPLOYEE, id=None))
    with pytest.raises(PayrollError, match="non vide"):
        mig.run(source_db, target, dry_run=False)


def test_altered_source_is_refused(source_db, tmp_path):
    altered = tmp_path / "altere.db"
    shutil.copy(source_db, altered)
    conn = sqlite3.connect(altered)
    conn.execute("DROP TRIGGER trg_documents_nodelete")
    conn.commit(); conn.close()
    with pytest.raises(PayrollError, match="protections"):
        mig.read_source(altered)
    with pytest.raises(PayrollError, match="valide"):
        (tmp_path / "x.db").write_bytes(b"pas une base")
        mig.read_source(tmp_path / "x.db")


def test_recalc_gap_is_reported_never_corrected(source_db):
    src = mig.read_source(source_db)
    slip = next(s for s in src.tables["payslips"] if s["status"] == "cloturee")
    tampered = json.loads(slip["result"]); tampered["net_a_payer"] = "6999"
    slip["result"] = json.dumps(tampered)
    gaps = mig.recalc_check(src)["ecarts"]
    assert gaps == [{"payslip_id": slip["id"], "periode": f"{slip['year']}-{slip['month']:02d}",
                     "version": slip["version"], "champs": ["net_a_payer"]}]
    assert json.loads(slip["result"])["net_a_payer"] == "6999"               # rien n'est corrigé
