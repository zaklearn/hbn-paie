"""S3 — trésorerie multi-salariés : plans, déclaration, paiement, réconciliation, exports, rapprochement (R0)."""

from __future__ import annotations

import datetime as dt
import inspect
import io
from dataclasses import replace
from decimal import Decimal

import pdfplumber
import pytest
from openpyxl import load_workbook

from app.core.errors import ConflictError
from app.paie.repositories.db import IntegrityError
from app.paie.services import master_data, payroll
from app.paie.services.demo import DEMO_COMPANY, DEMO_EMPLOYEE, REFERENCE_INPUT
from app.paie.services.errors import PayrollError
from app.tresorerie.legacy import db_gen, integrity, rapport
from app.tresorerie.services import echeancier, exports, rapprochement, reconciliation
from tests.paie.mysql_db import Database

ACTOR = "test"
TODAY = dt.date(2026, 11, 21)
T = db_gen


def employee(matricule, **changes):
    return replace(DEMO_EMPLOYEE, matricule=matricule, cin="", cnss="", id=None, **changes)


@pytest.fixture
def db(tmp_path):
    database = Database(tmp_path / "treso.db")
    database.migrate()
    master_data.ensure_initial_parameters(database)
    master_data.save_company(database, ACTOR, replace(DEMO_COMPANY))
    return database


@pytest.fixture
def trio(db):
    """A : plan d'origine ; B : sort le 05/10/2026 ; C : entre le 15/10/2026 ; plans différents."""
    a, _ = master_data.create_employee(db, ACTOR, employee("0001", date_embauche=dt.date(2026, 7, 1)))
    b, _ = master_data.create_employee(db, ACTOR, employee("0002", nom="SORTANT", date_embauche=dt.date(2025, 1, 1),
                                                          date_sortie=dt.date(2026, 10, 5)))
    c, _ = master_data.create_employee(db, ACTOR, employee("0003", nom="ENTRANT", date_embauche=dt.date(2026, 10, 15)))
    echeancier.create_plan(db, ACTOR, a, "2026-07", 2500, 1500, 2500, 2000, "plan v1 (ezzinecdi)")
    echeancier.create_plan(db, ACTOR, b, "2025-01", 3000, 1800, 3000, 2500)
    echeancier.create_plan(db, ACTOR, c, "2026-10", 1000, 600, 1000, 800)
    return db, a, b, c


def amounts(db, employee_id, year, month):
    return {e.type: e.montant for e in echeancier.list_echeances(db, year, month, employee_id)}


# --- Déclaration ---------------------------------------------------------------------------------

def test_declare_month_for_all_active_employees_with_their_plans(trio):
    db, a, b, c = trio
    report = echeancier.declare_month(db, ACTOR, 2026, 10, today=TODAY)
    assert sorted(report.declares) == ["0001", "0002", "0003"] and report.ignores == []
    assert report.message == "Octobre 2026 : 3 salarié(s), 4 échéances chacun, 0 ignoré(s)."
    assert amounts(db, a, 2026, 10) == {T.T_S1: 2500, T.T_CN: 1500, T.T_S2: 2500, T.T_S3: 2000}
    assert amounts(db, b, 2026, 10) == {T.T_S1: 3000, T.T_CN: 1800, T.T_S2: 3000, T.T_S3: 2500}
    assert amounts(db, c, 2026, 10) == {T.T_S1: 1000, T.T_CN: 600, T.T_S2: 1000, T.T_S3: 800}
    for emp in (a, b, c):
        rows = echeancier.list_echeances(db, employee_id=emp)
        assert [e.n for e in rows] == [1, 2, 3, 4]
        assert [(e.date_echeance, e.type) for e in rows] == [
            ("2026-10-10", T.T_S1), ("2026-10-10", T.T_CN), ("2026-10-20", T.T_S2), ("2026-10-30", T.T_S3)]
        assert all(e.statut == "Non payé" and e.rappel_j1 == (dt.date.fromisoformat(e.date_echeance)
                                                             - dt.timedelta(days=1)).isoformat() for e in rows)


