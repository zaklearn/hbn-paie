"""Migration paie-bulletins (.db SQLite) -> base ``paie`` MySQL (S5 / US-51, US-53).

R0 : la migration RECOPIE, elle ne recalcule pas. Paies (toutes versions et statuts), résultats, cumuls,
copies figées des paramètres, de la fiche salarié et de l'entreprise, PDF et empreintes, versions de
paramètres et journal sont importés octet pour octet, identifiants d'origine conservés (``replaces_id``).
Le noyau sert uniquement à VÉRIFIER : chaque paie clôturée ou remplacée est recalculée en lecture seule
et comparée chaîne par chaîne au résultat stocké ; un écart est signalé, jamais corrigé.

- Source ouverte en lecture seule (``mode=ro``) ; elle n'est jamais modifiée.
- Cible refusée si elle contient des données métier. Seules sont tolérées les lignes d'amorçage de
  l'application (version de paramètres initiale non référencée, comptes, journal de démarrage) : la
  version initiale est remplacée par celle de la source ; le journal de la source est alors ajouté
  à la suite (identifiants renumérotés, ordre et contenu conservés).
- Les déclencheurs d'immuabilité restent ACTIFS : l'import n'utilise que des INSERT (ils ne portent que
  sur UPDATE et DELETE). Les protections sont vérifiées après l'import.
- ``dry_run`` : lecture, contrôles et rapport, aucune écriture.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from app.paie.core.calculations.cumuls import compute_cumuls
from app.paie.core.calculations.engine import compute_payslip
from app.paie.core.models.parameters import PayrollParameters
from app.paie.core.models.payroll import MonthlyInput, PayslipResult
from app.paie.repositories.db import Database
from app.paie.services.errors import PayrollError

SOURCE_TABLES = ["company", "employees", "parameter_sets", "payslips", "documents", "audit_log"]
BUSINESS_TABLES = ["company", "employees", "payslips", "documents", "payment_plans", "echeances"]
EXPECTED_SOURCE_PROTECTIONS = {
    "trigger": {"trg_parameter_sets_immutable", "trg_payslips_closed_immutable", "trg_payslips_closed_nodelete",
                "trg_documents_immutable", "trg_documents_nodelete", "trg_audit_append_only"},
    "index": {"ux_employees_cin", "ux_employees_cnss", "ux_payslips_open", "ux_payslips_closed", "ix_payslips_period"},
}
BOOTSTRAP_AUDIT = {"parametres.initialisation", "utilisateur.creation", "connexion", "deconnexion",
                   "sauvegarde.creation"}


@dataclass
class Source:
    path: Path
    sha256: str
    schema_version: int
    tables: dict[str, list[dict]] = field(default_factory=dict)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_source(path: Path) -> Source:
    """Lit une sauvegarde .db de paie-bulletins en lecture seule et contrôle son intégrité."""
    path = Path(path)
    before = sha256_file(path)
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise PayrollError("Source corrompue (integrity_check).")
            version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
            if version != 1:
                raise PayrollError(f"Version de schéma de la source non prise en charge : {version}.")
            found = defaultdict(set)
            for kind, name in conn.execute("SELECT type, name FROM sqlite_master WHERE type IN ('trigger', 'index') "
                                           "AND sql IS NOT NULL"):
                found[kind].add(name)
            if dict(found) != EXPECTED_SOURCE_PROTECTIONS:
                raise PayrollError("Source refusée : protections (déclencheurs, index) différentes du schéma d'origine.")
            if conn.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise PayrollError("Source refusée : références incohérentes entre les tables.")
            source = Source(path, before, version)
            for table in SOURCE_TABLES:
                source.tables[table] = [dict(r) for r in conn.execute(f"SELECT * FROM {table} ORDER BY id")]
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        raise PayrollError("Ce fichier n'est pas une base paie-bulletins valide.") from exc
    if sha256_file(path) != before:
        raise PayrollError("La source a changé pendant la lecture.")
    return source


# --- Vérifications (lecture seule) --------------------------------------------------------------

def recalc_check(source: Source) -> dict:
    """R0.3 : recalcul de chaque paie clôturée ou remplacée par le noyau, comparé CHAÎNE PAR CHAÎNE."""
    checked, gaps = 0, []
    cumuls_info = []
    slips = source.tables["payslips"]
    for s in slips:
        if s["status"] not in ("cloturee", "remplacee") or not s["result"]:
            continue
        checked += 1
        inputs = MonthlyInput.from_dict(json.loads(s["inputs"]))
        params = PayrollParameters.from_dict(json.loads(s["parameters"]))
        nb = int(json.loads(s["employee_snapshot"])["nb_personnes_charge"])
        recomputed = json.dumps(compute_payslip(inputs, params, nb).to_dict())
        if recomputed != s["result"]:
            stored, again = json.loads(s["result"]), json.loads(recomputed)
            gaps.append({"payslip_id": s["id"], "periode": f"{s['year']:04d}-{s['month']:02d}", "version": s["version"],
                         "champs": sorted(k for k in again if again.get(k) != stored.get(k))})
        if s["status"] == "cloturee":
            before = [PayslipResult.from_dict(json.loads(o["result"])) for o in sorted(slips, key=lambda o: o["month"])
                      if o["employee_id"] == s["employee_id"] and o["year"] == s["year"] and o["month"] < s["month"]
                      and o["status"] == "cloturee"]
            again_cumuls = json.dumps(compute_cumuls(before, PayslipResult.from_dict(json.loads(s["result"]))).to_dict())
            if again_cumuls != s["cumuls"]:
                cumuls_info.append({"payslip_id": s["id"], "periode": f"{s['year']:04d}-{s['month']:02d}"})
    return {"paies_verifiees": checked, "ecarts": gaps, "cumuls_differents_d_aujourd_hui": cumuls_info}


def pdf_check(source: Source) -> dict:
    bad = [d["payslip_id"] for d in source.tables["documents"]
           if hashlib.sha256(bytes(d["content"])).hexdigest() != d["sha256"]]
    return {"pdf": len(source.tables["documents"]), "empreintes_differentes": bad,
            "empreintes": {d["filename"]: d["sha256"] for d in source.tables["documents"]}}


def monthly_totals(payslips: list[dict]) -> list[dict]:
    """Totaux par mois : paies par statut ; brut, net, cotisations des paies faisant foi (clôturées)."""
    out: dict[str, dict] = {}
    for s in payslips:
        key = f"{s['year']:04d}-{s['month']:02d}"
        row = out.setdefault(key, {"periode": key, "statuts": defaultdict(int), "brut": Decimal(0), "net": Decimal(0),
                                   "cotisations_salariales": Decimal(0), "cotisations_patronales": Decimal(0)})
        row["statuts"][s["status"]] += 1
        if s["status"] == "cloturee" and s["result"]:
            r = json.loads(s["result"])
            row["brut"] += Decimal(r["salaire_brut"])
            row["net"] += Decimal(r["net_a_payer"])
            row["cotisations_salariales"] += Decimal(r["total_cotisations_salariales"])
            row["cotisations_patronales"] += Decimal(r["total_cotisations_patronales"])
    return [{**v, "statuts": dict(sorted(v["statuts"].items())),
             **{k: str(v[k]) for k in ("brut", "net", "cotisations_salariales", "cotisations_patronales")}}
            for _, v in sorted(out.items())]


# --- Cible --------------------------------------------------------------------------------------

def _target_columns(conn, table: str) -> list[str]:
    return [r["c"] for r in conn.execute(
        "SELECT COLUMN_NAME AS c FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ? "
        "AND EXTRA NOT IN ('VIRTUAL GENERATED', 'STORED GENERATED') ORDER BY ORDINAL_POSITION", (table,)).fetchall()]


def target_state(db: Database) -> dict:
    """Décomptes de la cible et détection des seules lignes d'amorçage tolérées."""
    with db.read() as conn:
        counts = {t: conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
                  for t in BUSINESS_TABLES + ["parameter_sets", "audit_log"]}
        sets = conn.execute("SELECT id, valid_from, created_by FROM parameter_sets").fetchall()
        audit_actions = {r["action"] for r in conn.execute("SELECT DISTINCT action FROM audit_log")}
    business = {t: counts[t] for t in BUSINESS_TABLES if counts[t]}
    bootstrap_set = len(sets) == 1 and sets[0]["valid_from"] == "2000-01" and sets[0]["created_by"] == "système"
    problems = []
    if business:
        problems.append(f"données métier présentes : {business}")
    if sets and not bootstrap_set:
        problems.append("versions de paramètres autres que la version initiale d'amorçage")
    if audit_actions - BOOTSTRAP_AUDIT:
        problems.append(f"journal contenant d'autres opérations : {sorted(audit_actions - BOOTSTRAP_AUDIT)}")
    return {"counts": counts, "bootstrap_parameter_set": sets[0]["id"] if bootstrap_set else None,
            "audit_rows": counts["audit_log"], "problems": problems}


