"""API REST du module Paie (/api/paie/*) — S2 / US-25.

Chaque route appelle un service porté à l'identique ; aucun calcul ici (R0). Écritures : rôle
superadmin ; lecture et exports : tous les comptes connectés. Montants : chaînes décimales.
"""

from __future__ import annotations

import base64
import binascii
import math
from dataclasses import fields
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from app.api.deps import current_user, get_db, reveal, superadmin
from app.api.serialize import (
    company_out, employee_out, issues_out, jsonable, parameter_set_out, payslip_out,
)
from app.paie.core.models.entities import Company, Employee
from app.paie.core.models.parameters import PayrollParameters
from app.paie.core.models.payroll import MonthlyInput
from app.paie.core.pdf.bulletin import bulletin_filename
from app.paie.repositories.db import Database
from app.paie.services import master_data, payroll, reporting
from app.socle.users import User

router = APIRouter(prefix="/api/paie")
DECIMAL_PATTERN = r"^-?\d{1,12}(\.\d{1,6})?$"


# --- Schémas d'entrée ---------------------------------------------------------------------

class CompanyIn(BaseModel):
    raison_sociale: str = Field(max_length=500)
    adresse: str = Field(default="", max_length=2000)
    ville: str = Field(default="", max_length=255)
    ice: str = Field(default="", max_length=255)
    cnss_employeur: str = Field(default="", max_length=255)
    rc: str = Field(default="", max_length=255)
    identifiant_fiscal: str = Field(default="", max_length=255)
    telephone: str = Field(default="", max_length=255)
    email: str = Field(default="", max_length=255)
    logo_base64: str | None = Field(default=None, description="absent : logo inchangé ; vide : logo retiré")


class EmployeeIn(BaseModel):
    matricule: str = Field(max_length=255)
    nom: str = Field(max_length=500)
    prenom: str = Field(default="", max_length=500)
    date_naissance: date | None = None
    cin: str = Field(default="", max_length=255)
    cnss: str = Field(default="", max_length=255)
    situation_familiale: str = Field(max_length=255)
    nb_personnes_charge: int = 0
    date_embauche: date | None = None
    date_sortie: date | None = None
    fonction: str = Field(default="", max_length=500)
    departement: str = Field(default="", max_length=500)
    cimr: str = Field(default="", max_length=255)
    categorie: str = Field(default="", max_length=500)
    banque: str = Field(default="", max_length=500)
    compte_bancaire: str = Field(default="", max_length=255)
    adresse: str = Field(default="", max_length=2000)
    mode_paiement: str = Field(max_length=255)
    actif: bool = True


class InputsIn(BaseModel):
    """Saisie mensuelle : chaque montant en chaîne décimale (jamais de flottant)."""
    salaire_base: str = Field(default="0", pattern=DECIMAL_PATTERN)
    jours_declares: str = Field(default="0", pattern=DECIMAL_PATTERN)
    heures_sup: str = Field(default="0", pattern=DECIMAL_PATTERN)
    prime_panier: str = Field(default="0", pattern=DECIMAL_PATTERN)
    indemnite_transport: str = Field(default="0", pattern=DECIMAL_PATTERN)
    indemnite_representation: str = Field(default="0", pattern=DECIMAL_PATTERN)
    autre_prime: str = Field(default="0", pattern=DECIMAL_PATTERN)
    conges_reliquat: str = Field(default="0", pattern=DECIMAL_PATTERN)
    conges_acquis: str = Field(default="0", pattern=DECIMAL_PATTERN)
    conges_pris: str = Field(default="0", pattern=DECIMAL_PATTERN)

    def to_model(self) -> MonthlyInput:
        return MonthlyInput.from_dict(self.model_dump())


class PeriodInputsIn(BaseModel):
    employee_id: int
    year: int
    month: int
    inputs: InputsIn


class ParameterVersionIn(BaseModel):
    year: int
    month: int
    parameters: dict
    label: str = Field(default="", max_length=500)
    comment: str = Field(max_length=2000)


class ActiveIn(BaseModel):
    active: bool


class CloseIn(BaseModel):
    confirm_warnings: bool = False


class RectificationIn(BaseModel):
    reason: str = Field(max_length=2000)


# --- Utilitaires --------------------------------------------------------------------------

def _payslip_or_404(db: Database, payslip_id: int):
    slip = payroll.get_payslip(db, payslip_id)
    if slip is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Paie introuvable.")
    return slip


def _employee_or_404(db: Database, employee_id: int) -> Employee:
    emp = master_data.get_employee(db, employee_id)
    if emp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Salarié introuvable.")
    return emp