def test_exit_and_entry_during_month(trio):
    db, a, b, c = trio
    report = echeancier.declare_month(db, ACTOR, 2026, 11, today=TODAY)
    assert sorted(report.declares) == ["0001", "0003"]          # B est sorti en octobre
    assert echeancier.list_echeances(db, 2026, 11, b) == []
    report = echeancier.declare_month(db, ACTOR, 2026, 9, today=TODAY)
    assert sorted(report.declares) == ["0001", "0002"]          # C n'est pas encore entré
    assert echeancier.list_echeances(db, 2026, 9, c) == []


def test_anti_duplicate_per_employee(trio):
    db, a, _, _ = trio
    echeancier.declare_month(db, ACTOR, 2026, 10, employee_id=a, today=TODAY)
    report = echeancier.declare_month(db, ACTOR, 2026, 10, today=TODAY)
    assert sorted(report.declares) == ["0002", "0003"]
    assert report.ignores == [{"matricule": "0001", "raison": "« Octobre 2026 » déjà déclaré"}]
    with pytest.raises(PayrollError, match="déjà déclaré"):
        echeancier.declare_month(db, ACTOR, 2026, 10, employee_id=a, today=TODAY)
    assert len(echeancier.list_echeances(db, 2026, 10, a)) == 4


def test_plan_required(db):
    e, _ = master_data.create_employee(db, ACTOR, employee("0009", date_embauche=dt.date(2026, 1, 1)))
    report = echeancier.declare_month(db, ACTOR, 2026, 10, today=TODAY)
    assert report.ignores == [{"matricule": "0009", "raison": "aucun plan de versement en vigueur"}]
    with pytest.raises(PayrollError, match="aucun plan"):
        echeancier.declare_month(db, ACTOR, 2026, 10, employee_id=e, today=TODAY)


def test_february_and_31_day_months(trio):
    db, a, _, _ = trio
    echeancier.declare_month(db, ACTOR, 2027, 2, employee_id=a, today=TODAY)
    s3 = [e for e in echeancier.list_echeances(db, 2027, 2, a) if e.type == T.T_S3][0]
    assert s3.date_echeance == "2027-02-28"                    # db_gen d'origine : min(30, fin de mois)


def test_renumbering_per_employee_like_original(trio):
    db, a, _, c = trio
    echeancier.declare_month(db, ACTOR, 2026, 11, employee_id=a, today=TODAY)
    echeancier.declare_month(db, ACTOR, 2026, 8, employee_id=a, today=TODAY)
    rows = echeancier.list_echeances(db, employee_id=a)
    assert [e.n for e in rows] == list(range(1, 9))
    assert [e.date_echeance for e in sorted(rows, key=lambda e: e.n)][:4] == [
        "2026-08-10", "2026-08-10", "2026-08-20", "2026-08-30"]
    echeancier.declare_month(db, ACTOR, 2026, 11, employee_id=c, today=TODAY)
    assert [e.n for e in echeancier.list_echeances(db, employee_id=c)] == [1, 2, 3, 4]


def test_declaration_range_like_original(trio):
    db, a, _, _ = trio
    assert list(echeancier.declarable_years(TODAY)) == [2024, 2025, 2026, 2027, 2028]
    with pytest.raises(PayrollError, match="plage"):
        echeancier.declare_month(db, ACTOR, 2023, 12, employee_id=a, today=TODAY)
    with pytest.raises(PayrollError, match="plage"):
        echeancier.declare_month(db, ACTOR, 2029, 1, employee_id=a, today=TODAY)


# --- Plans versionnés ------------------------------------------------------------------------------

def test_plan_change_never_alters_existing_echeances(trio):
    db, a, _, _ = trio
    echeancier.declare_month(db, ACTOR, 2026, 11, employee_id=a, today=TODAY)
    before = echeancier.list_echeances(db, employee_id=a)
    echeancier.create_plan(db, ACTOR, a, "2026-12", 2600, 1550, 2600, 2100, "augmentation")
    assert echeancier.list_echeances(db, employee_id=a) == before
    echeancier.declare_month(db, ACTOR, 2026, 12, employee_id=a, today=TODAY)
    assert amounts(db, a, 2026, 12) == {T.T_S1: 2600, T.T_CN: 1550, T.T_S2: 2600, T.T_S3: 2100}
    assert amounts(db, a, 2026, 11) == {T.T_S1: 2500, T.T_CN: 1500, T.T_S2: 2500, T.T_S3: 2000}


