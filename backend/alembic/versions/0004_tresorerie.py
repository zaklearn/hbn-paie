"""Trésorerie multi-salariés (S3 / US-31, US-32).

- payment_plans : plan de versement d'un salarié, versionné par date d'effet (AAAA-MM), montants en
  ENTIERS DH comme l'original (S1, CNSS, S2, S3). Une version est immuable (déclencheur), comme les
  versions de paramètres de paie : un changement = nouvelle version, jamais rétroactive.
- echeances : les 9 champs d'origine d'ezzinecdi + employee_id, annee, mois_num, version (verrou
  optimiste) et source_ref (n d'origine à l'import). Clé métier : (salarié, année, mois, type).
- Types et statuts : chaînes exactes du legacy (db_gen / integrity).

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-21
"""

from __future__ import annotations

from alembic import op

from app.tresorerie.legacy import db_gen, integrity

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

TABLE_OPTS = "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin"


def _in_list(values) -> str:
    return ", ".join("'" + v.replace("'", "''") + "'" for v in values)


STATEMENTS = [
    f"""
    CREATE TABLE payment_plans (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        employee_id INT NOT NULL,
        valid_from VARCHAR(7) NOT NULL,
        s1 INT NOT NULL CHECK (s1 >= 0),
        cnss INT NOT NULL CHECK (cnss >= 0),
        s2 INT NOT NULL CHECK (s2 >= 0),
        s3 INT NOT NULL CHECK (s3 >= 0),
        comment TEXT NOT NULL DEFAULT (''),
        created_at VARCHAR(32) NOT NULL,
        created_by VARCHAR(255) NOT NULL DEFAULT '',
        UNIQUE KEY ux_payment_plans_effect (employee_id, valid_from),
        CONSTRAINT fk_payment_plans_employee FOREIGN KEY (employee_id) REFERENCES employees (id)
    ) {TABLE_OPTS}
    """,
    """
    CREATE TRIGGER trg_payment_plans_immutable BEFORE UPDATE ON payment_plans
    FOR EACH ROW
    SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Un plan de versement est immuable : créer une nouvelle version.'
    """,
    f"""
    CREATE TABLE echeances (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        employee_id INT NOT NULL,
        n INT NOT NULL,
        date_echeance VARCHAR(10) NOT NULL,
        mois VARCHAR(32) NOT NULL,
        type VARCHAR(64) NOT NULL CHECK (type IN ({_in_list(integrity.TYPES_VALIDES)})),
        montant INT NOT NULL CHECK (montant >= 0),
        statut VARCHAR(32) NOT NULL CHECK (statut IN ({_in_list(integrity.STATUTS_VALIDES)})),
        rappel_j1 VARCHAR(10) NOT NULL,
        observations TEXT NOT NULL DEFAULT (''),
        date_paiement VARCHAR(10),
        annee INT NOT NULL CHECK (annee BETWEEN 2000 AND 2100),
        mois_num INT NOT NULL CHECK (mois_num BETWEEN 1 AND 12),
        version INT NOT NULL DEFAULT 1 CHECK (version >= 1),
        source_ref VARCHAR(64) NOT NULL DEFAULT '',
        created_at VARCHAR(32) NOT NULL,
        updated_at VARCHAR(32) NOT NULL,
        -- cohérence payé <=> date_paiement (integrity.reconcile)
        CONSTRAINT ck_echeances_paiement CHECK (
            (statut = '{db_gen.STATUT_NON_PAYE}' AND date_paiement IS NULL)
            OR (statut <> '{db_gen.STATUT_NON_PAYE}' AND date_paiement IS NOT NULL)),
        UNIQUE KEY ux_echeances_cle (employee_id, annee, mois_num, type),
        KEY ix_echeances_periode (annee, mois_num),
        KEY ix_echeances_date (date_echeance),
        CONSTRAINT fk_echeances_employee FOREIGN KEY (employee_id) REFERENCES employees (id)
    ) {TABLE_OPTS}
    """,
]


def upgrade() -> None:
    bind = op.get_bind()
    for statement in STATEMENTS:
        bind.exec_driver_sql(statement)


def downgrade() -> None:
    raise RuntimeError("La trésorerie ne se rétrograde pas (R5).")
