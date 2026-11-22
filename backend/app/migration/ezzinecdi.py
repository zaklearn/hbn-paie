"""Migration ezzinecdi (data.json) -> échéances d'un salarié (S5 / US-52, US-53).

- Rattachement : toutes les échéances au salarié du ``--matricule`` (déjà présent dans la cible).
- Plan v1 : montants des 4 types sur le PREMIER mois des données, ``valid_from`` = ce mois (vérifié).
- Import à l'identique : les 9 champs d'origine sont recopiés tels quels ; ``n`` d'origine conservé dans
  ``source_ref`` ; numérotation par salarié recalculée par ``db_gen.trier_renumeroter`` d'origine.
- Réconciliation d'origine en SIMULATION (montant au plan) : toute correction qu'elle ferait est listée,
  jamais appliquée. Ne sont pas importés (et sont listés) : les enregistrements hors schéma, le doublon
  écarté par la règle d'origine (le payé prime), et une incohérence statut/date de paiement que la base refuse.
- Les ``backup_*.json`` sont seulement comparés au ``data.json`` (écarts signalés).
- ``dry_run`` : aucune écriture.
"""

from __future__ import annotations

import copy
import datetime as dt
import json
from pathlib import Path

from app.paie.repositories import repos
from app.paie.repositories.db import Database
from app.paie.services.errors import PayrollError
from app.tresorerie.legacy import db_gen, integrity
from app.tresorerie.services import echeancier
from app.tresorerie.services.echeancier import PaymentPlan
from app.tresorerie.services.reconciliation import FIELDS, simulate

from app.migration.paie_bulletins import sha256_file

ACTOR = "migration"


def load(path: Path) -> list:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PayrollError(f"{Path(path).name} : JSON illisible.") from exc
    if not isinstance(data, list):
        raise PayrollError(f"{Path(path).name} : une liste d'enregistrements est attendue.")
    return data


def first_month_plan(records: list) -> tuple[str, dict[str, int]]:
    """Plan v1 : montants des 4 types sur le premier mois des données (enregistrements valides)."""
    valid = [r for r in records if integrity._schema_ok(r)]
    if not valid:
        raise PayrollError("Aucun enregistrement valide : impossible de déduire le plan v1.")
    first = min(r["date_echeance"][:7] for r in valid)
    amounts: dict[str, set[int]] = {}
    for r in valid:
        if r["date_echeance"][:7] == first:
            amounts.setdefault(r["type"], set()).add(int(r["montant"]))
    if set(amounts) != set(echeancier.PLAN_FIELD) or any(len(v) != 1 for v in amounts.values()):
        raise PayrollError(f"Premier mois ({first}) incomplet ou ambigu : plan v1 à saisir par le propriétaire.")
    return first, {echeancier.PLAN_FIELD[t]: next(iter(v)) for t, v in amounts.items()}


def _plan(valid_from: str, amounts: dict[str, int]) -> PaymentPlan:
    return PaymentPlan(0, 0, valid_from, amounts["s1"], amounts["cnss"], amounts["s2"], amounts["s3"], "", "", "")


def analyse(records: list, valid_from: str, amounts: dict[str, int], today: dt.date) -> dict:
    """Classe chaque enregistrement : importé tel quel, ou non importé (motif) ; corrections proposées."""
    plan = _plan(valid_from, amounts)

    def expected(type_: str, date_: dt.date) -> int:
        if date_.isoformat()[:7] < valid_from:
            raise LookupError("échéance antérieure au plan v1")
        return plan.montant(type_)

    sim = simulate(records, expected, today)
    rejected, kept, dropped_dupes = [], [], []
    by_key: dict[tuple[str, str], int] = {}
    for i, rec in enumerate(records):
        if not integrity._schema_ok(rec):
            rejected.append({"index": i, "motif": "hors schéma", "extrait": str(rec)[:80]})
            continue
        key = db_gen.cle(rec)
        if key in by_key:                                       # règle d'origine : le payé prime
            j = by_key[key]
            if integrity.est_paye(rec) and not integrity.est_paye(records[j]):
                dropped_dupes.append({"index": j, "motif": "doublon (le payé prime)", "cle": list(key)})
                kept.remove(j)
                kept.append(i)
                by_key[key] = i
            else:
                dropped_dupes.append({"index": i, "motif": "doublon (le payé prime)", "cle": list(key)})
            continue
        by_key[key] = i
        kept.append(i)
    importable, incoherent = [], []
    for i in sorted(kept):
        rec = records[i]
        if integrity.est_paye(rec) != bool(rec.get("date_paiement")):
            incoherent.append({"index": i, "motif": "incohérence statut / date de paiement", "cle": list(db_gen.cle(rec)),
                               "statut": rec["statut"], "date_paiement": rec.get("date_paiement")})
        else:
            importable.append(i)
    return {"simulation": {"compte_rendu": sim["compte_rendu"], "corrections": sim["corrections"]},
            "importables": importable, "rejetes": rejected, "doublons_ecartes": dropped_dupes,
            "incoherences": incoherent}


