"""Definition of Done S2 — démonstration de septembre 2026 : bulletin clôturé identique à l'original.

L'original (upstream/paie-bulletins@df7ff12, SQLite) est exécuté tel quel dans un sous-processus ;
la version portée (MySQL) produit les mêmes données. On compare :
- le texte extrait de chaque page du PDF clôturé (pdfplumber) : identique ;
- le résultat, les cumuls et les copies figées : identiques chaîne par chaîne ;
- le nom de fichier du bulletin.
Les octets du PDF ne sont pas comparés : ReportLab y inscrit la date et l'heure de création.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pdfplumber
import pytest

from app.paie.services import demo, payroll
from tests.paie.mysql_db import Database

REPO = Path(__file__).resolve().parents[3]
UPSTREAM = REPO / "upstream/paie-bulletins@df7ff126fdbb3d3c0a509480507361eec6b2b842"
pytestmark = pytest.mark.skipif(not UPSTREAM.is_dir(), reason="upstream/ absent (hors dépôt)")

ORIGINAL_SCRIPT = r"""
import io, json, sys
import pdfplumber
sys.path.insert(0, ".")
from src.repositories.db import Database
from src.services import demo, payroll
db = Database(sys.argv[1]); db.migrate()
assert demo.seed_demo(db) is True
out = {}
for slip in payroll.list_payslips(db):
    doc = payroll.get_document(db, slip.id)
    with pdfplumber.open(io.BytesIO(doc.content)) as pdf:
        pages = [p.extract_text() for p in pdf.pages]
    out[str(slip.month)] = {"filename": doc.filename, "pages": pages, "result": slip.result.to_dict(),
                            "cumuls": slip.cumuls.to_dict(), "employee_snapshot": slip.employee_snapshot,
                            "company_snapshot": slip.company_snapshot, "parameters": slip.parameters.to_dict(),
                            "status": slip.status, "version": slip.version}
print(json.dumps(out, ensure_ascii=False))
"""


def _original(tmp_path) -> dict:
    run = subprocess.run([sys.executable, "-c", ORIGINAL_SCRIPT, str(tmp_path / "original.db")],
                         cwd=UPSTREAM, capture_output=True, text=True, timeout=300,
                         env={"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1",
                              "HOME": str(tmp_path)})
    assert run.returncode == 0, run.stderr[-3000:]
    return json.loads(run.stdout)


def _ported(tmp_path) -> dict:
    db = Database(tmp_path / "ported.db")
    db.migrate()
    assert demo.seed_demo(db) is True
    out = {}
    for slip in payroll.list_payslips(db):
        doc = payroll.get_document(db, slip.id)
        with pdfplumber.open(io.BytesIO(doc.content)) as pdf:
            pages = [p.extract_text() for p in pdf.pages]
        out[str(slip.month)] = {"filename": doc.filename, "pages": pages, "result": slip.result.to_dict(),
                                "cumuls": slip.cumuls.to_dict(), "employee_snapshot": slip.employee_snapshot,
                                "company_snapshot": slip.company_snapshot, "parameters": slip.parameters.to_dict(),
                                "status": slip.status, "version": slip.version}
    return out


def test_demo_bulletins_identical_to_original(tmp_path):
    original, ported = _original(tmp_path), _ported(tmp_path)
    assert sorted(original) == sorted(ported) == ["7", "8", "9"]
    for month in ("7", "8", "9"):
        o, p = original[month], ported[month]
        assert p["filename"] == o["filename"]
        assert p["result"] == o["result"] and p["cumuls"] == o["cumuls"]
        assert p["employee_snapshot"] == o["employee_snapshot"] and p["company_snapshot"] == o["company_snapshot"]
        assert p["parameters"] == o["parameters"]
        assert (p["status"], p["version"]) == (o["status"], o["version"])
        assert p["pages"] == o["pages"], f"texte du bulletin {month}/2026 différent"
    assert ported["9"]["filename"] == "bulletin_2026-09_0001.pdf"
    assert ported["9"]["cumuls"]["salaire_brut"] == "22099.53"
    text = "\n".join(ported["9"]["pages"])
    assert len(ported["9"]["pages"]) == 1 and "7 000,00" in text and "SOCIÉTÉ EXEMPLE SARL" in text
