"""US-24 / US-25 — API REST : connexion, sessions, rôles (refus côté API), parcours paie complet."""

from __future__ import annotations

import hashlib
import io
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app
from app.paie.core.calculations.defaults import DEFAULT_PARAMETERS
from app.paie.core.calculations.engine import compute_payslip
from app.paie.services.demo import DEMO_COMPANY, DEMO_EMPLOYEE, REFERENCE_INPUT
from app.socle import users
from tests.paie.mysql_db import Database

ADMIN_PW = "admin-motdepasse-1"
USER_PW = "user-motdepasse-1"
INPUTS = {k: str(v) for k, v in REFERENCE_INPUT.to_dict().items()}
COMPANY = {k: getattr(DEMO_COMPANY, k) for k in ("raison_sociale", "adresse", "ville", "ice", "cnss_employeur",
                                                 "rc", "identifiant_fiscal")}


def employee_body(matricule="0001", **changes):
    data = {f: getattr(DEMO_EMPLOYEE, f) for f in (
        "matricule", "nom", "prenom", "date_naissance", "cin", "cnss", "situation_familiale",
        "nb_personnes_charge", "date_embauche", "fonction", "mode_paiement", "banque", "compte_bancaire")}
    data.update(matricule=matricule, **changes)
    return {k: v.isoformat() if isinstance(v, date) else v for k, v in data.items()}


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(users, "HASH_ITERATIONS", 1000)
    get_settings.cache_clear()
    db = Database(tmp_path / "api.db")
    db.migrate()
    users.create_user(db, "test", "admin", "Admin", users.ROLE_SUPERADMIN, ADMIN_PW)
    users.create_user(db, "test", "lecteur", "Lecteur", users.ROLE_USER, USER_PW)
    with TestClient(create_app(db), base_url="https://testserver") as client:
        yield db, client
    get_settings.cache_clear()