def test_plan_versions_are_immutable(trio):
    db, a, _, _ = trio
    with pytest.raises(PayrollError, match="déjà effet"):
        echeancier.create_plan(db, ACTOR, a, "2026-07", 1, 1, 1, 1)
    conn = db.connect()
    try:
        with pytest.raises(IntegrityError, match="immuable"):
            conn.execute("UPDATE payment_plans SET s1 = 1 WHERE employee_id = ?", (a,))
    finally:
        conn.close()
    with pytest.raises(PayrollError, match="AAAA-MM"):
        echeancier.create_plan(db, ACTOR, a, "2026-7", 1, 1, 1, 1)


# --- Payer / dévalider ------------------------------------------------------------------------------

def _first(db, employee_id, year, month, type_):
    return [e for e in echeancier.list_echeances(db, year, month, employee_id) if e.type == type_][0]


def test_pay_statuses_like_original(trio):
    db, a, _, _ = trio
    echeancier.declare_month(db, ACTOR, 2026, 11, employee_id=a, today=TODAY)
    echeancier.declare_month(db, ACTOR, 2026, 12, employee_id=a, today=TODAY)
    s1 = _first(db, a, 2026, 11, T.T_S1)                  # échéance 10/11, payée le 21/11 -> retard
    paid = echeancier.pay(db, ACTOR, s1.id, s1.version, today=TODAY)
    assert (paid.statut, paid.date_paiement, paid.observations) == (
        "Payé – retard", "2026-11-21", "Payé le 21/11/2026 (retard)")
    s3 = _first(db, a, 2026, 11, T.T_S3)                  # 30/11 payé le 21/11 -> à temps
    assert echeancier.pay(db, ACTOR, s3.id, s3.version, today=TODAY).statut == "Payé – à temps"
    dec = _first(db, a, 2026, 12, T.T_S1)                 # décembre payé en novembre -> avance
    assert echeancier.pay(db, ACTOR, dec.id, dec.version, today=TODAY).statut == "Payé – avance"
    s2 = _first(db, a, 2026, 11, T.T_S2)                  # date saisie : le 15/11 pour le 20/11 -> à temps
    assert echeancier.pay(db, ACTOR, s2.id, s2.version, dt.date(2026, 11, 15), today=TODAY).observations == \
        "Payé le 15/11/2026 (à temps)"
    assert paid.version == s1.version + 1


def test_unpay_clears_date_and_observation(trio):
    db, a, _, _ = trio
    echeancier.declare_month(db, ACTOR, 2026, 11, employee_id=a, today=TODAY)
    e = _first(db, a, 2026, 11, T.T_CN)
    e = echeancier.pay(db, ACTOR, e.id, e.version, today=TODAY)
    back = echeancier.unpay(db, ACTOR, e.id, e.version)
    assert (back.statut, back.date_paiement, back.observations) == ("Non payé", None, "")
    with pytest.raises(PayrollError, match="n'est pas payée"):
        echeancier.unpay(db, ACTOR, back.id, back.version)


def test_version_conflict(trio):
    db, a, _, _ = trio
    echeancier.declare_month(db, ACTOR, 2026, 11, employee_id=a, today=TODAY)
    stale = _first(db, a, 2026, 11, T.T_S1)
    echeancier.pay(db, ACTOR, stale.id, stale.version, today=TODAY)       # autre poste
    with pytest.raises(ConflictError, match="modifiée entre-temps"):
        echeancier.unpay(db, ACTOR, stale.id, stale.version)
    with pytest.raises(ConflictError):
        echeancier.pay(db, ACTOR, stale.id, stale.version, today=TODAY)


def test_pay_rules(trio):
    db, a, _, _ = trio
    echeancier.declare_month(db, ACTOR, 2026, 11, employee_id=a, today=TODAY)
    e = _first(db, a, 2026, 11, T.T_S1)
    with pytest.raises(PayrollError, match="postérieure"):
        echeancier.pay(db, ACTOR, e.id, e.version, dt.date(2026, 11, 22), today=TODAY)
    e = echeancier.pay(db, ACTOR, e.id, e.version, today=TODAY)
    with pytest.raises(PayrollError, match="déjà payée"):
        echeancier.pay(db, ACTOR, e.id, e.version, today=TODAY)


