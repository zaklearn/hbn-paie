#!/usr/bin/env python3
"""Essai à blanc de la migration (S5 / US-53) — base de DEV uniquement, à partir de COPIES des sources.

1. Sources : dossier ``--sources`` (fichiers du propriétaire : *.db, data.json, backup_*.json) ; s'il n'en contient
   pas, sources de SUBSTITUTION générées (application d'origine + data.json synthétique).
2. Copie des sources dans un dossier temporaire (SHA-256 des originaux contrôlé avant/après).
3. Simulation (--dry-run) des deux outils, puis import réel dans une base de dev NEUVE, et contrôles.
4. Deux exécutions complètes sur deux bases neuves : les rapports doivent être identiques.
5. Rapport Markdown : docs/sprints/S5_MIGRATION_DRYRUN.md (ou --out).

Variables : PAIE_TEST_DB_URL (serveur MySQL de dev). Matricule : --matricule (défaut 0001).
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from app.migration import ezzinecdi, paie_bulletins  # noqa: E402
from app.paie.services import master_data  # noqa: E402
from app.socle.backup import check_database_protections  # noqa: E402
from app.tresorerie.legacy import integrity  # noqa: E402
from app.tresorerie.services import echeancier  # noqa: E402
from tests.migration.sources import make_ezzinecdi, make_paie_db  # noqa: E402
from tests.paie.mysql_db import Database  # noqa: E402

TODAY = dt.date(2026, 11, 21)          # date de référence figée : rapport rejouable à l'identique
REPRISE: dict | None = None            # reclôture dans HBN Paie (option --reprise), décision du 22/11/2026


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_sources(directory: Path | None) -> tuple[str, Path, Path, list[Path]]:
    if directory and directory.is_dir():
        dbs = sorted(directory.glob("*.db"))
        data = directory / "data.json"
        if not data.is_file():
            rebuilt = sorted(directory.glob("data_reconstitue_*.json"))
            data = rebuilt[-1] if rebuilt else data
        if dbs and data.is_file():
            kind = "propriétaire" if data.name == "data.json" else "propriétaire (data.json reconstitué sur déclaration)"
            return kind, dbs[0], data, sorted(directory.glob("backup_*.json"))
    tmp = Path(tempfile.mkdtemp(prefix="hbn-substitution-"))
    data, backup = make_ezzinecdi(tmp)
    return "substitution", make_paie_db(tmp), data, [backup]


def one_run(label: str, db_file: Path, data: Path, backups: list[Path], matricule: str, workdir: Path) -> dict:
    db = Database(workdir / f"cible-{label}.db")
    db.migrate()
    pb_dry = paie_bulletins.run(db_file, db, dry_run=True)
    ez_dry = ezzinecdi.run(data, matricule, None, dry_run=True, backups=backups, today=TODAY)
    pb = paie_bulletins.run(db_file, db, dry_run=False)
    ez = ezzinecdi.run(data, matricule, db, dry_run=False, backups=backups, today=TODAY)
    check_database_protections(db)
    reprise, comparaison = None, None
    if REPRISE:
        from app.migration import reprise_paie
        reprise = reprise_paie.reclose(db, matricule, REPRISE["year"], REPRISE["months"], REPRISE["copy"])
        comparaison = reprise_paie.compare_with_references(db, matricule, REPRISE["year"], REPRISE["references"])
    conn = db.connect()
    try:
        target_counts = {t: conn.execute(f"SELECT COUNT(*) AS n FROM {t}").fetchone()["n"]
                         for t in paie_bulletins.SOURCE_TABLES + ["payment_plans", "echeances"]}
    finally:
        conn.close()
    months: dict[str, dict] = {}
    for e in echeancier.list_echeances(db):
        m = months.setdefault(f"{e.annee:04d}-{e.mois_num:02d}", {"payees": 0, "non_payees": 0, "montant_paye": 0,
                                                                    "montant_non_paye": 0})
        paid = integrity.est_paye(e.legacy())
        m["payees" if paid else "non_payees"] += 1
        m["montant_paye" if paid else "montant_non_paye"] += e.montant
    for report in (pb, pb_dry):
        report.pop("cible_avant", None)
    params = [ps.valid_from for ps in master_data.list_parameter_sets(db)]
    return {"pb_dry": pb_dry, "ez_dry": ez_dry, "pb": pb, "ez": {k: v for k, v in ez.items() if k != "employee_id"},
            "target_counts": target_counts, "echeances_par_mois": dict(sorted(months.items())), "parametres": params,
            "reprise": reprise, "comparaison": comparaison}


def fmt(v) -> str:
    return f"{v:,}".replace(",", " ") if isinstance(v, int) else str(v)


def markdown(kind: str, hashes: dict, run: dict, identical: bool) -> str:
    pb, ez, dry = run["pb"], run["ez"], run["pb_dry"]
    r0 = pb["r0_recalcul"]
    L = ["# S5 — Essai à blanc de la migration (base de dev)", "",
         f"**Sources : {kind}.** " + ("Les fichiers du propriétaire n'étant pas encore déposés dans "
                                      "`migration/sources/`, l'essai porte sur des sources de SUBSTITUTION : une base .db "
                                      "produite par l'application paie-bulletins d'origine (démo fictive, rectification, "
                                      "second salarié, brouillon) et un data.json synthétique au format ezzinecdi. "
                                      "L'essai sur les vraies données est à rejouer dès leur dépôt (même commande)."
                                      if kind == "substitution" else "Fichiers déposés par le propriétaire (copies)."),
         "", f"**R0.3 : {r0['paies_verifiees']} paie(s) clôturée(s) ou remplacée(s) recalculée(s) en lecture seule, "
         f"{len(r0['ecarts'])} écart(s) chaîne par chaîne.** Rejouabilité : deux exécutions complètes sur deux bases "
         f"neuves → rapports {'IDENTIQUES' if identical else 'DIFFÉRENTS'}.", "",
         "## 1. Sources (copies ; originaux inchangés)", "| Fichier | SHA-256 avant | SHA-256 après |", "|---|---|---|"]
    for name, (before, after) in hashes.items():
        L.append(f"| `{name}` | `{before}` | `{after}`{'' if before == after else ' ⚠️'} |")
    L += ["", "## 2. Décomptes source → cible", "| Table | Source | Cible |", "|---|---|---|"]
    for t, n in pb["decomptes_source"].items():
        note = " (+1 : trace `migration.ezzinecdi`)" if t == "audit_log" and run["target_counts"][t] == n + 1 else ""
        L.append(f"| {t} | {n} | {run['target_counts'][t]}{note} |")
    L.append(f"| payment_plans | 1 (plan v1 déduit) | {run['target_counts']['payment_plans']} |")
    L.append(f"| echeances | {ez['source']['enregistrements']} enregistrements | {run['target_counts']['echeances']} |")
    L += ["", f"Écarts cible/source champ par champ (paie-bulletins) : **{pb['ecarts_cible_source'] or 'aucun'}**. "
          f"Échéances : {ez['ecarts_cible_source']['importees']} importées / {ez['ecarts_cible_source']['attendues']} "
          f"attendues, différentes : {ez['ecarts_cible_source']['differentes'] or 'aucune'}. Journal "
          f"{'renuméroté (cible amorcée)' if pb['import']['journal_renumerote'] else 'identifiants conservés'} ; "
          f"protections de la base vérifiées après import.", "",
          "## 3. Totaux par mois — paie (paies faisant foi)",
          "| Période | Statuts | Brut | Net | Cot. salariales | Cot. patronales |", "|---|---|---|---|---|---|"]
    for m in pb["totaux_par_mois"]:
        st = ", ".join(f"{k} {v}" for k, v in m["statuts"].items())
        L.append(f"| {m['periode']} | {st} | {m['brut']} | {m['net']} | {m['cotisations_salariales']} | "
                 f"{m['cotisations_patronales']} |")
    L += ["", "## 4. Totaux par mois — trésorerie (après import)",
          "| Période | Payées | Non payées | Montant payé (DH) | Montant non payé (DH) |", "|---|---|---|---|---|"]
    for k, v in run["echeances_par_mois"].items():
        L.append(f"| {k} | {v['payees']} | {v['non_payees']} | {fmt(v['montant_paye'])} | {fmt(v['montant_non_paye'])} |")
    L += ["", "## 5. Bulletins PDF : empreintes recalculées = stockées",
          f"{pb['pdf']['pdf']} PDF ; empreintes différentes : **{pb['pdf']['empreintes_differentes'] or 'aucune'}**.", "",
          "| Fichier | SHA-256 |", "|---|---|"]
    for name, digest in sorted(pb["pdf"]["empreintes"].items()):
        L.append(f"| `{name}` | `{digest}` |")
    L += ["", "## 6. R0.3 — recalcul de vérification",
          f"- Paies vérifiées : {r0['paies_verifiees']} ; écarts : {r0['ecarts'] or 'aucun'} (jamais corrigés).",
          f"- Cumuls différents de ceux qu'on calculerait aujourd'hui (information, attendu après une rectification "
          f"d'un mois antérieur : les bulletins conservent les cumuls tels qu'émis) : "
          f"{[c['periode'] for c in r0['cumuls_differents_d_aujourd_hui']] or 'aucun'}.", "",
          "## 7. ezzinecdi — plan v1, simulation de la réconciliation, anomalies",
          f"- Plan v1 (premier mois) : effet {ez['plan_v1']['valid_from']}, 1er versement {fmt(ez['plan_v1']['s1'])}, "
          f"CNSS {fmt(ez['plan_v1']['cnss'])}, 2e {fmt(ez['plan_v1']['s2'])}, 3e {fmt(ez['plan_v1']['s3'])} DH.",
          f"- Compte rendu de la réconciliation d'origine (simulation) : "
          f"{json.dumps({k: v for k, v in ez['simulation']['compte_rendu'].items() if k != 'details'}, ensure_ascii=False)}.",
          f"- Corrections qu'elle ferait (NON appliquées) : {len(ez['simulation']['corrections'])}."]
    for c in ez["simulation"]["corrections"]:
        L.append(f"  - n° {c['n']} {c['mois']} / {c['type']} : "
                 + "; ".join(f"{f} {v['avant']!r} → {v['apres']!r}" for f, v in c["changements"].items()))
    L.append(f"- Non importés : hors schéma {len(ez['rejetes'])}, doublons écartés (le payé prime) "
             f"{len(ez['doublons_ecartes'])}, incohérences statut/date {len(ez['incoherences'])}.")
    for i in ez["incoherences"]:
        L.append(f"  - {i['cle'][0]} / {i['cle'][1]} : statut « {i['statut']} » avec date {i['date_paiement']}")
    for b in ez["sauvegardes_comparees"]:
        L.append(f"- `{b['fichier']}` comparé à data.json : {b['enregistrements']} enregistrements, seulement dans "
                 f"data.json {b['seulement_dans_data_json']}, seulement dans le backup {b['seulement_dans_backup']}, "
                 f"différents {len(b['differents'])}.")
    if run.get("reprise"):
        L += ["", "## 7 bis. Reprise de paie par reclôture dans HBN Paie (décision du 22/11/2026)",
              "| Période | Action | Version | Net à payer |", "|---|---|---|---|"]
        for s in run["reprise"]:
            L.append(f"| {s['periode']} | {s['action']} | {s.get('version', '')} | {s.get('net_a_payer', '')} |")
        L += ["", "Comparaison du texte de chaque bulletin produit avec le PDF d'origine (hors « Paie clôturée le … » "
              "et « édité le … ») :", "", "| Bulletin d'origine | Identique | Lignes | SHA-256 d'origine (archivé) |",
              "|---|---|---|---|"]
        for c in run["comparaison"]:
            L.append(f"| `{c['reference']}` | {'oui' if c['identique'] else 'NON'} | {c.get('lignes', '')} "
                     f"({c.get('lignes_differentes', '?')} différente(s)) | `{c.get('sha256_reference', '')}` |")
    L += ["", "## 8. Simulation (--dry-run) : aucune écriture",
          f"Simulation paie-bulletins : cible inchangée ; rapport de simulation identique au rapport d'import sur "
          f"les contrôles source (R0.3, PDF, totaux) : {'oui' if dry['r0_recalcul'] == r0 and dry['pdf'] == pb['pdf'] and dry['totaux_par_mois'] == pb['totaux_par_mois'] else 'NON'}.",
          "", "## 9. Points soumis au propriétaire"]
    if kind == "substitution":
        L += ["1. Déposer la sauvegarde .db, data.json + backup_*.json et le matricule : l'essai sera rejoué sur ces copies.",
              "2. Valider les éventuelles corrections proposées par la réconciliation (aucune n'est appliquée).",
              "3. Les enregistrements non importés (hors schéma, doublon écarté, incohérence) restent à arbitrer.", ""]
    else:
        L += ["1. Valider ce rapport (décomptes, totaux, plan v1, échéances reconstituées) avant l'import réel (S6, étape D).",
              "2. Paie : valider la reprise par reclôture (texte des bulletins identique aux PDF d'origine, seules les dates "
              "de clôture et d'édition changent ; PDF d'origine archivés comme référence).",
              f"3. Corrections proposées : {len(ez['simulation']['corrections'])} ; non importés : "
              f"{len(ez['rejetes']) + len(ez['doublons_ecartes']) + len(ez['incoherences'])}.", ""]
    return "\n".join(L)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--sources", type=Path)
    p.add_argument("--matricule", default="0001")
    p.add_argument("--out", type=Path, default=ROOT / "docs/sprints/S5_MIGRATION_DRYRUN.md")
    p.add_argument("--reprise", help="AAAA:mois,…:mois_cree=mois_source (ex. 2026:7,8,9,10:10=9)")
    p.add_argument("--masquer", action="store_true", help="masque le matricule dans le rapport")
    a = p.parse_args()
    global REPRISE
    kind, db_file, data, backups = find_sources(a.sources)
    if a.reprise:
        year, months, copy = a.reprise.split(":")
        REPRISE = {"year": int(year), "months": [int(m) for m in months.split(",")],
                   "copy": {int(k): int(v) for k, v in (c.split("=") for c in copy.split(",") if c)},
                   "references": sorted((a.sources / "reference").glob("bulletin_*.pdf")) if a.sources else []}
    originals = [db_file, data, *backups]
    before = {f.name: sha(f) for f in originals}
    with tempfile.TemporaryDirectory(prefix="hbn-migration-") as tmp:
        work = Path(tmp)
        copies = []
        for f in originals:
            shutil.copy2(f, work / f.name)
            copies.append(work / f.name)
        db_copy, data_copy, backup_copies = copies[0], copies[1], copies[2:]
        runs = [one_run(str(i), db_copy, data_copy, backup_copies, a.matricule, work) for i in (1, 2)]
    after = {f.name: sha(f) for f in originals}
    identical = json.dumps(runs[0], sort_keys=True, default=str) == json.dumps(runs[1], sort_keys=True, default=str)
    hashes = {n: (before[n], after[n]) for n in before}
    text = markdown(kind, hashes, runs[0], identical)
    if a.masquer:
        text = text.replace(a.matricule, "•" * (len(a.matricule) - 4) + a.matricule[-4:])
    a.out.write_text(text, encoding="utf-8")
    print(f"rapport : {a.out} ; rejouable : {identical} ; originaux inchangés : {before == after}")
    from tests.paie import mysql_db                       # bases de dev de l'essai supprimées

    created, mysql_db.CREATED[:] = list(mysql_db.CREATED), []
    conn = mysql_db.admin_connection()
    try:
        with conn.cursor() as cur:
            for d in created:
                d.dispose()
                cur.execute(f"DROP DATABASE IF EXISTS `{d.name}`")
    finally:
        conn.close()
    return 0 if identical and before == after else 1


if __name__ == "__main__":
    sys.exit(main())
