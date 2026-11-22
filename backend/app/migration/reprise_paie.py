"""Reprise de paie par reclôture dans HBN Paie (décision du propriétaire, 22/11/2026).

Contexte : la seule sauvegarde paie-bulletins disponible (27/10/2026) contient juillet–septembre « calculées » ;
les bulletins d'origine (clôturés le 06/11/2026) existent en PDF. Décision : importer la sauvegarde, puis
clôturer dans HBN Paie, et créer les mois absents avec la saisie désignée ; les PDF d'origine sont archivés
comme RÉFÉRENCE et chaque bulletin produit leur est comparé.

R0 : aucun calcul hors du noyau ; les clôtures passent par ``payroll.close`` (contrôles d'origine, recalcul de
vérification identique exigé). Comparaison : texte de chaque page, à l'exception des seules mentions datées
« Paie clôturée le jj/mm/aaaa » et « édité le jj/mm/aaaa » (et de l'ancienneté si elle dépendait de la date).
"""

from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path

from app.paie.core.models.payroll import STATUT_CALCULEE, STATUT_CLOTUREE, STATUTS_OUVERTS
from app.paie.repositories.db import Database
from app.paie.services import master_data, payroll
from app.paie.services.errors import PayrollError

ACTOR = "reprise"
RECALC_REQUIRED = ("Les paramètres, la fiche salarié, l'entreprise ou les cumuls ont changé depuis le calcul : "
                   "recalculez la paie avant de la clôturer.")
DATED = [(re.compile(r"Paie clôturée le \d\d/\d\d/\d{4}"), "Paie clôturée le <date>"),
         (re.compile(r"édité le \d\d/\d\d/\d{4}"), "édité le <date>")]


def pdf_lines(content: bytes) -> list[str]:
    import pdfplumber  # dépendance de vérification (image de dev), absente de l'image de production

    with pdfplumber.open(io.BytesIO(content)) as pdf:
        lines = [line for page in pdf.pages for line in (page.extract_text() or "").splitlines()]
    out = []
    for line in lines:
        for pattern, repl in DATED:
            line = pattern.sub(repl, line)
        out.append(line)
    return out


def reclose(db: Database, matricule: str, year: int, months: list[int], copy_inputs_from: dict[int, int]) -> list[dict]:
    """Clôture les mois indiqués, dans l'ordre ; crée d'abord ceux de ``copy_inputs_from`` (mois -> mois source)."""
    emp = next((e for e in master_data.list_employees(db) if e.matricule == matricule), None)
    if emp is None:
        raise PayrollError(f"Matricule {matricule} absent.")
    company = master_data.get_company(db)
    steps = []
    for month in sorted(months):
        slip = payroll.current_payslip(db, emp.id, year, month)
        action = []
        if slip is None:
            if month not in copy_inputs_from:
                raise PayrollError(f"{year}-{month:02d} absent et aucune saisie désignée.")
            src = payroll.current_payslip(db, emp.id, year, copy_inputs_from[month])
            pid, _ = payroll.save_draft(db, ACTOR, emp.id, year, month, src.inputs)
            payroll.calculate(db, ACTOR, pid)
            slip = payroll.get_payslip(db, pid)
            action.append(f"créée (saisie de {year}-{copy_inputs_from[month]:02d}) et calculée")
        elif slip.status == STATUT_CLOTUREE:
            steps.append({"periode": f"{year}-{month:02d}", "payslip_id": slip.id, "action": "déjà clôturée"})
            continue
        elif slip.status != STATUT_CALCULEE:
            payroll.calculate(db, ACTOR, slip.id)
            action.append("calculée")
        errors = [i.message for i in payroll.closure_checks(db, slip.id) if i.level == "erreur"]
        if errors == [RECALC_REQUIRED]:
            # Procédure d'origine : un mois calculé avant la clôture du mois précédent doit être recalculé
            # (cumuls) avant sa propre clôture. Recalcul par le noyau, même saisie, mêmes paramètres.
            payroll.calculate(db, ACTOR, slip.id)
            action.append("recalculée (cumuls à jour, procédure d'origine)")
            errors = [i.message for i in payroll.closure_checks(db, slip.id) if i.level == "erreur"]
        if errors:
            raise PayrollError(f"{year}-{month:02d} : clôture refusée par les contrôles d'origine : {errors}")
        closed = payroll.close(db, ACTOR, slip.id, confirm_warnings=True, logo=company.logo if company else None)
        action.append("clôturée")
        steps.append({"periode": f"{year}-{month:02d}", "payslip_id": closed.id, "version": closed.version,
                      "action": ", ".join(action), "net_a_payer": str(closed.result.net_a_payer)})
    assert all(payroll.current_payslip(db, emp.id, year, m).status not in STATUTS_OUVERTS for m in months)
    return steps


def compare_with_references(db: Database, matricule: str, year: int, references: list[Path]) -> list[dict]:
    """Texte de chaque bulletin produit = PDF d'origine, hors mentions datées de clôture et d'édition."""
    emp = next(e for e in master_data.list_employees(db) if e.matricule == matricule)
    out = []
    for ref in sorted(references):
        m = re.search(r"bulletin_(\d{4})-(\d{2})_", ref.name)
        if not m or int(m.group(1)) != year:
            continue
        month = int(m.group(2))
        slip = payroll.current_payslip(db, emp.id, year, month)
        doc = payroll.get_document(db, slip.id) if slip else None
        if doc is None:
            out.append({"reference": ref.name, "identique": False, "motif": "aucun bulletin produit"})
            continue
        ours, theirs = pdf_lines(doc.content), pdf_lines(ref.read_bytes())
        diff = [i for i, (a, b) in enumerate(zip(ours, theirs)) if a != b]
        out.append({"reference": ref.name, "sha256_reference": hashlib.sha256(ref.read_bytes()).hexdigest(),
                    "bulletin_produit": doc.filename,          # empreinte non comparée : ReportLab y date la création
                    "identique": not diff and len(ours) == len(theirs), "lignes": len(theirs),
                    "lignes_differentes": len(diff) + abs(len(ours) - len(theirs))})
    return out