def import_source(db: Database, source: Source) -> dict:
    """Import à l'identique dans une transaction unique ; refus si la cible n'est pas vide."""
    state = target_state(db)
    if state["problems"]:
        raise PayrollError("Cible refusée (non vide) : " + " ; ".join(state["problems"]))
    renumber_audit = state["audit_rows"] > 0
    inserted = {}
    with db.transaction() as conn:
        if state["bootstrap_parameter_set"] is not None:
            conn.execute("DELETE FROM parameter_sets WHERE id = ?", (state["bootstrap_parameter_set"],))
        for table in SOURCE_TABLES:
            target_cols = set(_target_columns(conn, table))
            rows = source.tables[table]
            if not rows:
                inserted[table] = 0
                continue
            cols = [c for c in rows[0] if c in target_cols and not (table == "audit_log" and renumber_audit and c == "id")]
            missing = [c for c in rows[0] if c not in target_cols]
            if missing:
                raise PayrollError(f"Colonnes source inconnues de la cible ({table}) : {missing}")
            sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
            for row in rows:
                conn.execute(sql, [row[c] for c in cols])
            inserted[table] = len(rows)
    return {"inseres": inserted, "journal_renumerote": renumber_audit,
            "version_initiale_remplacee": state["bootstrap_parameter_set"] is not None}


