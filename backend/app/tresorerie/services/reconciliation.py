"""Réconciliation d'ezzinecdi adaptée au plan de versement par salarié (S3 / US-34).

``reconcile_plan`` est une COPIE de ``legacy.integrity.reconcile`` où UNE seule ligne change :
le montant attendu vient du plan du salarié à la date d'échéance (``montant_attendu(type, date)``)
au lieu du barème fixe ``db_gen.MONTANT_TYPE[type]``. ``tests/tresorerie/test_reconciliation.py``
vérifie que le reste du code est identique à l'original.

``simulate`` ne modifie rien : il travaille sur une copie et renvoie le compte rendu et la liste
des corrections que la réconciliation ferait (utilisé par le diagnostic et par l'import en S5).
La fusion conserve toujours le payé (dédoublonnage d'origine).
"""

from __future__ import annotations

import copy
import datetime as dt
from collections.abc import Callable
from typing import Dict, List, Tuple

from app.tresorerie.legacy import db_gen
from app.tresorerie.legacy.integrity import (
    _schema_ok, est_en_retard, est_paye, regularite, statut_paye,
)

MontantAttendu = Callable[[str, dt.date], int]


def reconcile_plan(records: List[Dict], montant_attendu: MontantAttendu,
                   today: dt.date | None = None) -> Tuple[List[Dict], Dict]:
    today = today or dt.date.today()
    rep = {"recus": len(records or []), "rejetes": 0, "doublons": 0,
           "rappels_corriges": 0, "montants_corriges": 0, "mois_corriges": 0,
           "statuts_corriges": 0, "total": 0, "payes": 0, "non_payes": 0,
           "en_retard": 0, "modifie": False, "details": []}

    valides: List[Dict] = []
    for rec in (records or []):
        if not _schema_ok(rec):
            rep["rejetes"] += 1
            rep["details"].append(f"Rejeté (schéma) : {str(rec)[:80]}")
            continue
        valides.append(rec)

    # Dédoublonnage (mois+type) — le payé prime
    par_cle: Dict[Tuple[str, str], Dict] = {}
    for rec in valides:
        k = db_gen.cle(rec)
        if k not in par_cle:
            par_cle[k] = rec
        else:
            rep["doublons"] += 1
            if est_paye(rec) and not est_paye(par_cle[k]):
                par_cle[k] = rec
            rep["details"].append(f"Doublon fusionné : {k[1]} / {k[0]}")
    dedup = list(par_cle.values())

    for rec in dedup:
        e = dt.date.fromisoformat(rec["date_echeance"])
        # rappel J-1 dérivé
        attendu = (e - dt.timedelta(days=1)).isoformat()
        if rec.get("rappel_j1") != attendu:
            rec["rappel_j1"] = attendu
            rep["rappels_corriges"] += 1
        # montant attendu par type
        att_m = montant_attendu(rec["type"], e)
        if int(rec["montant"]) != att_m:
            rec["montant"] = att_m
            rep["montants_corriges"] += 1
        else:
            rec["montant"] = int(rec["montant"])
        # mois cohérent avec la date
        att_mois = db_gen.mois_label(e.year, e.month)
        if rec.get("mois") != att_mois:
            rec["mois"] = att_mois
            rep["mois_corriges"] += 1
        rec["observations"] = rec.get("observations") or ""

        # Cohérence payé ⇔ date_paiement + recalcul du statut
        if est_paye(rec):
            if not rec.get("date_paiement"):
                rec["date_paiement"] = rec["date_echeance"]  # repli : à temps
            reg = regularite(rec["date_paiement"], rec["date_echeance"])
            att_statut = statut_paye(reg)
            if rec["statut"] != att_statut:
                rec["statut"] = att_statut
                rep["statuts_corriges"] += 1
        else:
            if rec.get("date_paiement") is not None:
                rec["date_paiement"] = None
                rep["statuts_corriges"] += 1

    clean = db_gen.trier_renumeroter(dedup)
    rep["modifie"] = any(rep[k] for k in
                         ("rejetes", "doublons", "rappels_corriges",
                          "montants_corriges", "mois_corriges", "statuts_corriges"))
    rep["total"] = len(clean)
    rep["payes"] = sum(1 for r in clean if est_paye(r))
    rep["non_payes"] = rep["total"] - rep["payes"]
    rep["en_retard"] = sum(1 for r in clean if est_en_retard(r, today))
    return clean, rep


FIELDS = ("date_echeance", "mois", "type", "montant", "statut", "rappel_j1", "observations", "date_paiement")


def simulate(records: List[Dict], montant_attendu: MontantAttendu, today: dt.date | None = None) -> Dict:
    """Réconciliation en simulation : rien n'est écrit, les originaux ne sont pas modifiés.

    Renvoie le compte rendu d'origine, les corrections champ par champ (par position d'origine)
    et les enregistrements nettoyés tels que la réconciliation les produirait.
    """
    originals = copy.deepcopy(records or [])
    working = copy.deepcopy(records or [])
    tagged = []
    for i, rec in enumerate(working):
        if isinstance(rec, dict):
            rec = dict(rec)
            tagged.append((i, rec))
    by_identity = {id(rec): i for i, rec in tagged}
    clean, rep = reconcile_plan([rec for _, rec in tagged] + [r for r in working if not isinstance(r, dict)],
                                montant_attendu, today)
    corrections = []
    for rec in clean:
        i = by_identity.get(id(rec))
        if i is None:
            continue
        before = originals[i]
        changes = {f: {"avant": before.get(f), "apres": rec.get(f)} for f in FIELDS if before.get(f) != rec.get(f)}
        if changes:
            corrections.append({"index": i, "n": before.get("n"), "mois": rec.get("mois"), "type": rec.get("type"),
                                "changements": changes})
    return {"compte_rendu": rep, "corrections": corrections, "resultat": clean}


def plan_lookup(plans: list) -> MontantAttendu:
    """Montant attendu = plan du salarié en vigueur à la date d'échéance (plans triés ou non)."""
    ordered = sorted(plans, key=lambda p: p.valid_from)

    def montant(type_: str, date_echeance: dt.date) -> int:
        period = date_echeance.isoformat()[:7]
        applicable = [p for p in ordered if p.valid_from <= period]
        if not applicable:
            raise LookupError(f"aucun plan de versement en vigueur en {period}")
        return applicable[-1].montant(type_)

    return montant


def simulate_employee(db, employee_id: int, today: dt.date | None = None) -> Dict:
    """Diagnostic (panneau d'origine) : réconciliation simulée des échéances d'un salarié, sans écriture."""
    from app.tresorerie.services import echeancier

    records = [e.legacy() for e in echeancier.list_echeances(db, employee_id=employee_id)]
    lookup = plan_lookup(echeancier.list_plans(db, employee_id))
    try:
        result = simulate(records, lookup, today)
    except LookupError as exc:
        return {"compte_rendu": None, "corrections": [], "resultat": [], "erreur": str(exc)}
    result["erreur"] = None
    return result
