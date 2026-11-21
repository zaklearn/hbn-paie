"""Échéancier multi-salariés : plans de versement, déclaration d'un mois, paiement, dévalidation.

Extension validée (conception §2, R1) : chaque échéance appartient à un salarié (``employee_id``) et
son montant vient du **plan de versement du salarié en vigueur à la date d'échéance**. Tout le reste
est la logique d'origine (``app.tresorerie.legacy``), appelée sans modification :

- gabarit (jours 10/10/20/30-ou-fin, types, ordre, rappel J-1) : ``db_gen.generer_mois`` ;
- numérotation ``n`` (par salarié) : ``db_gen.trier_renumeroter`` ;
- statuts et régularité au jour : ``integrity.regularite`` / ``integrity.statut_paye`` ;
- badge « en retard » : ``integrity.est_en_retard`` (calculé, jamais stocké).

La trésorerie ne touche jamais aux tables de paie (R0.2).
"""

from __future__ import annotations

import calendar
import datetime as dt
from dataclasses import dataclass

from app.core.errors import ConflictError, NotFoundError
from app.paie.core.models.entities import Employee
from app.paie.repositories import repos
from app.paie.repositories.db import Database
from app.paie.services.errors import PayrollError
from app.tresorerie.legacy import dates, db_gen, integrity

PLAN_FIELD = {db_gen.T_S1: "s1", db_gen.T_CN: "cnss", db_gen.T_S2: "s2", db_gen.T_S3: "s3"}
SALARY_TYPES = (db_gen.T_S1, db_gen.T_S2, db_gen.T_S3)
LEGACY_KEYS = ("n", "date_echeance", "mois", "type", "montant", "statut", "rappel_j1", "observations",
               "date_paiement")


# --- Plans de versement (versionnés par date d'effet, immuables) ---------------------------------

@dataclass(frozen=True)
class PaymentPlan:
    id: int
    employee_id: int
    valid_from: str          # AAAA-MM
    s1: int
    cnss: int
    s2: int
    s3: int
    comment: str
    created_at: str
    created_by: str

    def montant(self, type_: str) -> int:
        return getattr(self, PLAN_FIELD[type_])

    @property
    def total_salaire(self) -> int:
        return self.s1 + self.s2 + self.s3


def _plan(row) -> PaymentPlan:
    return PaymentPlan(row["id"], row["employee_id"], row["valid_from"], row["s1"], row["cnss"], row["s2"],
                       row["s3"], row["comment"], row["created_at"], row["created_by"])


def _period(value: str) -> str:
    try:
        year, month = value.split("-")
        if len(year) == 4 and len(month) == 2 and 2000 <= int(year) <= 2100 and 1 <= int(month) <= 12:
            return value
    except ValueError:
        pass
    raise PayrollError("Date d'effet invalide : format AAAA-MM attendu.")


def plan_for_period(conn, employee_id: int, period: str) -> PaymentPlan | None:
    """Plan en vigueur pour « AAAA-MM » : le plus récent dont la date d'effet ≤ période."""
    row = conn.execute("SELECT * FROM payment_plans WHERE employee_id = ? AND valid_from <= ? "
                       "ORDER BY valid_from DESC LIMIT 1", (employee_id, period)).fetchone()
    return _plan(row) if row else None


def plan_for_date(conn, employee_id: int, date_iso: str) -> PaymentPlan | None:
    return plan_for_period(conn, employee_id, date_iso[:7])


def list_plans(db: Database, employee_id: int) -> list[PaymentPlan]:
    with db.read() as conn:
        rows = conn.execute("SELECT * FROM payment_plans WHERE employee_id = ? ORDER BY valid_from DESC",
                            (employee_id,))
        return [_plan(r) for r in rows]


