"""API REST du module Trésorerie (/api/tresorerie/*) — S3 / US-37.

Écritures (plans, déclarer, payer, dévalider) : superadmin. Lecture et exports : tous les comptes.
La trésorerie n'écrit jamais dans les tables de paie (R0.2).
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from app.api.deps import current_user, get_db, superadmin
from app.paie.repositories.db import Database
from app.paie.services import master_data
from app.socle.users import User
from app.tresorerie.legacy import dates, integrity
from app.tresorerie.services import echeancier, exports, rapprochement, reconciliation

router = APIRouter(prefix="/api/tresorerie")
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class PlanIn(BaseModel):
    employee_id: int
    valid_from: str = Field(pattern=r"^\d{4}-\d{2}$")
    s1: int = Field(ge=0)
    cnss: int = Field(ge=0)
    s2: int = Field(ge=0)
    s3: int = Field(ge=0)
    comment: str = Field(default="", max_length=2000)


class DeclareIn(BaseModel):
    year: int
    month: int
    employee_id: int | None = None


class PayIn(BaseModel):
    version: int
    date_paiement: date | None = None


class VersionIn(BaseModel):
    version: int


def _out(e: echeancier.Echeance, today: date) -> dict:
    data = asdict(e)
    data["paye"] = integrity.est_paye(e.legacy())
    data["en_retard"] = integrity.est_en_retard(e.legacy(), today)     # badge calculé, jamais stocké
    return data


def _groups(db: Database, employee_ids: list[int] | None):
    employees = master_data.list_employees(db)
    if employee_ids:
        wanted = set(employee_ids)
        employees = [e for e in employees if e.id in wanted]
        if len(employees) != len(wanted):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Salarié introuvable.")
    groups = []
    for emp in employees:
        records = [e.legacy() for e in echeancier.list_echeances(db, employee_id=emp.id)]
        if records or employee_ids:
            groups.append((emp, records))
    return groups


def _file(content: bytes, media: str, filename: str) -> Response:
    return Response(content, media_type=media, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# --- Gabarit et plans ---------------------------------------------------------------------------

@router.get("/gabarit")
def template(_: User = Depends(current_user)) -> list[dict]:
    return echeancier.template()


@router.get("/plans")
def list_plans(employee_id: int, _: User = Depends(current_user), db: Database = Depends(get_db)) -> list[dict]:
    return [asdict(p) | {"total_salaire": p.total_salaire, "total_mensuel": p.total_salaire + p.cnss}
            for p in echeancier.list_plans(db, employee_id)]


@router.post("/plans", status_code=201)
def create_plan(body: PlanIn, user: User = Depends(superadmin), db: Database = Depends(get_db)) -> dict:
    plan_id = echeancier.create_plan(db, user.actor, body.employee_id, body.valid_from, body.s1, body.cnss,
                                     body.s2, body.s3, body.comment)
    return next(asdict(p) for p in echeancier.list_plans(db, body.employee_id) if p.id == plan_id)


# --- Échéances --------------------------------------------------------------------------------------

@router.get("/echeances")
def list_echeances(year: int | None = None, month: int | None = None, employee_id: int | None = None,
                   paid: bool | None = None, _: User = Depends(current_user), db: Database = Depends(get_db)) -> list[dict]:
    today = dates.aujourdhui()
    return [_out(e, today) for e in echeancier.list_echeances(db, year, month, employee_id, paid)]


@router.get("/a-venir")
def upcoming(employee_id: int | None = None, _: User = Depends(current_user), db: Database = Depends(get_db)) -> dict:
    today = dates.aujourdhui()
    data = echeancier.upcoming(db, employee_id, today)
    return {"aujourdhui": today.isoformat(), "en_retard": [_out(e, today) for e in data["en_retard"]],
            "a_venir": [_out(e, today) for e in data["a_venir"]]}


@router.get("/rappels")
def reminders(employee_id: int | None = None, _: User = Depends(current_user), db: Database = Depends(get_db)) -> list[dict]:
    today = dates.aujourdhui()
    return [_out(e, today) for e in echeancier.reminders(db, employee_id)]


@router.get("/recap")
def recap(employee_id: int | None = None, year: int | None = None, month: int | None = None,
          _: User = Depends(current_user), db: Database = Depends(get_db)) -> dict:
    return echeancier.recap(db, employee_id, year, month)


@router.post("/declarer")
def declare(body: DeclareIn, user: User = Depends(superadmin), db: Database = Depends(get_db)) -> dict:
    report = echeancier.declare_month(db, user.actor, body.year, body.month, body.employee_id)
    return {"periode": report.periode, "declares": report.declares, "ignores": report.ignores,
            "echeances_par_salarie": report.echeances_par_salarie, "message": report.message}


@router.get("/echeances/{echeance_id}/regularite")
def preview_regularity(echeance_id: int, date_paiement: date | None = None, _: User = Depends(current_user),
                       db: Database = Depends(get_db)) -> dict:
    """Aperçu du statut qu'aurait le paiement à cette date (règle d'origine, aucune écriture)."""
    e = echeancier.get_echeance(db, echeance_id)
    if e is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Échéance introuvable.")
    paid_on = (date_paiement or dates.aujourdhui()).isoformat()
    reg = integrity.regularite(paid_on, e.date_echeance)
    return {"date_paiement": paid_on, "regularite": reg, "statut": integrity.statut_paye(reg)}


@router.post("/echeances/{echeance_id}/payer")
def pay(echeance_id: int, body: PayIn, user: User = Depends(superadmin), db: Database = Depends(get_db)) -> dict:
    return _out(echeancier.pay(db, user.actor, echeance_id, body.version, body.date_paiement), dates.aujourdhui())


@router.post("/echeances/{echeance_id}/devalider")
def unpay(echeance_id: int, body: VersionIn, user: User = Depends(superadmin), db: Database = Depends(get_db)) -> dict:
    return _out(echeancier.unpay(db, user.actor, echeance_id, body.version), dates.aujourdhui())


# --- Diagnostic, rapprochement, exports --------------------------------------------------------------

@router.get("/reconciliation")
def reconcile(employee_id: int, _: User = Depends(current_user), db: Database = Depends(get_db)) -> dict:
    """Diagnostic : réconciliation d'origine en SIMULATION (aucune écriture)."""
    result = reconciliation.simulate_employee(db, employee_id)
    return {"compte_rendu": result["compte_rendu"], "corrections": result["corrections"], "erreur": result["erreur"]}


