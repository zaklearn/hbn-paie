"""US-37 — API trésorerie : plans, déclaration, payer/dévalider (409 sur conflit), rôles, exports."""

from __future__ import annotations

import io

import pytest
from openpyxl import load_workbook

from app.tresorerie.legacy import dates, db_gen
from tests.test_api import USER_PW, employee_body, env, login, setup_employee  # noqa: F401 (fixture env)


@pytest.fixture
def treso(env):  # noqa: F811
    db, client = env
    login(client)
    eid = setup_employee(client)
    r = client.post("/api/tresorerie/plans", json={"employee_id": eid, "valid_from": "2026-07", "s1": 2500,
                                                   "cnss": 1500, "s2": 2500, "s3": 2000, "comment": "plan v1"})
    assert r.status_code == 201, r.text
    today = dates.aujourdhui()
    r = client.post("/api/tresorerie/declarer", json={"year": today.year, "month": today.month})
    assert r.status_code == 200, r.text
    return db, client, eid, today


def test_declare_and_list(treso):
    _, client, eid, today = treso
    rows = client.get("/api/tresorerie/echeances", params={"employee_id": eid}).json()
    assert [r["type"] for r in rows] == [db_gen.T_S1, db_gen.T_CN, db_gen.T_S2, db_gen.T_S3]
    assert [r["montant"] for r in rows] == [2500, 1500, 2500, 2000]
    assert all(r["statut"] == "Non payé" and r["version"] == 1 for r in rows)
    again = client.post("/api/tresorerie/declarer", json={"year": today.year, "month": today.month}).json()
    assert again["declares"] == [] and len(again["ignores"]) == 1
    assert client.get("/api/tresorerie/gabarit").json()[0] == {"jour": 10, "type": db_gen.T_S1, "ordre": 0, "plan": "s1"}


def test_pay_unpay_and_conflict(treso):
    _, client, eid, today = treso
    e = client.get("/api/tresorerie/echeances", params={"employee_id": eid}).json()[0]
    r = client.post(f"/api/tresorerie/echeances/{e['id']}/payer", json={"version": e["version"]})
    assert r.status_code == 200 and r.json()["statut"].startswith("Payé – ") and r.json()["version"] == 2
    assert r.json()["date_paiement"] == today.isoformat()
    stale = client.post(f"/api/tresorerie/echeances/{e['id']}/devalider", json={"version": 1})
    assert stale.status_code == 409 and "modifiée entre-temps" in stale.json()["detail"]
    ok = client.post(f"/api/tresorerie/echeances/{e['id']}/devalider", json={"version": 2})
    assert ok.status_code == 200 and ok.json()["statut"] == "Non payé" and ok.json()["date_paiement"] is None
    audit = {a["action"] for a in client.get("/api/paie/audit").json()}
    assert {"tresorerie.paiement", "tresorerie.devalidation", "tresorerie.declaration",
            "tresorerie.plan.creation"} <= audit


def test_user_role_reads_but_cannot_write(treso):
    _, client, eid, today = treso
    e = client.get("/api/tresorerie/echeances", params={"employee_id": eid}).json()[0]
    client.post("/api/auth/deconnexion")
    login(client, "lecteur", USER_PW)
    assert client.get("/api/tresorerie/a-venir").status_code == 200
    assert client.get("/api/tresorerie/recap", params={"employee_id": eid}).status_code == 200
    assert client.get("/api/tresorerie/exports/rappels_salaires_cnss.ics").status_code == 200
    for path, body in (("/api/tresorerie/plans", {"employee_id": eid, "valid_from": "2027-01", "s1": 1, "cnss": 1,
                                                  "s2": 1, "s3": 1}),
                       ("/api/tresorerie/declarer", {"year": today.year, "month": today.month}),
                       (f"/api/tresorerie/echeances/{e['id']}/payer", {"version": 1}),
                       (f"/api/tresorerie/echeances/{e['id']}/devalider", {"version": 1})):
        assert client.post(path, json=body).status_code == 403


def test_exports_have_original_names(treso):
    _, client, eid, _ = treso
    for name, media in (("recap_paiements.xlsx", "spreadsheetml"), ("base_complete.xlsx", "spreadsheetml"),
                        ("rappels_salaires_cnss.ics", "text/calendar")):
        r = client.get(f"/api/tresorerie/exports/{name}", params={"employee_id": eid})
        assert r.status_code == 200 and media in r.headers["content-type"]
        assert f'filename="{name}"' in r.headers["content-disposition"]
    ws = load_workbook(io.BytesIO(client.get("/api/tresorerie/exports/base_complete.xlsx").content)).active
    assert ws.max_row == 6                                    # en-tête + 4 échéances + TOTAL


def test_rapprochement_and_diagnostic(treso):
    _, client, eid, today = treso
    r = client.get("/api/tresorerie/rapprochement", params={"employee_id": eid, "year": today.year,
                                                            "month": today.month}).json()
    assert r["echeances_salaire"] == 3 and r["verse_salaire"] == "0" and r["bulletin"] is None
    diag = client.get("/api/tresorerie/reconciliation", params={"employee_id": eid}).json()
    assert diag["erreur"] is None and diag["corrections"] == [] and diag["compte_rendu"]["total"] == 4