def login(client, username="admin", password=ADMIN_PW):
    r = client.post("/api/auth/connexion", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r


def setup_employee(client):
    assert client.put("/api/paie/entreprise", json=COMPANY).status_code == 200
    r = client.post("/api/paie/salaries", json=employee_body())
    assert r.status_code == 201, r.text
    return r.json()["employee"]["id"]


def close_month(client, employee_id, month):
    r = client.post("/api/paie/brouillons", json={"employee_id": employee_id, "year": 2026, "month": month,
                                                  "inputs": INPUTS})
    assert r.status_code == 200, r.text
    pid = r.json()["payslip"]["id"]
    assert client.post(f"/api/paie/paies/{pid}/calcul").status_code == 200
    r = client.post(f"/api/paie/paies/{pid}/cloture", json={"confirm_warnings": True})
    assert r.status_code == 200, r.text
    return r.json()


# --- Connexion et sessions ------------------------------------------------------------------

def test_health_with_database(env):
    _, client = env
    assert client.get("/api/health").json()["db"] == "ok"


def test_api_requires_session(env):
    _, client = env
    for path in ("/api/paie/salaries", "/api/paie/entreprise", "/api/auth/moi", "/api/paie/audit"):
        assert client.get(path).status_code == 401


def test_login_cookie_is_httponly_secure_strict(env):
    _, client = env
    header = login(client).headers["set-cookie"].lower()
    assert "httponly" in header and "secure" in header and "samesite=strict" in header


def test_wrong_password_and_inactive_account_rejected_with_same_message(env):
    db, client = env
    bad = client.post("/api/auth/connexion", json={"username": "admin", "password": "mauvais-mdp-123"})
    unknown = client.post("/api/auth/connexion", json={"username": "personne", "password": "x" * 12})
    assert bad.status_code == unknown.status_code == 401
    assert bad.json() == unknown.json()
    lecteur = [u for u in users.list_users(db) if u.username == "lecteur"][0]
    users.set_active(db, "test", lecteur.id, False)
    assert client.post("/api/auth/connexion", json={"username": "lecteur", "password": USER_PW}).status_code == 401


def test_logout_revokes_session_server_side(env):
    _, client = env
    login(client)
    token = client.cookies.get("hbn_paie_session")
    assert client.post("/api/auth/deconnexion").status_code == 200
    client.cookies.set("hbn_paie_session", token)       # rejouer l'ancien jeton
    assert client.get("/api/auth/moi").status_code == 401


def test_password_change_revokes_sessions(env):
    db, client = env
    login(client, "lecteur", USER_PW)
    lecteur = [u for u in users.list_users(db) if u.username == "lecteur"][0]
    users.set_password(db, "test", lecteur.id, "nouveau-motdepasse")
    assert client.get("/api/auth/moi").status_code == 401


def test_last_superadmin_cannot_be_disabled_or_demoted(env):
    db, client = env
    login(client)
    admin = [u for u in users.list_users(db) if u.username == "admin"][0]
    assert client.post(f"/api/socle/utilisateurs/{admin.id}/activation", json={"active": False}).status_code == 400
    assert client.post(f"/api/socle/utilisateurs/{admin.id}/role", json={"role": "user"}).status_code == 400


def test_superadmin_manages_users(env):
    _, client = env
    login(client)
    r = client.post("/api/socle/utilisateurs", json={"username": "compta", "display_name": "Compta",
                                                     "role": "user", "password": "compta-motdepasse"})
    assert r.status_code == 201 and r.json()["role"] == "user" and "password_hash" not in r.json()
    assert client.post("/api/socle/utilisateurs", json={"username": "compta", "role": "user",
                                                        "password": "compta-motdepasse"}).status_code == 400
    assert client.post("/api/socle/utilisateurs", json={"username": "court", "role": "user",
                                                        "password": "court"}).status_code == 400
    assert {u["username"] for u in client.get("/api/socle/utilisateurs").json()} == {"admin", "lecteur", "compta"}


# --- Rôles : le rôle « user » ne peut rien écrire (refus côté API) ----------------------------

WRITES = [
    ("put", "/api/paie/entreprise", COMPANY),
    ("post", "/api/paie/salaries", employee_body("0009")),
    ("put", "/api/paie/salaries/{eid}", employee_body()),
    ("post", "/api/paie/salaries/{eid}/activation", {"active": False}),
    ("post", "/api/paie/parametres", {"year": 2027, "month": 1, "parameters": {}, "comment": "x"}),
    ("post", "/api/paie/brouillons", {"employee_id": 0, "year": 2026, "month": 10, "inputs": INPUTS}),
    ("post", "/api/paie/paies/{pid}/calcul", None),
    ("post", "/api/paie/paies/{pid}/cloture", {"confirm_warnings": True}),
    ("post", "/api/paie/paies/{cid}/rectification", {"reason": "erreur de saisie"}),
    ("delete", "/api/paie/paies/{pid}", None),
    ("get", "/api/socle/utilisateurs", None),
    ("post", "/api/socle/utilisateurs", {"username": "x1x", "role": "user", "password": "x" * 12}),
]


@pytest.fixture
def seeded(env):
    db, client = env
    login(client)
    eid = setup_employee(client)
    closed = close_month(client, eid, 7)["payslip"]
    r = client.post("/api/paie/brouillons", json={"employee_id": eid, "year": 2026, "month": 8, "inputs": INPUTS})
    pid = r.json()["payslip"]["id"]
    client.post("/api/auth/deconnexion")
    return db, client, eid, pid, closed["id"]


@pytest.mark.parametrize("method, path, body", WRITES, ids=[f"{m} {p}" for m, p, _ in WRITES])
def test_user_role_cannot_write(seeded, method, path, body):
    db, client, eid, pid, cid = seeded
    login(client, "lecteur", USER_PW)
    before = len(client.get("/api/paie/audit").json())
    url = path.format(eid=eid, pid=pid, cid=cid)
    r = client.request(method.upper(), url, json=body) if body is not None else client.request(method.upper(), url)
    assert r.status_code == 403
    assert len(client.get("/api/paie/audit").json()) == before + 0


def test_user_role_reads_and_exports_with_masked_identifiers(seeded):
    _, client, eid, pid, cid = seeded
    login(client, "lecteur", USER_PW)
    emp = client.get(f"/api/paie/salaries/{eid}").json()
    assert emp["cin"] == "••••0000" and emp["compte_bancaire"].startswith("••••") and emp["date_naissance"] is None
    slip = client.get(f"/api/paie/paies/{cid}").json()
    assert slip["employee_snapshot"]["cin"] == "••••0000"
    assert client.get(f"/api/paie/paies/{cid}/bulletin").status_code == 200
    assert client.get("/api/paie/exports/livre-de-paie.csv", params={"year": 2026}).status_code == 200
    assert client.get("/api/paie/tableau-de-bord", params={"year": 2026}).status_code == 200


def test_superadmin_sees_identifiers(seeded):
    _, client, eid, _, _ = seeded
    login(client)
    assert client.get(f"/api/paie/salaries/{eid}").json()["cin"] == DEMO_EMPLOYEE.cin


# --- Parcours paie via l'API ---------------------------------------------------------------------

def test_full_cycle_amounts_are_decimal_strings_and_match_core(env):
    db, client = env
    login(client)
    eid = setup_employee(client)
    body = {"employee_id": eid, "year": 2026, "month": 7, "inputs": INPUTS}
    preview = client.post("/api/paie/apercu", json=body).json()
    expected = compute_payslip(REFERENCE_INPUT, DEFAULT_PARAMETERS, 0).to_dict()
    assert preview["result"] == expected                      # aperçu = noyau, chaîne par chaîne
    assert all(isinstance(v, str) for v in preview["result"].values())
    closed = close_month(client, eid, 7)
    assert closed["payslip"]["status"] == "cloturee"
    assert closed["payslip"]["result"] == expected
    pdf = client.get(f"/api/paie/paies/{closed['payslip']['id']}/bulletin")
    assert pdf.headers["content-type"] == "application/pdf"
    assert 'filename="bulletin_2026-07_0001.pdf"' in pdf.headers["content-disposition"]
    assert hashlib.sha256(pdf.content).hexdigest() == closed["document"]["sha256"]
    audit = client.get("/api/paie/audit").json()
    assert {"paie.cloture", "paie.calcul", "paie.brouillon.creation"} <= {a["action"] for a in audit}
    assert all(a["actor"] == "admin" for a in audit if a["action"].startswith("paie."))


def test_closure_without_confirmation_and_rectification(env):
    _, client = env
    login(client)
    eid = setup_employee(client)
    r = client.post("/api/paie/brouillons", json={"employee_id": eid, "year": 2026, "month": 8, "inputs": INPUTS})
    pid = r.json()["payslip"]["id"]
    client.post(f"/api/paie/paies/{pid}/calcul")
    checks = client.get(f"/api/paie/paies/{pid}/controles").json()["issues"]
    assert any(i["level"] == "avertissement" for i in checks)  # juillet manquant
    r = client.post(f"/api/paie/paies/{pid}/cloture", json={"confirm_warnings": False})
    assert r.status_code == 400 and "avertissements" in r.json()["detail"]
    assert client.post(f"/api/paie/paies/{pid}/cloture", json={"confirm_warnings": True}).status_code == 200
    r = client.post(f"/api/paie/paies/{pid}/rectification", json={"reason": "abc"})
    assert r.status_code == 400                                  # motif de 5 caractères minimum
    r = client.post(f"/api/paie/paies/{pid}/rectification", json={"reason": "correction de la prime"})
    assert r.status_code == 201 and r.json()["version"] == 2 and r.json()["replaces_id"] == pid
    assert client.delete(f"/api/paie/paies/{r.json()['id']}").status_code == 200


def test_validation_errors_return_issues(env):
    _, client = env
    login(client)
    r = client.post("/api/paie/salaries", json=employee_body(nom=""))
    assert r.status_code == 422 and r.json()["issues"]
    eid = setup_employee(client)
    bad = dict(INPUTS, salaire_base="1.5e3")
    r = client.post("/api/paie/apercu", json={"employee_id": eid, "year": 2026, "month": 7, "inputs": bad})
    assert r.status_code == 422                                  # pas de notation flottante


def test_parameter_versions_are_never_modified(env):
    _, client = env
    login(client)
    versions = client.get("/api/paie/parametres").json()
    assert len(versions) == 1 and versions[0]["valid_from"] == "2000-01"
    params = versions[0]["parameters"]
    r = client.post("/api/paie/parametres", json={"year": 2027, "month": 1, "parameters": params,
                                                  "label": "LF 2027", "comment": "Saisie du propriétaire"})
    assert r.status_code == 201
    r = client.post("/api/paie/parametres", json={"year": 2027, "month": 1, "parameters": params, "comment": "x"})
    assert r.status_code == 400
    assert [v["valid_from"] for v in client.get("/api/paie/parametres").json()] == ["2027-01", "2000-01"]


def test_exports_and_journal(env):
    _, client = env
    login(client)
    eid = setup_employee(client)
    for m in (7, 8, 9):
        close_month(client, eid, m)
    j = client.get("/api/paie/journal", params={"year": 2026}).json()
    assert len(j["journal"]) == 3 and j["journal"][0]["Net à payer"] == "7000.0"
    assert "CIN" not in j["journal"][0] and "Compte" not in str(j)
    csv = client.get("/api/paie/exports/livre-de-paie.csv", params={"year": 2026, "month": 9})
    assert 'filename="livre_de_paie_2026-09.csv"' in csv.headers["content-disposition"]
    xlsx = client.get("/api/paie/exports/recapitulatif.xlsx", params={"year": 2026})
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(xlsx.content))
    assert wb.sheetnames == ["Livre de paie", "Récap mensuel", "Récap annuel"]
    dash = client.get("/api/paie/tableau-de-bord", params={"year": 2026}).json()
    assert dash["mois_clotures"] == [7, 8, 9] and len(dash["dernieres_paies"]) == 3
