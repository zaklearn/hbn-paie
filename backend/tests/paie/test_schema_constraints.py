"""US-21 / US-22 — tests de violation : chaque contrainte et chaque déclencheur du schéma MySQL.

Les messages des déclencheurs sont ceux de paie-bulletins (db.py, RAISE(ABORT, …)).
"""

from __future__ import annotations

import re
import threading
from dataclasses import replace

import pytest

from app.paie.repositories.db import IntegrityError
from app.paie.services import master_data, payroll

from .conftest import ACTOR, make_employee

MSG_PARAMS = "Une version de paramètres est immuable : créer une nouvelle version."
MSG_CLOSED_UPDATE = "Paie clôturée : modification interdite (passer par une rectification)."
MSG_CLOSED_DELETE = "Paie clôturée : suppression interdite."
MSG_DOC_UPDATE = "Bulletin archivé : modification interdite."
MSG_DOC_DELETE = "Bulletin archivé : suppression interdite."
MSG_AUDIT = "Journal en ajout seul."

TS = "2026-11-21T00:00:00"


def _closed(db, employee_id, ref_input, month=7):
    payslip_id, _ = payroll.save_draft(db, ACTOR, employee_id, 2026, month, ref_input)
    payroll.calculate(db, ACTOR, payslip_id)
    return payroll.close(db, ACTOR, payslip_id, confirm_warnings=True)


def _raw(db, sql, params=()):
    conn = db.connect()
    try:
        return conn.execute(sql, params)
    finally:
        conn.close()


def _insert_employee(db, matricule, cin="", cnss="", **extra):
    cols = {"matricule": matricule, "nom": "X", "situation_familiale": "Célibataire", "cin": cin,
            "cnss": cnss, "created_at": TS, "updated_at": TS, **extra}
    names = ", ".join(cols)
    _raw(db, f"INSERT INTO employees ({names}) VALUES ({', '.join('?' for _ in cols)})", list(cols.values()))


# --- Déclencheurs (6), mêmes messages que l'original ------------------------------------------

def test_trigger_parameter_sets_immutable(db):
    with pytest.raises(IntegrityError, match=re.escape(MSG_PARAMS)):
        _raw(db, "UPDATE parameter_sets SET label = ?", ("modifié",))


def test_trigger_closed_payslip_update_refused(setup, ref_input):
    db, employee_id = setup
    closed = _closed(db, employee_id, ref_input)
    for column, value in (("inputs", "{}"), ("result", "{}"), ("closed_by", "x"), ("status", "calculee")):
        with pytest.raises(IntegrityError, match=re.escape(MSG_CLOSED_UPDATE)):
            _raw(db, f"UPDATE payslips SET {column} = ? WHERE id = ?", (value, closed.id))


def test_trigger_allows_only_closed_to_replaced_without_other_change(setup, ref_input):
    db, employee_id = setup
    closed = _closed(db, employee_id, ref_input)
    with pytest.raises(IntegrityError, match=re.escape(MSG_CLOSED_UPDATE)):
        _raw(db, "UPDATE payslips SET status = 'remplacee', inputs = '{}' WHERE id = ?", (closed.id,))
    _raw(db, "UPDATE payslips SET status = 'remplacee' WHERE id = ?", (closed.id,))
    with pytest.raises(IntegrityError, match=re.escape(MSG_CLOSED_UPDATE)):     # une paie remplacée est figée
        _raw(db, "UPDATE payslips SET status = 'cloturee' WHERE id = ?", (closed.id,))


def test_trigger_closed_or_replaced_payslip_delete_refused(setup, ref_input):
    db, employee_id = setup
    closed = _closed(db, employee_id, ref_input)
    with pytest.raises(IntegrityError, match=re.escape(MSG_CLOSED_DELETE)):
        _raw(db, "DELETE FROM payslips WHERE id = ?", (closed.id,))
    _raw(db, "UPDATE payslips SET status = 'remplacee' WHERE id = ?", (closed.id,))
    with pytest.raises(IntegrityError, match=re.escape(MSG_CLOSED_DELETE)):
        _raw(db, "DELETE FROM payslips WHERE id = ?", (closed.id,))


def test_trigger_documents_immutable_and_not_deletable(setup, ref_input):
    db, employee_id = setup
    closed = _closed(db, employee_id, ref_input)
    with pytest.raises(IntegrityError, match=re.escape(MSG_DOC_UPDATE)):
        _raw(db, "UPDATE documents SET filename = ? WHERE payslip_id = ?", ("x.pdf", closed.id))
    with pytest.raises(IntegrityError, match=re.escape(MSG_DOC_DELETE)):
        _raw(db, "DELETE FROM documents WHERE payslip_id = ?", (closed.id,))


def test_trigger_audit_append_only(setup, ref_input):
    db, _ = setup
    with pytest.raises(IntegrityError, match=re.escape(MSG_AUDIT)):
        _raw(db, "UPDATE audit_log SET actor = ?", ("x",))


# --- Unicité -----------------------------------------------------------------------------------

def test_unique_matricule(db):
    _insert_employee(db, "M1")
    with pytest.raises(IntegrityError):
        _insert_employee(db, "M1")


