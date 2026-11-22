"""US-50 — API Configuration › Sauvegardes : superadmin seulement, aller-retour, noms protégés."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app
from tests.test_api import USER_PW, close_month, env, login, setup_employee  # noqa: F401


@pytest.fixture
def api(env, tmp_path, monkeypatch):  # noqa: F811
    db, _ = env
    monkeypatch.setenv("PAIE_BACKUP_DIR", str(tmp_path / "sauvegardes"))
    get_settings.cache_clear()
    with TestClient(create_app(db), base_url="https://testserver") as client:
        yield db, client
    get_settings.cache_clear()


def test_backup_roundtrip_through_api(api):
    db, client = api
    login(client)
    eid = setup_employee(client)
    close_month(client, eid, 7)
    created = client.post("/api/socle/sauvegardes").json()
    assert [b["name"] for b in client.get("/api/socle/sauvegardes").json()] == [created["name"]]
    content = client.get(f"/api/socle/sauvegardes/{created['name']}").content
    client.post("/api/paie/salaries", json={"matricule": "0099", "nom": "X", "situation_familiale": "Célibataire",
                                            "mode_paiement": "Virement"})
    assert len(client.get("/api/paie/salaries").json()) == 2
    r = client.post("/api/socle/sauvegardes/restauration", content=content, headers={"Content-Type": "application/zip"})
    assert r.status_code == 200 and r.json()["safety"].endswith("_avant_restauration.zip")
    assert client.get("/api/auth/moi").status_code == 401            # sessions fermées par la restauration
    login(client)
    assert len(client.get("/api/paie/salaries").json()) == 1
    assert client.get("/api/paie/paies", params={"year": 2026}).json()[0]["status"] == "cloturee"


def test_invalid_file_rejected_and_names_protected(api):
    _, client = api
    login(client)
    r = client.post("/api/socle/sauvegardes/restauration", content=b"pas une sauvegarde")
    assert r.status_code == 400 and "valide" in r.json()["detail"]
    assert client.get("/api/socle/sauvegardes").json() == []          # aucune sauvegarde de sécurité créée
    for name in ("..%2F..%2Fetc%2Fpasswd", "paie_x.zip", "autre.zip"):
        assert client.get(f"/api/socle/sauvegardes/{name}").status_code == 404


def test_user_role_has_no_access_to_backups(api):
    _, client = api
    login(client, "lecteur", USER_PW)
    assert client.get("/api/socle/sauvegardes").status_code == 403
    assert client.post("/api/socle/sauvegardes").status_code == 403
    assert client.post("/api/socle/sauvegardes/restauration", content=b"x").status_code == 403
