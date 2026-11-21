"""Rapprochement trésorerie ↔ paie (S3 / US-36) — LECTURE SEULE (R0.2).

Pour un salarié et un mois :
- versé au salarié = somme des versements de salaire (S1 + S2 + S3) payés ;
- net à payer = celui du bulletin clôturé, sinon de la paie calculée ;
- CNSS versée comparée aux cotisations salariales + patronales du résultat stocké (information).

Aucune écriture, aucun effet sur un calcul, une saisie, un paramètre ou un statut de paie.
Branché comme AVERTISSEMENT confirmable sur le point d'extension de clôture
(``payroll.CLOSURE_WARNING_PROVIDERS``), uniquement pour un salarié suivi en trésorerie
(plan de versement en vigueur sur le mois).
"""

from __future__ import annotations

from decimal import Decimal

from app.paie.core.formatting import fmt_money
from app.paie.core.models.payroll import STATUT_CALCULEE, STATUT_CLOTUREE
from app.paie.repositories import repos
from app.paie.repositories.db import Database
from app.paie.services import payroll
from app.paie.core.validation.validators import AVERTISSEMENT, Issue
from app.tresorerie.legacy import db_gen, integrity
from app.tresorerie.services import echeancier


def _compute(conn, employee_id: int, year: int, month: int, slip=None) -> dict:
    rows = conn.execute("SELECT type, montant, statut FROM echeances WHERE employee_id = ? AND annee = ? "
                        "AND mois_num = ?", (employee_id, year, month)).fetchall()
    salary = [r for r in rows if r["type"] in echeancier.SALARY_TYPES]
    paid_salary = [r for r in salary if integrity.est_paye(r)]
    cnss = [r for r in rows if r["type"] == db_gen.T_CN]
    if slip is None:
        slip = repos.get_closed_payslip(conn, employee_id, year, month)
        if slip is None:
            open_slip = repos.get_open_payslip(conn, employee_id, year, month)
            slip = open_slip if open_slip and open_slip.status == STATUT_CALCULEE else None
    result = slip.result if slip else None
    verse = Decimal(sum(r["montant"] for r in paid_salary))
    attendu = Decimal(sum(r["montant"] for r in salary))
    cnss_versee = Decimal(sum(r["montant"] for r in cnss if integrity.est_paye(r)))
    out = {
        "employee_id": employee_id, "year": year, "month": month,
        "echeances_salaire": len(salary), "echeances_salaire_payees": len(paid_salary),
        "versements_complets": bool(salary) and len(paid_salary) == len(salary),
        "verse_salaire": str(verse), "echeances_salaire_montant": str(attendu),
        "bulletin": None, "net_a_payer": None, "ecart_net": None,
        "cnss_versee": str(cnss_versee), "cotisations_totales": None, "ecart_cnss": None,
    }
    if result is not None:
        cotisations = result.total_cotisations_salariales + result.total_cotisations_patronales
        out.update(bulletin={"id": slip.id, "status": slip.status, "version": slip.version},
                   net_a_payer=str(result.net_a_payer), ecart_net=str(verse - result.net_a_payer),
                   cotisations_totales=str(cotisations), ecart_cnss=str(cnss_versee - cotisations))
    return out


def rapprochement(db: Database, employee_id: int, year: int, month: int) -> dict:
    """Rapprochement en lecture seule (affiché au tableau de bord, en paie du mois, sur la fiche)."""
    with db.read() as conn:
        return _compute(conn, employee_id, year, month)


def closure_warnings(conn, slip) -> list[Issue]:
    """Avertissements confirmables à la clôture ; ne bloquent jamais et ne modifient rien."""
    if slip.status not in (STATUT_CALCULEE, STATUT_CLOTUREE) or slip.result is None:
        return []
    if echeancier.plan_for_period(conn, slip.employee_id, f"{slip.year:04d}-{slip.month:02d}") is None:
        return []                                   # salarié non suivi en trésorerie ce mois-là
    r = _compute(conn, slip.employee_id, slip.year, slip.month, slip)
    issues: list[Issue] = []
    if not r["versements_complets"]:
        issues.append(Issue(AVERTISSEMENT, "tresorerie",
                            f"Versements incomplets : {r['echeances_salaire_payees']} versement(s) de salaire "
                            f"payé(s) sur {r['echeances_salaire']} ({fmt_money(Decimal(r['verse_salaire']))} DH "
                            f"versés)."))
    if Decimal(r["ecart_net"]) != 0:
        issues.append(Issue(AVERTISSEMENT, "tresorerie",
                            f"Écart de {fmt_money(abs(Decimal(r['ecart_net'])))} DH entre les versements de salaire "
                            f"({fmt_money(Decimal(r['verse_salaire']))} DH) et le net à payer "
                            f"({fmt_money(Decimal(r['net_a_payer']))} DH)."))
    return issues


def register() -> None:
    """Active l'avertissement de clôture (appelé au démarrage de l'application, une seule fois)."""
    if closure_warnings not in payroll.CLOSURE_WARNING_PROVIDERS:
        payroll.CLOSURE_WARNING_PROVIDERS.append(closure_warnings)
