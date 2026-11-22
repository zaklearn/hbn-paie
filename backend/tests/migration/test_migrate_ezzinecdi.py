"""US-52 — migration ezzinecdi : rattachement, plan v1, import à l'identique, simulation, anomalies listées."""

from __future__ import annotations

import datetime as dt
import json

import pytest

from app.migration import ezzinecdi as mig
from app.migration import paie_bulletins as pb
from app.paie.services.errors import PayrollError
from app.tresorerie.legacy import db_gen
from app.tresorerie.services import echeancier
from tests.migration.sources import UPSTREAM_PAIE, make_ezzinecdi, make_paie_db
from tests.paie.mysql_db import Database

pytestmark = pytest.mark.skipif(not UPSTREAM_PAIE.is_dir(), reason="upstream/ absent (hors dépôt)")
TODAY = dt.date(2026, 11, 21)


@pytest.fixture(scope="module")
def sources(tmp_path_factory):
    d = tmp_path_factory.mktemp("sources")
    data, backup = make_ezzinecdi(d)
    return make_paie_db(d), data, backup


@pytest.fixture
def target(tmp_path, sources):
    db = Database(tmp_path / "cible.db")
    db.migrate()
    pb.run(sources[0], db, dry_run=False)
    return db


def test_plan_v1_from_first_month(sources):
    _, data, _ = sources
    assert mig.first_month_plan(mig.load(data)) == ("2026-07", {"s1": 2500, "cnss": 1500, "s2": 2500, "s3": 2000})


def test_dry_run_lists_anomalies_and_writes_nothing(sources, target):
    _, data, backup = sources
    before = echeancier.list_echeances(target)
    report = mig.run(data, "0001", target, dry_run=True, backups=[backup], today=TODAY)
    assert echeancier.list_echeances(target) == before == []
    assert len(report["importables"]) == 19                 # 20 enregistrements d'origine − 1 incohérence
    assert [r["motif"] for r in report["rejetes"]] == ["hors schéma"]
    assert [d["motif"] for d in report["doublons_ecartes"]] == ["doublon (le payé prime)"]
    assert report["incoherences"][0]["cle"] == ["Novembre 2026", db_gen.T_S2]
    sim = report["simulation"]["compte_rendu"]
    assert (sim["rejetes"], sim["doublons"], sim["statuts_corriges"]) == (1, 1, 1)
    assert report["sauvegardes_comparees"][0]["seulement_dans_data_json"] == 4   # novembre absent du backup
    again = mig.run(data, "0001", target, dry_run=True, backups=[backup], today=TODAY)
    assert json.dumps(again, sort_keys=True, default=str) == json.dumps(report, sort_keys=True, default=str)


def test_import_copies_records_as_is(sources, target):
    _, data, _ = sources
    sha = pb.sha256_file(data)
    report = mig.run(data, "0001", target, dry_run=False, today=TODAY)
    assert report["ecarts_cible_source"]["differentes"] == [] and report["ecarts_cible_source"]["importees"] == 19
    emp = report["employee_id"]
    plans = echeancier.list_plans(target, emp)
    assert [(p.valid_from, p.s1, p.cnss, p.s2, p.s3) for p in plans] == [("2026-07", 2500, 1500, 2500, 2000)]
    rows = echeancier.list_echeances(target, employee_id=emp)
    assert [e.n for e in rows] == list(range(1, 20))
    paid_dup = next(e for e in rows if e.mois == "Novembre 2026" and e.type == db_gen.T_CN)
    assert paid_dup.statut == "Payé – à temps"                # le payé prime
    oct_s1 = next(e for e in rows if e.mois == "Octobre 2026" and e.type == db_gen.T_S1)
    assert (oct_s1.statut, oct_s1.date_paiement, oct_s1.observations) == ("Payé – retard", "2026-10-15",
                                                                          "Payé le 15/10/2026 (retard)")
    assert pb.sha256_file(data) == sha
    with pytest.raises(PayrollError, match="déjà des échéances"):
        mig.run(data, "0001", target, dry_run=False, today=TODAY)


def test_unknown_matricule_refused(sources, target):
    _, data, _ = sources
    with pytest.raises(PayrollError, match="absent de la cible"):
        mig.run(data, "9999", target, dry_run=True, today=TODAY)
