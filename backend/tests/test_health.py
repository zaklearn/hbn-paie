from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_health_ok():
    client = TestClient(create_app())
    assert client.get("/health").status_code == 200
    assert client.get("/health").json() == {"status": "ok"}


def test_api_health_reports_db_state():
    body = TestClient(create_app()).get("/api/health").json()
    assert body["status"] == "ok"
    assert body["db"] in {"ok", "non_configuree", "injoignable", "erreur"}
