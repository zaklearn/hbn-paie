"""Sources de substitution pour les tests et l'essai à blanc (S5) — AUCUNE donnée réelle.

- paie-bulletins : base .db produite par l'APPLICATION D'ORIGINE (upstream/paie-bulletins@df7ff12, SQLite),
  exécutée telle quelle : démo fictive juillet–septembre 2026, rectification de septembre (v2 clôturée,
  v1 remplacée), second salarié fictif (juillet clôturé), brouillon d'octobre.
- ezzinecdi : data.json au format d'origine (9 champs) généré par db_gen d'origine, avec paiements,
  un doublon, un enregistrement hors schéma et une incohérence statut/date ; plus un backup_*.json.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
UPSTREAM_PAIE = REPO / "upstream/paie-bulletins@df7ff126fdbb3d3c0a509480507361eec6b2b842"

PAIE_SCRIPT = r"""
import sys
from dataclasses import replace
from datetime import date
from decimal import Decimal as D
sys.path.insert(0, ".")
from src.repositories.db import Database
from src.services import demo, master_data, payroll
db = Database(sys.argv[1]); db.migrate()
master_data.ensure_initial_parameters(db)
assert demo.seed_demo(db)
emp = master_data.list_employees(db)[0]
sept = [s for s in payroll.list_payslips(db) if s.month == 9][0]
new_id = payroll.open_rectification(db, "origine", sept.id, "Correction prime de panier")
payroll.save_draft(db, "origine", emp.id, 2026, 9, replace(demo.REFERENCE_INPUT, prime_panier=D("1000")))
payroll.calculate(db, "origine", new_id)
payroll.close(db, "origine", new_id, confirm_warnings=True)
other, _ = master_data.create_employee(db, "origine", replace(demo.DEMO_EMPLOYEE, id=None, matricule="0002",
    nom="EXEMPLE DEUX", cin="XX000002", cnss="000000002", nb_personnes_charge=2, date_embauche=date(2026, 7, 1)))
pid, _ = payroll.save_draft(db, "origine", other, 2026, 7, replace(demo.REFERENCE_INPUT, salaire_base=D("8000")))
payroll.calculate(db, "origine", pid)
payroll.close(db, "origine", pid, confirm_warnings=True)
payroll.save_draft(db, "origine", emp.id, 2026, 10, demo.REFERENCE_INPUT)
print("ok")
"""


def make_paie_db(directory: Path) -> Path:
    target = Path(directory) / "paie_bulletins_sauvegarde.db"
    run = subprocess.run([sys.executable, "-c", PAIE_SCRIPT, str(target)], cwd=UPSTREAM_PAIE, capture_output=True,
                         text=True, timeout=300, env={"PATH": "/usr/local/bin:/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"})
    if run.returncode != 0:
        raise RuntimeError(run.stderr[-2000:])
    return target


def make_ezzinecdi(directory: Path) -> tuple[Path, Path]:
    from app.tresorerie.legacy import db_gen

    data = db_gen.base_vide()
    for year, month in ((2026, 7), (2026, 8), (2026, 9), (2026, 10), (2026, 11)):
        data, _, _ = db_gen.ajouter_mois(data, year, month)
    for rec in data:
        if rec["date_echeance"] < "2026-10-01":
            rec["statut"], rec["date_paiement"] = "Payé – à temps", rec["date_echeance"]
            rec["observations"] = f"Payé le {rec['date_echeance'][8:10]}/{rec['date_echeance'][5:7]}/2026 (à temps)"
    oct_s1 = next(r for r in data if r["mois"] == "Octobre 2026" and r["type"] == db_gen.T_S1)
    oct_s1.update(statut="Payé – retard", date_paiement="2026-10-15", observations="Payé le 15/10/2026 (retard)")
    backup = json.loads(json.dumps(data))
    # Anomalies d'origine possibles : doublon (le payé prime), hors schéma, incohérence statut/date.
    dup = dict(next(r for r in data if r["mois"] == "Novembre 2026" and r["type"] == db_gen.T_CN))
    dup.update(statut="Payé – à temps", date_paiement="2026-11-09")
    data.append(dup)
    data.append({"foo": "bar"})
    nov_s2 = next(r for r in data if r["mois"] == "Novembre 2026" and r["type"] == db_gen.T_S2)
    nov_s2["date_paiement"] = "2026-11-19"                       # « Non payé » avec une date : incohérent
    d = Path(directory)
    (d / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "backup_20261101.json").write_text(json.dumps(backup[:-4], ensure_ascii=False), encoding="utf-8")
    return d / "data.json", d / "backup_20261101.json"