def _logo(db: Database) -> bytes | None:
    company = master_data.get_company(db)
    return company.logo if company else None


def _pdf(content: bytes, filename: str) -> Response:
    return Response(content, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def _cell(value):
    """Cellule des récapitulatifs d'origine (pandas, flottants) -> chaîne décimale exacte."""
    if isinstance(value, float):
        if math.isnan(value):
            return None
        return str(Decimal(repr(value)))
    if hasattr(value, "item"):          # entiers numpy
        return value.item()
    return value


def _records(df) -> list[dict]:
    return [{k: _cell(v) for k, v in row.items()} for row in df.to_dict(orient="records")]


def _suffix(year: int, month: int | None) -> str:
    return f"{year}" + (f"-{month:02d}" if month else "")


# --- Référentiels (libellés d'origine du noyau) ---------------------------------------------

@router.get("/referentiels")
def referentiels(_: User = Depends(current_user)) -> dict:
    from app.paie.core.models.entities import MODES_PAIEMENT, SITUATIONS_FAMILIALES
    from app.paie.core.models.parameters import METHODES_TOTAUX
    from app.paie.core.models.payroll import MOIS_FR, STATUTS_LIBELLES

    return {"situations_familiales": list(SITUATIONS_FAMILIALES), "modes_paiement": list(MODES_PAIEMENT),
            "mois": list(MOIS_FR), "statuts": STATUTS_LIBELLES, "methodes_totaux": dict(METHODES_TOTAUX)}


# --- Entreprise ---------------------------------------------------------------------------

@router.get("/entreprise")
def get_company(_: User = Depends(current_user), db: Database = Depends(get_db)) -> dict | None:
    return company_out(master_data.get_company(db))


@router.put("/entreprise")
def save_company(body: CompanyIn, user: User = Depends(superadmin), db: Database = Depends(get_db)) -> dict:
    current = master_data.get_company(db)
    if body.logo_base64 is None:
        logo = current.logo if current else None
    elif body.logo_base64 == "":
        logo = None
    else:
        try:
            logo = base64.b64decode(body.logo_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Logo : base64 invalide.") from exc
    company = Company(**body.model_dump(exclude={"logo_base64"}), logo=logo)
    issues = master_data.save_company(db, user.actor, company)
    return {"company": company_out(master_data.get_company(db)), "issues": issues_out(issues)}


# --- Salariés -----------------------------------------------------------------------------

@router.get("/salaries")
def list_employees(active_only: bool = False, search: str = "", user: User = Depends(current_user),
                   db: Database = Depends(get_db)) -> list[dict]:
    return [employee_out(e, reveal(user)) for e in master_data.list_employees(db, active_only, search)]


@router.post("/salaries", status_code=201)
def create_employee(body: EmployeeIn, user: User = Depends(superadmin), db: Database = Depends(get_db)) -> dict:
    employee_id, issues = master_data.create_employee(db, user.actor, Employee(**body.model_dump()))
    return {"employee": employee_out(master_data.get_employee(db, employee_id), True), "issues": issues_out(issues)}


@router.get("/salaries/{employee_id}")
def get_employee(employee_id: int, user: User = Depends(current_user), db: Database = Depends(get_db)) -> dict:
    return employee_out(_employee_or_404(db, employee_id), reveal(user))


@router.put("/salaries/{employee_id}")
def update_employee(employee_id: int, body: EmployeeIn, user: User = Depends(superadmin),
                    db: Database = Depends(get_db)) -> dict:
    _employee_or_404(db, employee_id)
    issues = master_data.update_employee(db, user.actor, Employee(**body.model_dump(), id=employee_id))
    return {"employee": employee_out(master_data.get_employee(db, employee_id), True), "issues": issues_out(issues)}


@router.post("/salaries/{employee_id}/activation")
def set_employee_active(employee_id: int, body: ActiveIn, user: User = Depends(superadmin),
                        db: Database = Depends(get_db)) -> dict:
    master_data.set_employee_active(db, user.actor, employee_id, body.active)
    return employee_out(master_data.get_employee(db, employee_id), True)


# --- Paramètres (versions datées, jamais modifiées) ----------------------------------------

@router.get("/parametres")
def list_parameter_sets(_: User = Depends(current_user), db: Database = Depends(get_db)) -> list[dict]:
    return [parameter_set_out(ps) for ps in master_data.list_parameter_sets(db)]


@router.get("/parametres/en-vigueur")
def parameters_for_period(year: int, month: int, _: User = Depends(current_user),
                          db: Database = Depends(get_db)) -> dict | None:
    ps = master_data.parameters_for_period(db, year, month)
    return parameter_set_out(ps) if ps else None


@router.post("/parametres", status_code=201)
def create_parameter_version(body: ParameterVersionIn, user: User = Depends(superadmin),
                             db: Database = Depends(get_db)) -> dict:
    try:
        params = PayrollParameters.from_dict(body.parameters)
    except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Paramètres incomplets ou invalides.") from exc
    issues = master_data.create_parameter_version(db, user.actor, body.year, body.month, params,
                                                  body.label, body.comment)
    return {"issues": issues_out(issues)}


# --- Saisie, aperçu, brouillon -----------------------------------------------------------------

@router.get("/saisie/preremplissage")
def prefill(employee_id: int, year: int, month: int, _: User = Depends(current_user),
            db: Database = Depends(get_db)) -> dict:
    p = payroll.prefill_inputs(db, employee_id, year, month)
    return {"inputs": p.inputs.to_dict(), "source": p.source, "warnings": issues_out(p.warnings)}


@router.post("/saisie/controle")
def check_inputs(body: PeriodInputsIn, _: User = Depends(current_user), db: Database = Depends(get_db)) -> dict:
    return {"issues": issues_out(payroll.check_inputs(db, body.employee_id, body.year, body.month,
                                                      body.inputs.to_model()))}


@router.post("/apercu")
def preview(body: PeriodInputsIn, _: User = Depends(current_user), db: Database = Depends(get_db)) -> dict:
    """Aperçu instantané : calculé par le noyau, rien n'est enregistré."""
    _employee_or_404(db, body.employee_id)
    p = payroll.preview(db, body.employee_id, body.year, body.month, body.inputs.to_model())
    return {"result": p.result.to_dict(), "cumuls": p.cumuls.to_dict(),
            "parameter_set": {"id": p.parameter_set.id, "valid_from": p.parameter_set.valid_from,
                              "label": p.parameter_set.label}}


@router.post("/brouillons")
def save_draft(body: PeriodInputsIn, user: User = Depends(superadmin), db: Database = Depends(get_db)) -> dict:
    payslip_id, issues = payroll.save_draft(db, user.actor, body.employee_id, body.year, body.month,
                                            body.inputs.to_model())
    return {"payslip": payslip_out(payroll.get_payslip(db, payslip_id), True), "issues": issues_out(issues)}


# --- Paies ---------------------------------------------------------------------------------

@router.get("/paies")
def list_payslips(year: int | None = None, month: int | None = None, employee_id: int | None = None,
                  status_: list[str] | None = Query(default=None, alias="status"),
                  user: User = Depends(current_user), db: Database = Depends(get_db)) -> list[dict]:
    slips = payroll.list_payslips(db, year=year, month=month, employee_id=employee_id,
                                  statuses=tuple(status_) if status_ else None)
    return [payslip_out(s, reveal(user)) for s in slips]


@router.get("/paies/courante")
def current_payslip(employee_id: int, year: int, month: int, user: User = Depends(current_user),
                    db: Database = Depends(get_db)) -> dict | None:
    slip = payroll.current_payslip(db, employee_id, year, month)
    return payslip_out(slip, reveal(user)) if slip else None


@router.get("/paies/versions")
def versions(employee_id: int, year: int, month: int, user: User = Depends(current_user),
             db: Database = Depends(get_db)) -> list[dict]:
    return [payslip_out(s, reveal(user)) for s in payroll.list_versions(db, employee_id, year, month)]


@router.get("/paies/{payslip_id}")
def get_payslip(payslip_id: int, user: User = Depends(current_user), db: Database = Depends(get_db)) -> dict:
    return payslip_out(_payslip_or_404(db, payslip_id), reveal(user))


@router.post("/paies/{payslip_id}/calcul")
def calculate(payslip_id: int, user: User = Depends(superadmin), db: Database = Depends(get_db)) -> dict:
    return payslip_out(payroll.calculate(db, user.actor, payslip_id), True)


@router.get("/paies/{payslip_id}/controles")
def closure_checks(payslip_id: int, _: User = Depends(current_user), db: Database = Depends(get_db)) -> dict:
    return {"issues": issues_out(payroll.closure_checks(db, payslip_id))}


@router.post("/paies/{payslip_id}/cloture")
def close(payslip_id: int, body: CloseIn, user: User = Depends(superadmin), db: Database = Depends(get_db)) -> dict:
    closed = payroll.close(db, user.actor, payslip_id, confirm_warnings=body.confirm_warnings, logo=_logo(db))
    document = payroll.get_document(db, closed.id)
    return {"payslip": payslip_out(closed, True),
            "document": {"filename": document.filename, "sha256": document.sha256}}


@router.post("/paies/{payslip_id}/rectification", status_code=201)
def open_rectification(payslip_id: int, body: RectificationIn, user: User = Depends(superadmin),
                       db: Database = Depends(get_db)) -> dict:
    new_id = payroll.open_rectification(db, user.actor, payslip_id, body.reason)
    return payslip_out(payroll.get_payslip(db, new_id), True)


@router.delete("/paies/{payslip_id}")
def delete_draft(payslip_id: int, user: User = Depends(superadmin), db: Database = Depends(get_db)) -> dict:
    payroll.delete_draft(db, user.actor, payslip_id)
    return {"ok": True}


@router.get("/paies/{payslip_id}/pdf-provisoire")
def provisional_pdf(payslip_id: int, _: User = Depends(current_user), db: Database = Depends(get_db)) -> Response:
    slip = _payslip_or_404(db, payslip_id)
    content = payroll.provisional_pdf(db, payslip_id, _logo(db))
    return _pdf(content, bulletin_filename(slip).replace(".pdf", "_PROVISOIRE.pdf"))


@router.get("/paies/{payslip_id}/bulletin")
def document(payslip_id: int, _: User = Depends(current_user), db: Database = Depends(get_db)) -> Response:
    doc = payroll.get_document(db, payslip_id)
    if doc is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Aucun bulletin archivé pour cette paie.")
    return _pdf(doc.content, doc.filename)


# --- Tableau de bord, journal, récapitulatifs, exports ---------------------------------------

@router.get("/mois")
def month_payroll(year: int, month: int, _: User = Depends(current_user), db: Database = Depends(get_db)) -> list[dict]:
    """Paie du mois : salariés actifs du mois et état de leur paie (agrégat en lecture seule)."""
    from app.socle import dashboard as dash

    return dash.month_payroll(db, year, month)


@router.get("/tableau-de-bord-mois")
def monthly_dashboard(year: int, month: int, _: User = Depends(current_user), db: Database = Depends(get_db)) -> dict:
    """Tableau de bord du mois (maquette 1) : totaux calculés côté serveur."""
    from app.socle import dashboard as dash

    return dash.dashboard(db, year, month)


@router.get("/tableau-de-bord")
def dashboard(year: int, user: User = Depends(current_user), db: Database = Depends(get_db)) -> dict:
    stats = reporting.dashboard(db, year)
    data = jsonable({f.name: getattr(stats, f.name) for f in fields(stats) if f.name != "dernieres_paies"})
    data["dernieres_paies"] = [payslip_out(s, reveal(user)) for s in stats.dernieres_paies]
    return data


@router.get("/journal")
def journal(year: int, month: int | None = None, include_open: bool = False, _: User = Depends(current_user),
            db: Database = Depends(get_db)) -> dict:
    df = reporting.payroll_journal(db, year, month, include_open=include_open)
    return {"journal": _records(df), "monthly": _records(reporting.monthly_summary(df)),
            "annual": _records(reporting.annual_summary(df))}


@router.get("/exports/livre-de-paie.csv")
def export_csv(year: int, month: int | None = None, include_open: bool = False, _: User = Depends(current_user),
               db: Database = Depends(get_db)) -> Response:
    df = reporting.payroll_journal(db, year, month, include_open=include_open)
    return Response(reporting.to_csv_bytes(df), media_type="text/csv",
                    headers={"Content-Disposition": f'attachment; filename="livre_de_paie_{_suffix(year, month)}.csv"'})


@router.get("/exports/recapitulatif.xlsx")
def export_xlsx(year: int, month: int | None = None, include_open: bool = False, _: User = Depends(current_user),
                db: Database = Depends(get_db)) -> Response:
    df = reporting.payroll_journal(db, year, month, include_open=include_open)
    content = reporting.to_excel_bytes({"Livre de paie": df, "Récap mensuel": reporting.monthly_summary(df),
                                        "Récap annuel": reporting.annual_summary(df)})
    return Response(content, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition":
                             f'attachment; filename="recapitulatif_paie_{_suffix(year, month)}.xlsx"'})


@router.get("/audit")
def audit(limit: int = Query(default=500, ge=1, le=5000), action: str | None = None,
          _: User = Depends(current_user), db: Database = Depends(get_db)) -> list[dict]:
    return _records(reporting.audit_log(db, limit=limit, action=action))