def create_plan(db: Database, actor: str, employee_id: int, valid_from: str, s1: int, cnss: int, s2: int,
                s3: int, comment: str = "") -> int:
    """Nouvelle version du plan. N'affecte jamais une échéance déjà déclarée (montant figé à la déclaration)."""
    valid_from = _period(valid_from)
    amounts = {"s1": s1, "cnss": cnss, "s2": s2, "s3": s3}
    for name, value in amounts.items():
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise PayrollError(f"Montant {name.upper()} invalide : entier positif en DH attendu.")
    with db.transaction() as conn:
        repos.lock_employee(conn, employee_id)
        if repos.get_employee(conn, employee_id) is None:
            raise NotFoundError("Salarié introuvable.")
        if conn.execute("SELECT id FROM payment_plans WHERE employee_id = ? AND valid_from = ?",
                        (employee_id, valid_from)).fetchone():
            raise PayrollError(f"Une version du plan prend déjà effet en {valid_from}. Choisissez un autre mois.")
        cur = conn.execute(
            "INSERT INTO payment_plans (employee_id, valid_from, s1, cnss, s2, s3, comment, created_at, created_by) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (employee_id, valid_from, s1, cnss, s2, s3, comment.strip(), repos.now_iso(), actor))
        plan_id = int(cur.lastrowid)
        repos.log(conn, actor, "tresorerie.plan.creation", "payment_plan", plan_id,
                  {"employee_id": employee_id, "effet": valid_from, **amounts})
    return plan_id


# --- Échéances -----------------------------------------------------------------------------------

@dataclass(frozen=True)
class Echeance:
    id: int
    employee_id: int
    n: int
    date_echeance: str
    mois: str
    type: str
    montant: int
    statut: str
    rappel_j1: str
    observations: str
    date_paiement: str | None
    annee: int
    mois_num: int
    version: int
    source_ref: str

    def legacy(self) -> dict:
        """Enregistrement au format d'origine (9 champs) pour les fonctions du legacy."""
        return {k: getattr(self, k) for k in LEGACY_KEYS}


def _echeance(row) -> Echeance:
    return Echeance(row["id"], row["employee_id"], row["n"], row["date_echeance"], row["mois"], row["type"],
                    row["montant"], row["statut"], row["rappel_j1"], row["observations"], row["date_paiement"],
                    row["annee"], row["mois_num"], row["version"], row["source_ref"])


def get_echeance(db: Database, echeance_id: int) -> Echeance | None:
    with db.read() as conn:
        row = conn.execute("SELECT * FROM echeances WHERE id = ?", (echeance_id,)).fetchone()
    return _echeance(row) if row else None


def list_echeances(db: Database, year: int | None = None, month: int | None = None,
                   employee_id: int | None = None, paid: bool | None = None) -> list[Echeance]:
    sql, args = "SELECT * FROM echeances WHERE 1 = 1", []
    for column, value in (("annee", year), ("mois_num", month), ("employee_id", employee_id)):
        if value is not None:
            sql += f" AND {column} = ?"
            args.append(value)
    if paid is True:
        sql += " AND statut <> ?"
        args.append(db_gen.STATUT_NON_PAYE)
    elif paid is False:
        sql += " AND statut = ?"
        args.append(db_gen.STATUT_NON_PAYE)
    sql += " ORDER BY employee_id, n"
    with db.read() as conn:
        return [_echeance(r) for r in conn.execute(sql, args)]


def _renumber(conn, employee_id: int) -> None:
    """Numérotation ``n`` par salarié, triée comme l'original (date d'échéance, ordre du type)."""
    rows = [_echeance(r) for r in conn.execute("SELECT * FROM echeances WHERE employee_id = ?", (employee_id,))]
    records = [dict(e.legacy(), _id=e.id) for e in rows]
    for rec in db_gen.trier_renumeroter(records):
        current = next(e for e in rows if e.id == rec["_id"])
        if current.n != rec["n"]:
            conn.execute("UPDATE echeances SET n = ? WHERE id = ?", (rec["n"], rec["_id"]))


def employed_during(emp: Employee, year: int, month: int) -> bool:
    """Actif sur le mois : embauche ≤ fin de mois, sortie ≥ début de mois, fiche active."""
    first = dt.date(year, month, 1)
    last = dt.date(year, month, calendar.monthrange(year, month)[1])
    if not emp.actif:
        return False
    if emp.date_embauche and emp.date_embauche > last:
        return False
    if emp.date_sortie and emp.date_sortie < first:
        return False
    return True


def declarable_years(today: dt.date) -> range:
    """Années proposées par l'original pour « Régularisation / nouveau mois » : range(an − 2, an + 3)."""
    return range(today.year - 2, today.year + 3)


@dataclass(frozen=True)
class DeclarationReport:
    periode: str
    declares: list[str]                 # matricules
    ignores: list[dict]                 # {"matricule", "raison"}
    echeances_par_salarie: int = 4

    @property
    def message(self) -> str:
        return (f"{db_gen.mois_label(*self._ym)} : {len(self.declares)} salarié(s), "
                f"{self.echeances_par_salarie} échéances chacun, {len(self.ignores)} ignoré(s).")

    @property
    def _ym(self) -> tuple[int, int]:
        y, m = self.periode.split("-")
        return int(y), int(m)


def declare_month(db: Database, actor: str, year: int, month: int, employee_id: int | None = None,
                  today: dt.date | None = None) -> DeclarationReport:
    """Déclare un mois : 4 échéances par salarié actif (ou pour un seul salarié), anti-doublon par salarié."""
    today = today or dates.aujourdhui()
    if year not in declarable_years(today) or not 1 <= month <= 12:
        raise PayrollError("Période hors de la plage de déclaration (année − 2 à année + 2).")
    period = f"{year:04d}-{month:02d}"
    declared, ignored = [], []
    with db.transaction() as conn:
        if employee_id is not None:
            emp = repos.get_employee(conn, employee_id)
            if emp is None:
                raise NotFoundError("Salarié introuvable.")
            candidates = [emp]
        else:
            candidates = [e for e in repos.list_employees(conn) if employed_during(e, year, month)]
        for emp in candidates:
            repos.lock_employee(conn, emp.id)
            if not employed_during(emp, year, month):
                reason = "salarié non actif sur ce mois (embauche, sortie ou fiche désactivée)"
            elif conn.execute("SELECT id FROM echeances WHERE employee_id = ? AND annee = ? AND mois_num = ? LIMIT 1",
                              (emp.id, year, month)).fetchone():
                reason = f"« {db_gen.mois_label(year, month)} » déjà déclaré"
            elif (plan := plan_for_period(conn, emp.id, period)) is None:
                reason = "aucun plan de versement en vigueur"
            else:
                reason = None
            if reason:
                if employee_id is not None:
                    raise PayrollError(f"Salarié {emp.matricule} : {reason}.")
                ignored.append({"matricule": emp.matricule, "raison": reason})
                continue
            ts = repos.now_iso()
            for rec in db_gen.generer_mois(year, month):
                conn.execute(
                    "INSERT INTO echeances (employee_id, n, date_echeance, mois, type, montant, statut, rappel_j1, "
                    "observations, date_paiement, annee, mois_num, version, source_ref, created_at, updated_at) "
                    "VALUES (?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, '', ?, ?)",
                    (emp.id, rec["date_echeance"], rec["mois"], rec["type"], plan.montant(rec["type"]),
                     rec["statut"], rec["rappel_j1"], rec["observations"], rec["date_paiement"], year, month, ts, ts))
            _renumber(conn, emp.id)
            declared.append(emp.matricule)
        repos.log(conn, actor, "tresorerie.declaration", "echeances", period,
                  {"declares": declared, "ignores": [i["matricule"] for i in ignored]})
    return DeclarationReport(period, declared, ignored)


def _fr(iso: str) -> str:
    """Date au format jj/mm/aaaa, comme ``app._fr`` d'ezzinecdi."""
    try:
        return dt.date.fromisoformat(iso).strftime("%d/%m/%Y")
    except (ValueError, TypeError):
        return iso or ""


def _locked(conn, echeance_id: int, version: int) -> Echeance:
    row = conn.execute("SELECT * FROM echeances WHERE id = ? FOR UPDATE", (echeance_id,)).fetchone()
    if row is None:
        raise NotFoundError("Échéance introuvable.")
    current = _echeance(row)
    if current.version != version:
        raise ConflictError("Cette échéance a été modifiée entre-temps (autre poste ou autre onglet) : "
                            "rechargez-la avant de recommencer.")
    return current


def pay(db: Database, actor: str, echeance_id: int, version: int, date_paiement: dt.date | None = None,
        today: dt.date | None = None) -> Echeance:
    """Payer : saisie de la date de paiement (aujourd'hui par défaut) -> statut recalculé au jour."""
    today = today or dates.aujourdhui()
    paid_on = date_paiement or today
    if paid_on > today:
        raise PayrollError("La date de paiement ne peut pas être postérieure à aujourd'hui.")
    with db.transaction() as conn:
        e = _locked(conn, echeance_id, version)
        if integrity.est_paye(e.legacy()):
            raise PayrollError("Cette échéance est déjà payée.")
        iso = paid_on.isoformat()
        reg = integrity.regularite(iso, e.date_echeance)
        conn.execute("UPDATE echeances SET statut = ?, date_paiement = ?, observations = ?, version = version + 1, "
                     "updated_at = ? WHERE id = ? AND version = ?",
                     (integrity.statut_paye(reg), iso, f"Payé le {_fr(iso)} ({reg})", repos.now_iso(),
                      echeance_id, version))
        repos.log(conn, actor, "tresorerie.paiement", "echeance", echeance_id,
                  {"employee_id": e.employee_id, "mois": e.mois, "type": e.type, "date_paiement": iso,
                   "regularite": reg})
    return get_echeance(db, echeance_id)


def unpay(db: Database, actor: str, echeance_id: int, version: int) -> Echeance:
    """Dévalider : retour à « Non payé », date et observation effacées (comme l'original)."""
    with db.transaction() as conn:
        e = _locked(conn, echeance_id, version)
        if not integrity.est_paye(e.legacy()):
            raise PayrollError("Cette échéance n'est pas payée.")
        conn.execute("UPDATE echeances SET statut = ?, date_paiement = NULL, observations = '', "
                     "version = version + 1, updated_at = ? WHERE id = ? AND version = ?",
                     (integrity.STATUT_NON_PAYE, repos.now_iso(), echeance_id, version))
        repos.log(conn, actor, "tresorerie.devalidation", "echeance", echeance_id,
                  {"employee_id": e.employee_id, "mois": e.mois, "type": e.type})
    return get_echeance(db, echeance_id)


# --- Vues de pilotage (logique des panneaux d'origine) --------------------------------------------

def upcoming(db: Database, employee_id: int | None = None, today: dt.date | None = None) -> dict:
    """Panneau « À venir » : échues non payées (en retard), puis les 6 prochaines échéances non payées."""
    today = today or dates.aujourdhui()
    non_payes = [e for e in list_echeances(db, employee_id=employee_id, paid=False)]
    echus = sorted([e for e in non_payes if integrity.est_en_retard(e.legacy(), today)],
                   key=lambda e: e.date_echeance)
    a_venir = sorted([e for e in non_payes if not integrity.est_en_retard(e.legacy(), today)],
                     key=lambda e: e.date_echeance)[:6]
    return {"en_retard": echus, "a_venir": a_venir}


def reminders(db: Database, employee_id: int | None = None) -> list[Echeance]:
    """Panneau « Rappels » : échéances non payées (rappel J-1)."""
    return sorted(list_echeances(db, employee_id=employee_id, paid=False), key=lambda e: e.date_echeance)


def recap(db: Database, employee_id: int | None = None, year: int | None = None, month: int | None = None) -> dict:
    """Panneau « Récap » : total payé, restant dû, échéances payées n/N, avancement, régularité."""
    rows = list_echeances(db, year=year, month=month, employee_id=employee_id)
    payees = [e for e in rows if integrity.est_paye(e.legacy())]
    total = sum(e.montant for e in rows)
    paye = sum(e.montant for e in payees)
    rep = {reg: sum(1 for e in payees if e.statut == integrity.statut_paye(reg))
           for reg in (integrity.REG_A_TEMPS, integrity.REG_RETARD, integrity.REG_AVANCE)}
    return {"total_paye": paye, "restant_du": total - paye, "payees": len(payees), "echeances": len(rows),
            "avancement": round(100 * paye / total) if total else 0, "regularite": rep}


def template() -> list[dict]:
    """Gabarit d'échéancier fixe, commun à tous (lecture seule) : jour, type, ordre."""
    return [{"jour": jour, "type": typ, "ordre": ordre, "plan": PLAN_FIELD[typ]}
            for jour, typ, _montant, ordre in db_gen.BAREME]
