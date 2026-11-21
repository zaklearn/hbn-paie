"""S4 — endpoints de lecture pour l'interface : tableau de bord du mois, paie du mois, référentiels,
aperçu de régularité, service de la SPA à la racine."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app
from app.tresorerie.legacy import dates
from tests.test_api import ADMIN_PW, INPUTS, close_month, env, login, setup_employee  # noqa: F401


def _plan_and_declare(client, eid, year, month):
    client.post("/api/tresorerie/plans", json={"employee_id": eid, "valid_from": "2026-07", "s1": 2500, "cnss": 1500,
                                               "s2": 2500, "s3": 2000})
    return client.post("/api/tresorerie/declarer", json={"year": year, "month": month}).json()


def test_monthly_dashboard_totals_computed_server_side(env):  # noqa: F811
    _, client = env
    login(client)
    eid = setup_employee(client)
    today = dates.aujourdhui()
    _plan_and_declare(client, eid, today.year, today.month)
    first = client.get("/api/tresorerie/echeances", params={"employee_id": eid}).json()[0]
    client.post(f"/api/tresorerie/echeances/{first['id']}/payer", json={"version": first["version"]})
    d = client.get("/api/paie/tableau-de-bord-mois", params={"year": today.year, "month": today.month}).json()
    assert d["salaries_actifs"] == 1
    assert d["kpi"]["salaires_attendus"] == 7000 and d["kpi"]["salaires_verses"] == 2500
    assert d["kpi"]["salaires_reste"] == 4500 and d["kpi"]["cnss_du_mois"] == 1500
    assert d["kpi"]["bulletins"] == {"cloturee": 0, "calculee": 0, "brouillon": 0, "a_saisir": 1}
    row = d["rows"][0]
    assert [x["state"] for x in row["dots"]][1:] != [] and row["dots"][0]["state"].startswith("paye_")
    assert row["status"] == "a_saisir" and row["verse_salaire"] == 2500


def test_month_payroll_lists_active_employees_with_status(env):  # noqa: F811
    _, client = env
    login(client)
    eid = setup_employee(client)
    close_month(client, eid, 7)
    rows = client.get("/api/paie/mois", params={"year": 2026, "month": 7}).json()
    assert rows[0]["status"] == "cloturee" and rows[0]["net_a_payer"] == "7000"
    assert client.get("/api/paie/mois", params={"year": 2026, "month": 8}).json()[0]["status"] == "a_saisir"
    assert client.get("/api/paie/mois", params={"year": 2026, "month": 6}).json() == []    # embauche au 01/07


def test_referentiels_and_regularity_preview(env):  # noqa: F811
    _, client = env
    login(client)
    refs = client.get("/api/paie/referentiels").json()
    assert refs["situations_familiales"][0] == "Célibataire" and refs["modes_paiement"] == ["Virement", "Chèque", "Espèces"]
    eid = setup_employee(client)
    today = dates.aujourdhui()
    _plan_and_declare(client, eid, today.year, today.month)
    e = client.get("/api/tresorerie/echeances", params={"employee_id": eid}).json()[-1]   # 3e versement
    before = client.get(f"/api/tresorerie/echeances/{e['id']}").status_code
    r = client.get(f"/api/tresorerie/echeances/{e['id']}/regularite", params={"date_paiement": e["date_echeance"]}).json()
    assert r["statut"] == "Payé – à temps" and before in (404, 405)
    assert client.get("/api/tresorerie/echeances", params={"employee_id": eid}).json()[-1]["statut"] == "Non payé"


def test_spa_served_at_root_with_history_fallback(env, tmp_path, monkeypatch):  # noqa: F811
    db, _ = env
    (tmp_path / "index.html").write_text("<!doctype html><div id=app></div>", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    monkeypatch.setenv("PAIE_STATIC_DIR", str(tmp_path))
    get_settings.cache_clear()
    with TestClient(create_app(db), base_url="https://testserver") as client:
        assert "id=app" in client.get("/").text
        assert "id=app" in client.get("/paie?periode=2026-11").text           # route de la SPA
        assert client.get("/assets/app.js").text == "console.log(1)"
        assert client.get("/api/inconnu").status_code == 404
        assert client.get("/../../etc/passwd").status_code in (200, 404) and "root:" not in client.get("/../../etc/passwd").text
        assert client.get("/api/health").json()["status"] == "ok"
    get_settings.cache_clear()
