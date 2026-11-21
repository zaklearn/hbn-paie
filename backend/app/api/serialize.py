"""Conversion des objets métier en JSON : montants en chaînes décimales exactes (jamais de float)."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from datetime import date
from decimal import Decimal

from app.paie.core.formatting import mask
from app.paie.core.models.payroll import STATUTS_LIBELLES
from app.paie.services.master_data import SENSITIVE_EMPLOYEE_FIELDS

MASKED_WITH_SUFFIX = {"cin", "cnss", "compte_bancaire"}   # comme la page Salariés d'origine


def jsonable(value):
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bytes):
        return None
    if is_dataclass(value):
        return {f.name: jsonable(getattr(value, f.name)) for f in fields(value)}
    if isinstance(value, dict):
        return {k: jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


def mask_employee_dict(data: dict | None) -> dict | None:
    """Rôle « user » : CIN, CNSS et compte masqués (••••1234), autres données sensibles retirées."""
    if data is None:
        return None
    out = dict(data)
    for key in SENSITIVE_EMPLOYEE_FIELDS:
        if key not in out:
            continue
        if key in MASKED_WITH_SUFFIX:
            out[key] = mask(out[key] or "")
        else:
            out[key] = None if key == "date_naissance" else ""
    return out


def employee_out(emp, reveal: bool) -> dict:
    data = jsonable(emp)
    return data if reveal else mask_employee_dict(data)


def company_out(company) -> dict | None:
    if company is None:
        return None
    data = jsonable(company)
    data["logo"] = None
    data["has_logo"] = bool(company.logo)
    return data


def payslip_out(slip, reveal: bool) -> dict:
    return {
        "id": slip.id, "employee_id": slip.employee_id, "year": slip.year, "month": slip.month,
        "version": slip.version, "status": slip.status, "status_label": STATUTS_LIBELLES[slip.status],
        "inputs": slip.inputs.to_dict(),
        "result": slip.result.to_dict() if slip.result else None,
        "cumuls": slip.cumuls.to_dict() if slip.cumuls else None,
        "parameter_set_id": slip.parameter_set_id,
        "parameters": slip.parameters.to_dict() if slip.parameters else None,
        "employee_snapshot": slip.employee_snapshot if reveal else mask_employee_dict(slip.employee_snapshot),
        "company_snapshot": slip.company_snapshot,
        "replaces_id": slip.replaces_id, "rectification_reason": slip.rectification_reason,
        "created_at": slip.created_at, "updated_at": slip.updated_at,
        "calculated_at": slip.calculated_at, "closed_at": slip.closed_at, "closed_by": slip.closed_by,
    }


def parameter_set_out(ps) -> dict:
    return {"id": ps.id, "valid_from": ps.valid_from, "label": ps.label, "comment": ps.comment,
            "created_at": ps.created_at, "created_by": ps.created_by, "parameters": ps.params.to_dict()}


def issues_out(issues) -> list[dict]:
    return [{"level": i.level, "field": i.field, "message": i.message} for i in issues]


def user_out(user) -> dict:
    return {"id": user.id, "username": user.username, "display_name": user.display_name, "role": user.role,
            "active": user.active, "created_at": user.created_at, "last_login_at": user.last_login_at}