def test_paid_status_requires_payment_date_in_database(trio):
    db, a, _, _ = trio
    echeancier.declare_month(db, ACTOR, 2026, 11, employee_id=a, today=TODAY)
    conn = db.connect()
    try:
        with pytest.raises(IntegrityError):
            conn.execute("UPDATE echeances SET statut = 'Payé – à temps' WHERE employee_id = ?", (a,))
        with pytest.raises(IntegrityError):
            conn.execute("UPDATE echeances SET statut = 'Inventé' WHERE employee_id = ?", (a,))
    finally:
        conn.close()


def test_upcoming_and_reminders(trio):
    db, a, b, c = trio
    for m in (10, 11, 12):
        echeancier.declare_month(db, ACTOR, 2026, m, today=TODAY)
    view = echeancier.upcoming(db, today=TODAY)
    assert all(e.date_echeance < "2026-11-21" for e in view["en_retard"])
    assert len(view["a_venir"]) == 6 and all(e.date_echeance >= "2026-11-21" for e in view["a_venir"])
    assert [e.date_echeance for e in view["a_venir"]] == sorted(e.date_echeance for e in view["a_venir"])
    assert len(echeancier.reminders(db, a)) == 12
    stats = echeancier.recap(db, employee_id=a)
    assert stats == {"total_paye": 0, "restant_du": 3 * 8500, "payees": 0, "echeances": 12, "avancement": 0,
                     "regularite": {"à temps": 0, "retard": 0, "avance": 0}}


# --- Réconciliation (US-34) -------------------------------------------------------------------------

def test_reconcile_plan_code_identical_to_original_except_amount_line():
    ours = inspect.getsource(reconciliation.reconcile_plan).splitlines()
    theirs = inspect.getsource(integrity.reconcile).splitlines()
    body_ours = ours[ours.index("    today = today or dt.date.today()"):]
    body_theirs = theirs[theirs.index("    today = today or dt.date.today()"):]
    diff = [(o, t) for o, t in zip(body_ours, body_theirs) if o != t]
    assert len(body_ours) == len(body_theirs)
    assert diff == [('        att_m = montant_attendu(rec["type"], e)',
                     '        att_m = db_gen.MONTANT_TYPE[rec["type"]]')]


def test_reconcile_with_original_scale_equals_original():
    data = db_gen.base_vide()
    for a, m in ((2026, 10), (2026, 8)):
        data, _, _ = db_gen.ajouter_mois(data, a, m)
    data[0]["montant"], data[1]["rappel_j1"] = 1, "X"
    original = integrity.reconcile([dict(r) for r in data], TODAY)
    ported = reconciliation.reconcile_plan([dict(r) for r in data], lambda t, _d: db_gen.MONTANT_TYPE[t], TODAY)
    assert ported == original


def test_simulation_uses_employee_plan_and_writes_nothing(trio):
    db, a, _, c = trio
    plans = echeancier.list_plans(db, c)
    records = db_gen.generer_mois(2026, 10)               # montants du barème d'origine (2 500…)
    records.append(dict(records[0], statut="Payé – à temps", date_paiement="2026-10-12"))   # doublon payé
    snapshot = [dict(r) for r in records]
    result = reconciliation.simulate(records, reconciliation.plan_lookup(plans), TODAY)
    assert records == snapshot                            # entrée inchangée
    assert result["compte_rendu"]["montants_corriges"] == 4 and result["compte_rendu"]["doublons"] == 1
    s1 = [r for r in result["resultat"] if r["type"] == T.T_S1][0]
    assert s1["montant"] == 1000 and s1["statut"] == "Payé – retard"     # le payé prime, statut recalculé
    assert {tuple(c["changements"]) for c in result["corrections"]} >= {("montant",)}
    before = echeancier.list_echeances(db, employee_id=c)
    assert reconciliation.simulate_employee(db, c, TODAY)["corrections"] == []
    assert echeancier.list_echeances(db, employee_id=c) == before


# --- Exports (US-35) ----------------------------------------------------------------------------------

def _values(ws):
    return [[c.value for c in row] for row in ws.iter_rows()]