@router.get("/rapprochement")
def reconciliation_with_payroll(employee_id: int, year: int, month: int, _: User = Depends(current_user),
                                db: Database = Depends(get_db)) -> dict:
    return rapprochement.rapprochement(db, employee_id, year, month)


@router.get(f"/exports/{exports.FILE_RECAP}")
def export_recap(employee_id: list[int] | None = Query(default=None), _: User = Depends(current_user),
                 db: Database = Depends(get_db)) -> Response:
    return _file(exports.build_recap_xlsx(_groups(db, employee_id), only_paid=True), XLSX, exports.FILE_RECAP)


@router.get(f"/exports/{exports.FILE_COMPLETE}")
def export_complete(employee_id: list[int] | None = Query(default=None), _: User = Depends(current_user),
                    db: Database = Depends(get_db)) -> Response:
    return _file(exports.build_recap_xlsx(_groups(db, employee_id), only_paid=False), XLSX, exports.FILE_COMPLETE)


@router.get(f"/exports/{exports.FILE_ICS}")
def export_ics(employee_id: list[int] | None = Query(default=None), _: User = Depends(current_user),
               db: Database = Depends(get_db)) -> Response:
    return _file(exports.build_ics(_groups(db, employee_id), only_unpaid=True), "text/calendar", exports.FILE_ICS)