def test_matricule_is_case_sensitive_like_sqlite(db):
    _insert_employee(db, "ab1")
    _insert_employee(db, "AB1")   # collation binaire : distincts, comme en SQLite


def test_unique_cin_and_cnss_only_when_filled(db):
    _insert_employee(db, "M1", cin="", cnss="")
    _insert_employee(db, "M2", cin="", cnss="")        # vides : plusieurs autorisés
    _insert_employee(db, "M3", cin="AB1", cnss="111")
    with pytest.raises(IntegrityError):
        _insert_employee(db, "M4", cin="AB1")
    with pytest.raises(IntegrityError):
        _insert_employee(db, "M5", cnss="111")


def test_unique_closed_payslip_per_month(setup, ref_input):
    db, employee_id = setup
    _closed(db, employee_id, ref_input)
    with pytest.raises(IntegrityError):
        _raw(db, "INSERT INTO payslips (employee_id, year, month, version, status, inputs, created_at, "
                 "updated_at) VALUES (?, 2026, 7, 5, 'cloturee', '{}', 'x', 'x')", (employee_id,))


def test_unique_version_per_month(setup, ref_input):
    db, employee_id = setup
    payroll.save_draft(db, ACTOR, employee_id, 2026, 7, ref_input)
    with pytest.raises(IntegrityError):
        _raw(db, "INSERT INTO payslips (employee_id, year, month, version, status, inputs, created_at, "
                 "updated_at) VALUES (?, 2026, 7, 1, 'remplacee', '{}', 'x', 'x')", (employee_id,))


def test_unique_parameter_set_valid_from(db, params):
    with pytest.raises(IntegrityError):
        _raw(db, "INSERT INTO parameter_sets (valid_from, data, created_at) VALUES ('2000-01', '{}', ?)", (TS,))


# --- CHECK, JSON, clés étrangères ---------------------------------------------------------------

@pytest.mark.parametrize("column, value", [("nb_personnes_charge", -1), ("actif", 2)])
def test_employee_checks(db, column, value):
    with pytest.raises(IntegrityError):
        _insert_employee(db, "M9", **{column: value})


def test_company_single_row(db):
    with pytest.raises(IntegrityError):
        _raw(db, "INSERT INTO company (id, raison_sociale, updated_at) VALUES (2, 'X', ?)", (TS,))


@pytest.mark.parametrize("column, value", [
    ("year", 1999), ("month", 13), ("version", 0), ("status", "inconnu"), ("inputs", "pas du json")])
def test_payslip_checks(setup, column, value):
    db, employee_id = setup
    row = {"employee_id": employee_id, "year": 2026, "month": 7, "version": 1, "status": "brouillon",
           "inputs": "{}", "created_at": TS, "updated_at": TS, column: value}
    with pytest.raises(IntegrityError):
        _raw(db, f"INSERT INTO payslips ({', '.join(row)}) VALUES ({', '.join('?' for _ in row)})",
             list(row.values()))


def test_payslip_requires_existing_employee(db):
    with pytest.raises(IntegrityError):
        _raw(db, "INSERT INTO payslips (employee_id, year, month, version, status, inputs, created_at, "
                 "updated_at) VALUES (999, 2026, 7, 1, 'brouillon', '{}', 'x', 'x')")


def test_amounts_stored_as_exact_text(setup, ref_input):
    """R0.2 : les montants restent du texte décimal exact (colonnes LONGTEXT, aucune colonne arrondissante)."""
    db, employee_id = setup
    closed = _closed(db, employee_id, ref_input)
    row = _raw(db, "SELECT result, inputs FROM payslips WHERE id = ?", (closed.id,)).fetchone()
    assert '"salaire_base": "5436.51"' in row["inputs"]
    types = {r["DATA_TYPE"] for r in _raw(
        db, "SELECT DATA_TYPE FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
            "AND TABLE_NAME IN ('payslips', 'parameter_sets', 'employees', 'company', 'documents', 'audit_log')")}
    assert not types & {"decimal", "float", "double"}


# --- Verrou FOR UPDATE (US-22) -------------------------------------------------------------------

def test_concurrent_drafts_for_same_month_are_serialized(setup, ref_input):
    """Deux enregistrements simultanés du même mois : sérialisés (une seule version de travail), comme BEGIN IMMEDIATE."""
    db, employee_id = setup
    barrier, errors, ids = threading.Barrier(4), [], []

    def worker(i):
        try:
            barrier.wait()
            pid, _ = payroll.save_draft(db, ACTOR, employee_id, 2026, 7,
                                        replace(ref_input, heures_sup=ref_input.heures_sup + i))
            ids.append(pid)
        except Exception as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert len(set(ids)) == 1
    assert len(payroll.list_versions(db, employee_id, 2026, 7)) == 1


def test_lock_is_released_after_transaction(setup, ref_input):
    db, employee_id = setup
    other, _ = master_data.create_employee(db, ACTOR, make_employee("0002"))
    payroll.save_draft(db, ACTOR, employee_id, 2026, 7, ref_input)
    payroll.save_draft(db, ACTOR, other, 2026, 7, ref_input)
    assert len(payroll.list_payslips(db, year=2026, month=7)) == 2