def test_excel_single_employee_is_original_format(trio):
    db, a, _, _ = trio
    echeancier.declare_month(db, ACTOR, 2026, 11, employee_id=a, today=TODAY)
    emp = master_data.get_employee(db, a)
    records = [e.legacy() for e in echeancier.list_echeances(db, employee_id=a)]
    ours = load_workbook(io.BytesIO(exports.build_recap_xlsx([(emp, records)], only_paid=False))).active
    theirs = load_workbook(io.BytesIO(rapport.build_recap_xlsx(records, only_paid=False))).active
    assert _values(ours) == _values(theirs) and ours.title == "Complet"
    assert [c.value for c in ours[1]] == rapport.COLONNES


def test_excel_one_sheet_per_employee_identical_to_original_sheet(trio):
    db, a, b, c = trio
    echeancier.declare_month(db, ACTOR, 2026, 10, today=TODAY)
    e = _first(db, b, 2026, 10, T.T_S1)
    echeancier.pay(db, ACTOR, e.id, e.version, dt.date(2026, 10, 9), today=TODAY)
    groups = [(master_data.get_employee(db, i), [x.legacy() for x in echeancier.list_echeances(db, employee_id=i)])
              for i in (a, b, c)]
    wb = load_workbook(io.BytesIO(exports.build_recap_xlsx(groups, only_paid=False)))
    assert wb.sheetnames == ["0001 EXEMPLE", "0002 SORTANT", "0003 ENTRANT"]
    for (emp, records), ws in zip(groups, wb.worksheets):
        ref = load_workbook(io.BytesIO(rapport.build_recap_xlsx(records, only_paid=False))).active
        assert _values(ws) == _values(ref)
        assert ws.freeze_panes == ref.freeze_panes == "A2" and ws.auto_filter.ref == ref.auto_filter.ref
        assert [ws.cell(r, 5).number_format for r in range(2, ws.max_row + 1)] == \
            [ref.cell(r, 5).number_format for r in range(2, ref.max_row + 1)]
        assert ws.cell(ws.max_row, 4).value == "TOTAL"
        assert ws.column_dimensions["D"].width == ref.column_dimensions["D"].width
    paid = load_workbook(io.BytesIO(exports.build_recap_xlsx(groups, only_paid=True)))
    assert paid.worksheets[1].cell(paid.worksheets[1].max_row, 5).value == 3000


def test_ics_names_employee_and_keeps_original_events(trio):
    db, a, b, c = trio
    echeancier.declare_month(db, ACTOR, 2026, 10, today=TODAY)
    groups = [(master_data.get_employee(db, i), [x.legacy() for x in echeancier.list_echeances(db, employee_id=i)])
              for i in (a, b, c)]
    ics = exports.build_ics(groups).decode("utf-8")
    assert ics.startswith("BEGIN:VCALENDAR") and ics.endswith("END:VCALENDAR\r\n")
    assert ics.count("BEGIN:VEVENT") == 12 and ics.count("TRIGGER:-PT15H") == 12
    assert ics.count("CATEGORIES:CNSS") == 3 and ics.count("CATEGORIES:SALAIRE") == 9
    unfolded = ics.replace("\r\n ", "")
    assert "SUMMARY:Salarié EXEMPLE · Salaire – 1er versement — 2 500 DH" in unfolded
    assert "SUMMARY:Salarié ENTRANT · Salaire – 1er versement — 1 000 DH" in unfolded
    uids = [l for l in unfolded.split("\r\n") if l.startswith("UID:")]
    assert len(set(uids)) == 12
    assert all(len(line.encode("utf-8")) <= 75 for line in ics.split("\r\n"))


# --- Rapprochement en lecture seule (US-36) et isolation R0 --------------------------------------------

def _payslips_fingerprint(db):
    conn = db.connect()
    try:
        return conn.execute("SELECT * FROM payslips ORDER BY id").fetchall(), \
            conn.execute("SELECT id, sha256 FROM documents ORDER BY id").fetchall()
    finally:
        conn.close()


def _calculated(db, employee_id, month):
    pid, _ = payroll.save_draft(db, ACTOR, employee_id, 2026, month, REFERENCE_INPUT)
    return payroll.calculate(db, ACTOR, pid)