def compare_target(db: Database, source: Source, audit_renumbered: bool) -> dict:
    """Cible = source, champ par champ (octets compris), pour chaque table importée."""
    diffs = {}
    with db.read() as conn:
        for table in SOURCE_TABLES:
            rows = source.tables[table]
            if not rows:
                continue
            cols = [c for c in rows[0] if not (table == "audit_log" and audit_renumbered and c == "id")]
            if table == "audit_log" and audit_renumbered:
                got = conn.execute(f"SELECT {', '.join(cols)} FROM audit_log ORDER BY id").fetchall()[-len(rows):]
            else:
                got = conn.execute(f"SELECT {', '.join(cols)} FROM {table} ORDER BY id").fetchall()
            expected = [[r[c] for c in cols] for r in rows]
            actual = [[bytes(v) if isinstance(v, (bytes, bytearray)) else v for v in (g[c] for c in cols)] for g in got]
            norm = [[bytes(v) if isinstance(v, (bytes, bytearray, memoryview)) else v for v in e] for e in expected]
            if actual != norm:
                bad = [i for i, (a, e) in enumerate(zip(actual, norm)) if a != e]
                diffs[table] = {"source": len(norm), "cible": len(actual), "lignes_differentes": bad[:20]}
    return diffs


def run(source_path: Path, db: Database | None, dry_run: bool) -> dict:
    """Migration complète (ou simulation) ; renvoie le compte rendu (US-53)."""
    source = read_source(source_path)
    report = {
        "source": {"fichier": source_path.name, "sha256": source.sha256, "schema_version": source.schema_version},
        "decomptes_source": {t: len(r) for t, r in source.tables.items()},
        "totaux_par_mois": monthly_totals(source.tables["payslips"]),
        "r0_recalcul": recalc_check(source),
        "pdf": pdf_check(source),
        "dry_run": dry_run,
    }
    if db is not None:
        report["cible_avant"] = target_state(db)
        if not dry_run:
            result = import_source(db, source)
            report["import"] = result
            report["ecarts_cible_source"] = compare_target(db, source, result["journal_renumerote"])
            from app.socle.backup import check_database_protections

            check_database_protections(db)
            report["protections_verifiees"] = True
    if sha256_file(source_path) != source.sha256:
        raise PayrollError("La source a été modifiée pendant la migration.")
    report["source"]["sha256_apres"] = source.sha256
    return report