def compare_backups(records: list, backups: list[Path]) -> list[dict]:
    """Comparaison simple de chaque backup_*.json au data.json (clé mois + type)."""
    def index(recs):
        return {db_gen.cle(r): r for r in recs if isinstance(r, dict) and "mois" in r and "type" in r}

    main = index(records)
    out = []
    for path in sorted(backups):
        other = index(load(path))
        differing = sorted(k for k in set(main) & set(other)
                           if any(main[k].get(f) != other[k].get(f) for f in FIELDS))
        out.append({"fichier": Path(path).name, "sha256": sha256_file(path), "enregistrements": len(other),
                    "seulement_dans_data_json": len(set(main) - set(other)),
                    "seulement_dans_backup": len(set(other) - set(main)),
                    "differents": [list(k) for k in differing]})
    return out


def run(source: Path, matricule: str, db: Database | None, dry_run: bool, backups: list[Path] | None = None,
        today: dt.date | None = None) -> dict:
    today = today or dt.date.today()
    sha = sha256_file(source)
    records = load(source)
    valid_from, amounts = first_month_plan(records)
    result = analyse(records, valid_from, amounts, today)
    report = {"source": {"fichier": Path(source).name, "sha256": sha, "enregistrements": len(records)},
              "matricule": matricule, "plan_v1": {"valid_from": valid_from, **amounts}, "dry_run": dry_run,
              **result, "sauvegardes_comparees": compare_backups(records, backups or [])}
    if db is not None:
        with db.read() as conn:
            emp = conn.execute("SELECT id FROM employees WHERE matricule = ?", (matricule,)).fetchone()
            if emp is None:
                raise PayrollError(f"Matricule {matricule} absent de la cible : importer d'abord paie-bulletins.")
            existing = conn.execute("SELECT (SELECT COUNT(*) FROM echeances WHERE employee_id = ?) + "
                                    "(SELECT COUNT(*) FROM payment_plans WHERE employee_id = ?) AS n",
                                    (emp["id"], emp["id"])).fetchone()["n"]
        if existing:
            raise PayrollError(f"Cible refusée : le salarié {matricule} a déjà des échéances ou un plan.")
        report["employee_id"] = emp["id"]
        if not dry_run:
            _import(db, emp["id"], records, result["importables"], valid_from, amounts)
            report["ecarts_cible_source"] = _compare(db, emp["id"], records, result["importables"])
    if sha256_file(source) != sha:
        raise PayrollError("La source a été modifiée pendant la migration.")
    return report


def _import(db: Database, employee_id: int, records: list, indexes: list[int], valid_from: str,
            amounts: dict[str, int]) -> None:
    ts = repos.now_iso()
    with db.transaction() as conn:
        repos.lock_employee(conn, employee_id)
        conn.execute("INSERT INTO payment_plans (employee_id, valid_from, s1, cnss, s2, s3, comment, created_at, created_by) "
                     "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (employee_id, valid_from, amounts["s1"], amounts["cnss"], amounts["s2"], amounts["s3"],
                      "Plan v1 repris d'ezzinecdi (montants du premier mois)", ts, ACTOR))
        for i in indexes:
            r = copy.deepcopy(records[i])
            d = dt.date.fromisoformat(r["date_echeance"])
            conn.execute(
                "INSERT INTO echeances (employee_id, n, date_echeance, mois, type, montant, statut, rappel_j1, observations, "
                "date_paiement, annee, mois_num, version, source_ref, created_at, updated_at) "
                "VALUES (?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)",
                (employee_id, r["date_echeance"], r["mois"], r["type"], int(r["montant"]), r["statut"], r["rappel_j1"],
                 r["observations"] or "", r["date_paiement"], d.year, d.month, str(r.get("n", "")), ts, ts))
        echeancier._renumber(conn, employee_id)
        repos.log(conn, ACTOR, "migration.ezzinecdi", "employee", employee_id,
                  {"echeances": len(indexes), "plan_v1": valid_from})


def _compare(db: Database, employee_id: int, records: list, indexes: list[int]) -> dict:
    rows = {e.source_ref: e for e in echeancier.list_echeances(db, employee_id=employee_id)}
    diffs = []
    for i in indexes:
        r = records[i]
        e = rows.get(str(r.get("n", "")))
        if e is None or any((getattr(e, f) if f != "observations" else e.observations) != (r[f] if f != "observations" else r[f] or "")
                            for f in FIELDS):
            diffs.append(r.get("n"))
    return {"importees": len(rows), "attendues": len(indexes), "differentes": diffs}
