"""Tableau de bord et liste « Paie du mois » (S4 / US-41, US-43) — agrégats en LECTURE SEULE.

Tous les totaux sont calculés ici, côté serveur (Decimal pour la paie, entiers DH pour la trésorerie) :
le frontend n'effectue aucun calcul sur les montants (R0). Les montants de paie proviennent des
résultats stockés du noyau ; rien n'est recalculé.
"""

from __future__ import annotations

import datetime as dt

from app.paie.core.models.payroll import STATUT_CALCULEE, STATUTS_LIBELLES
from app.paie.core.validation.validators import ERREUR
from app.paie.repositories.db import Database
from app.paie.services import master_data, payroll
from app.tresorerie.legacy import dates, db_gen, integrity
from app.tresorerie.services import echeancier

ORDER = (db_gen.T_S1, db_gen.T_CN, db_gen.T_S2, db_gen.T_S3)


def _dot(e: echeancier.Echeance | None, today: dt.date) -> str:
    """Pastille d'échéance : paye_a_temps, paye_retard, paye_avance, en_retard, a_venir, non_declaree."""
    if e is None:
        return "non_declaree"
    if integrity.est_paye(e.legacy()):
        return {"Payé – à temps": "paye_a_temps", "Payé – retard": "paye_retard"}.get(e.statut, "paye_avance")
    return "en_retard" if integrity.est_en_retard(e.legacy(), today) else "a_venir"


def payslip_state(slip) -> dict:
    if slip is None:
        return {"status": "a_saisir", "status_label": "À saisir", "payslip_id": None, "version": None,
                "net_a_payer": None}
    return {"status": slip.status, "status_label": STATUTS_LIBELLES[slip.status], "payslip_id": slip.id,
            "version": slip.version,
            "net_a_payer": str(slip.result.net_a_payer) if slip.result is not None else None}


def month_payroll(db: Database, year: int, month: int) -> list[dict]:
    """Salariés actifs du mois et état de leur paie (version de travail, sinon clôturée en vigueur)."""
    rows = []
    for emp in master_data.list_employees(db):
        if not echeancier.employed_during(emp, year, month):
            continue
        state = payslip_state(payroll.current_payslip(db, emp.id, year, month))
        rows.append({"employee_id": emp.id, "matricule": emp.matricule, "nom": emp.nom, "prenom": emp.prenom,
                     "fonction": emp.fonction, "nb_personnes_charge": emp.nb_personnes_charge, **state})
    return rows


def dashboard(db: Database, year: int, month: int, today: dt.date | None = None) -> dict:
    today = today or dates.aujourdhui()
    period = f"{year:04d}-{month:02d}"
    tomorrow = (today + dt.timedelta(days=1)).isoformat()
    rows, late, ready = [], [], []
    plan_total = paid_salary = cnss_total = cnss_paid = 0
    counts = {"cloturee": 0, "calculee": 0, "brouillon": 0, "a_saisir": 0}
    with db.read() as conn:
        plans = {}
        for emp in master_data.list_employees(db):
            if echeancier.employed_during(emp, year, month):
                plans[emp.id] = (emp, echeancier.plan_for_period(conn, emp.id, period))
    for emp_id, (emp, plan) in plans.items():
        items = {e.type: e for e in echeancier.list_echeances(db, year, month, emp_id)}
        dots = [{"type": t, "state": _dot(items.get(t), today)} for t in ORDER]
        paid = [e for e in items.values() if integrity.est_paye(e.legacy())]
        late_items = [e for e in items.values() if integrity.est_en_retard(e.legacy(), today)]
        late += [{"employee_id": emp_id, "nom": f"{emp.nom} {emp.prenom}".strip(), "type": e.type,
                  "date_echeance": e.date_echeance, "montant": e.montant} for e in late_items]
        verse = sum(e.montant for e in paid if e.type in echeancier.SALARY_TYPES)
        expected_salary = sum(e.montant for e in items.values() if e.type in echeancier.SALARY_TYPES)
        if not items and plan is not None:
            expected_salary = plan.total_salaire
        plan_total += expected_salary
        paid_salary += verse
        cnss_total += sum(e.montant for e in items.values() if e.type == db_gen.T_CN)
        cnss_paid += sum(e.montant for e in paid if e.type == db_gen.T_CN)
        slip = payroll.current_payslip(db, emp_id, year, month)
        state = payslip_state(slip)
        counts[state["status"]] += 1
        if slip is not None and slip.status == STATUT_CALCULEE and \
                not any(i.level == ERREUR for i in payroll.closure_checks(db, slip.id)):
            ready.append({"employee_id": emp_id, "nom": f"{emp.nom} {emp.prenom}".strip(), "payslip_id": slip.id})
        rows.append({
            "employee_id": emp_id, "matricule": emp.matricule, "nom": emp.nom, "prenom": emp.prenom,
            "fonction": emp.fonction, "declared": bool(items), "has_plan": plan is not None, "dots": dots,
            "paid_count": len(paid), "late_count": len(late_items), "echeances": len(items),
            "verse_salaire": verse, "salaire_attendu": expected_salary, **state,
        })
    # Rappels J-1 de demain et prochaines échéances non payées (groupées par date et type).
    unpaid = [e for e in echeancier.list_echeances(db, paid=False) if e.employee_id in plans]
    reminders_tomorrow = [e for e in unpaid if e.rappel_j1 == tomorrow]
    future = sorted([e for e in unpaid if e.date_echeance >= today.isoformat()], key=lambda e: (e.date_echeance, e.n))
    next_rem = min((e.rappel_j1 for e in unpaid if e.rappel_j1 > tomorrow), default=None)
    groups: dict[tuple[str, str], dict] = {}
    for e in future:
        g = groups.setdefault((e.date_echeance, e.type), {"date_echeance": e.date_echeance, "type": e.type,
                                                          "nombre": 0, "montant": 0})
        g["nombre"] += 1
        g["montant"] += e.montant
    next_year, next_month = (year + (month == 12), month % 12 + 1)
    next_declared = any(echeancier.list_echeances(db, next_year, next_month, emp_id) for emp_id in plans)
    return {
        "periode": period, "aujourdhui": today.isoformat(), "salaries_actifs": len(plans),
        "kpi": {
            "salaires_attendus": plan_total, "salaires_verses": paid_salary,
            "salaires_reste": plan_total - paid_salary,
            "salaires_avancement": round(100 * paid_salary / plan_total) if plan_total else 0,
            "cnss_du_mois": cnss_total, "cnss_versee": cnss_paid,
            "bulletins_clotures": counts["cloturee"], "bulletins": counts,
        },
        "rows": rows,
        "a_traiter": {"en_retard": late, "rappels_demain": len(reminders_tomorrow), "prochain_rappel": next_rem,
                      "prets_a_cloturer": ready},
        "prochaines": list(groups.values())[:6],
        "mois_suivant": {"year": next_year, "month": next_month, "declare": next_declared},
    }