def test_rapprochement_is_read_only_and_matches_demo(trio):
    db, a, _, _ = trio
    rapprochement.register()
    for m in (7, 8, 9):
        echeancier.declare_month(db, ACTOR, 2026, m, employee_id=a, today=TODAY)
        for e in echeancier.list_echeances(db, 2026, m, a):
            echeancier.pay(db, ACTOR, e.id, e.version, dt.date(2026, m, 1), today=TODAY)
        slip = _calculated(db, a, m)
        before = _payslips_fingerprint(db)
        r = rapprochement.rapprochement(db, a, 2026, m)
        assert _payslips_fingerprint(db) == before
        assert r["net_a_payer"] == slip.result.to_dict()["net_a_payer"]          # texte exact du noyau
        assert (Decimal(r["verse_salaire"]), Decimal(r["net_a_payer"]), Decimal(r["ecart_net"])) == (7000, 7000, 0)
        assert (Decimal(r["cnss_versee"]), Decimal(r["cotisations_totales"])) == (1500, Decimal("1513.00"))  # §1
        assert r["versements_complets"] and r["bulletin"]["status"] == "calculee"
        assert [i for i in payroll.closure_checks(db, slip.id) if i.field == "tresorerie"] == []
        payroll.close(db, ACTOR, slip.id, confirm_warnings=True)
        assert rapprochement.rapprochement(db, a, 2026, m)["bulletin"]["status"] == "cloturee"


def _close_september_with(tmp_path, name, pay_salaries: bool):
    db = Database(tmp_path / name)
    db.migrate()
    master_data.ensure_initial_parameters(db)
    master_data.save_company(db, ACTOR, replace(DEMO_COMPANY))
    emp, _ = master_data.create_employee(db, ACTOR, replace(DEMO_EMPLOYEE, id=None))
    echeancier.create_plan(db, ACTOR, emp, "2026-07", 2500, 1500, 2500, 2000)
    for m in (7, 8, 9):
        echeancier.declare_month(db, ACTOR, 2026, m, employee_id=emp, today=TODAY)
        if pay_salaries:
            for e in echeancier.list_echeances(db, 2026, m, emp):
                echeancier.pay(db, ACTOR, e.id, e.version, dt.date(2026, m, 1), today=TODAY)
        slip = _calculated(db, emp, m)
        checks = payroll.closure_checks(db, slip.id)
        if not pay_salaries:
            with pytest.raises(PayrollError, match="avertissements"):
                payroll.close(db, ACTOR, slip.id, confirm_warnings=False)
        closed = payroll.close(db, ACTOR, slip.id, confirm_warnings=True)
    doc = payroll.get_document(db, closed.id)
    with pdfplumber.open(io.BytesIO(doc.content)) as pdf:
        text = [p.extract_text() for p in pdf.pages]
    return closed, checks, text


def test_closure_result_identical_with_and_without_treasury_gap(tmp_path):
    """R0 : clôturer avec ou sans écart de trésorerie donne une paie identique chaîne par chaîne."""
    rapprochement.register()
    ok, checks_ok, text_ok = _close_september_with(tmp_path, "sans_ecart.db", pay_salaries=True)
    gap, checks_gap, text_gap = _close_september_with(tmp_path, "avec_ecart.db", pay_salaries=False)
    assert [i for i in checks_ok if i.field == "tresorerie"] == []
    treso = [i.message for i in checks_gap if i.field == "tresorerie"]
    assert treso == ["Versements incomplets : 0 versement(s) de salaire payé(s) sur 3 (0,00 DH versés).",
                     "Écart de 7 000,00 DH entre les versements de salaire (0,00 DH) et le net à payer (7 000,00 DH)."]
    assert all(i.level == "avertissement" for i in checks_gap if i.field == "tresorerie")
    assert ok.result.to_dict() == gap.result.to_dict()
    assert ok.cumuls.to_dict() == gap.cumuls.to_dict()
    assert ok.inputs.to_dict() == gap.inputs.to_dict() and ok.parameters.to_dict() == gap.parameters.to_dict()
    assert ok.employee_snapshot == gap.employee_snapshot and ok.company_snapshot == gap.company_snapshot
    assert (ok.status, ok.version) == (gap.status, gap.version) == ("cloturee", 1)
    assert text_ok == text_gap


def test_untracked_employee_gets_no_treasury_warning(db):
    rapprochement.register()
    emp, _ = master_data.create_employee(db, ACTOR, replace(DEMO_EMPLOYEE, id=None))
    slip = _calculated(db, emp, 7)
    assert [i for i in payroll.closure_checks(db, slip.id) if i.field == "tresorerie"] == []
