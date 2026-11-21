"""Schéma paie v1 — transposition MySQL 8.4 de paie-bulletins (src/repositories/db.py, migration 1).

S2 / US-20, US-21. Correspondance avec l'original :
- tables, colonnes, valeurs par défaut, CHECK et UNIQUE identiques ;
- TEXT des montants / JSON -> LONGTEXT + CHECK (JSON_VALID(...)) : texte exact conservé (R0.2) ;
- dates et horodatages : VARCHAR, même texte ISO que l'original (import octet pour octet, comparaisons
  de chaînes « AAAA-MM » inchangées) ;
- index partiels SQLite -> colonnes générées + UNIQUE (NULL non contraint) ;
- 6 déclencheurs RAISE(ABORT) -> SIGNAL SQLSTATE '45000', mêmes messages, mêmes conditions
  (« IS » de SQLite = égalité sûre vis-à-vis de NULL « <=> ») ;
- collation utf8mb4_bin : égalité, unicité et tri identiques à SQLite (BINARY).

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-21
"""

from __future__ import annotations

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TABLE_OPTS = "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin"

STATEMENTS = [
    f"""
    CREATE TABLE schema_version (
        version INT NOT NULL
    ) {TABLE_OPTS}
    """,
    f"""
    CREATE TABLE company (
        id INT NOT NULL PRIMARY KEY CHECK (id = 1),
        raison_sociale TEXT NOT NULL,
        adresse TEXT NOT NULL DEFAULT (''),
        ville TEXT NOT NULL DEFAULT (''),
        ice VARCHAR(255) NOT NULL DEFAULT '',
        cnss_employeur VARCHAR(255) NOT NULL DEFAULT '',
        rc VARCHAR(255) NOT NULL DEFAULT '',
        identifiant_fiscal VARCHAR(255) NOT NULL DEFAULT '',
        telephone VARCHAR(255) NOT NULL DEFAULT '',
        email VARCHAR(255) NOT NULL DEFAULT '',
        logo LONGBLOB,
        updated_at VARCHAR(32) NOT NULL
    ) {TABLE_OPTS}
    """,
    f"""
    CREATE TABLE employees (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        matricule VARCHAR(255) NOT NULL,
        nom TEXT NOT NULL,
        prenom TEXT NOT NULL DEFAULT (''),
        date_naissance VARCHAR(10),
        cin VARCHAR(255) NOT NULL DEFAULT '',
        cnss VARCHAR(255) NOT NULL DEFAULT '',
        situation_familiale VARCHAR(255) NOT NULL,
        nb_personnes_charge INT NOT NULL DEFAULT 0 CHECK (nb_personnes_charge >= 0),
        date_embauche VARCHAR(10),
        date_sortie VARCHAR(10),
        fonction TEXT NOT NULL DEFAULT (''),
        departement TEXT NOT NULL DEFAULT (''),
        cimr VARCHAR(255) NOT NULL DEFAULT '',
        categorie TEXT NOT NULL DEFAULT (''),
        banque TEXT NOT NULL DEFAULT (''),
        compte_bancaire VARCHAR(255) NOT NULL DEFAULT '',
        adresse TEXT NOT NULL DEFAULT (''),
        mode_paiement VARCHAR(255) NOT NULL DEFAULT 'Virement',
        actif TINYINT NOT NULL DEFAULT 1 CHECK (actif IN (0, 1)),
        created_at VARCHAR(32) NOT NULL,
        updated_at VARCHAR(32) NOT NULL,
        -- ux_employees_cin / ux_employees_cnss : unicité si renseigné (index partiel SQLite)
        cin_key VARCHAR(255) GENERATED ALWAYS AS (NULLIF(cin, '')) VIRTUAL,
        cnss_key VARCHAR(255) GENERATED ALWAYS AS (NULLIF(cnss, '')) VIRTUAL,
        UNIQUE KEY ux_employees_matricule (matricule),
        UNIQUE KEY ux_employees_cin (cin_key),
        UNIQUE KEY ux_employees_cnss (cnss_key)
    ) {TABLE_OPTS}
    """,
    f"""
    CREATE TABLE parameter_sets (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        valid_from VARCHAR(7) NOT NULL,
        label TEXT NOT NULL DEFAULT (''),
        data LONGTEXT NOT NULL CHECK (JSON_VALID(data)),
        comment TEXT NOT NULL DEFAULT (''),
        created_at VARCHAR(32) NOT NULL,
        created_by VARCHAR(255) NOT NULL DEFAULT '',
        UNIQUE KEY ux_parameter_sets_valid_from (valid_from)
    ) {TABLE_OPTS}
    """,
    """
    CREATE TRIGGER trg_parameter_sets_immutable BEFORE UPDATE ON parameter_sets
    FOR EACH ROW
    SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Une version de paramètres est immuable : créer une nouvelle version.'
    """,
    f"""
    CREATE TABLE payslips (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        employee_id INT NOT NULL,
        year INT NOT NULL CHECK (year BETWEEN 2000 AND 2100),
        month INT NOT NULL CHECK (month BETWEEN 1 AND 12),
        version INT NOT NULL DEFAULT 1 CHECK (version >= 1),
        status VARCHAR(16) NOT NULL CHECK (status IN ('brouillon', 'calculee', 'cloturee', 'remplacee')),
        inputs LONGTEXT NOT NULL CHECK (JSON_VALID(inputs)),
        result LONGTEXT CHECK (JSON_VALID(result)),
        cumuls LONGTEXT CHECK (JSON_VALID(cumuls)),
        parameter_set_id INT,
        parameters LONGTEXT CHECK (JSON_VALID(parameters)),
        employee_snapshot LONGTEXT CHECK (JSON_VALID(employee_snapshot)),
        company_snapshot LONGTEXT CHECK (JSON_VALID(company_snapshot)),
        replaces_id INT,
        rectification_reason TEXT NOT NULL DEFAULT (''),
        created_at VARCHAR(32) NOT NULL,
        updated_at VARCHAR(32) NOT NULL,
        calculated_at VARCHAR(32),
        closed_at VARCHAR(32),
        closed_by VARCHAR(255) NOT NULL DEFAULT '',
        -- Au plus une version de travail et une version clôturée faisant foi par salarié et mois.
        open_key TINYINT GENERATED ALWAYS AS (IF(status IN ('brouillon', 'calculee'), 1, NULL)) VIRTUAL,
        closed_key TINYINT GENERATED ALWAYS AS (IF(status = 'cloturee', 1, NULL)) VIRTUAL,
        UNIQUE KEY ux_payslips_version (employee_id, year, month, version),
        UNIQUE KEY ux_payslips_open (employee_id, year, month, open_key),
        UNIQUE KEY ux_payslips_closed (employee_id, year, month, closed_key),
        KEY ix_payslips_period (year, month),
        CONSTRAINT fk_payslips_employee FOREIGN KEY (employee_id) REFERENCES employees (id),
        CONSTRAINT fk_payslips_parameter_set FOREIGN KEY (parameter_set_id) REFERENCES parameter_sets (id),
        CONSTRAINT fk_payslips_replaces FOREIGN KEY (replaces_id) REFERENCES payslips (id)
    ) {TABLE_OPTS}
    """,
    # Une paie clôturée est figée ; seule la transition cloturee -> remplacee est admise,
    # sans aucune autre modification.
    """
    CREATE TRIGGER trg_payslips_closed_immutable BEFORE UPDATE ON payslips
    FOR EACH ROW
    BEGIN
        IF OLD.status IN ('cloturee', 'remplacee') AND NOT (
            OLD.status = 'cloturee' AND NEW.status = 'remplacee'
            AND NEW.inputs <=> OLD.inputs AND NEW.result <=> OLD.result
            AND NEW.cumuls <=> OLD.cumuls AND NEW.parameters <=> OLD.parameters
            AND NEW.employee_snapshot <=> OLD.employee_snapshot
            AND NEW.company_snapshot <=> OLD.company_snapshot
            AND NEW.closed_at <=> OLD.closed_at AND NEW.version <=> OLD.version
            AND NEW.year <=> OLD.year AND NEW.month <=> OLD.month
            AND NEW.employee_id <=> OLD.employee_id
        ) THEN
            SIGNAL SQLSTATE '45000'
                SET MESSAGE_TEXT = 'Paie clôturée : modification interdite (passer par une rectification).';
        END IF;
    END
    """,
    """
    CREATE TRIGGER trg_payslips_closed_nodelete BEFORE DELETE ON payslips
    FOR EACH ROW
    BEGIN
        IF OLD.status IN ('cloturee', 'remplacee') THEN
            SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Paie clôturée : suppression interdite.';
        END IF;
    END
    """,
    f"""
    CREATE TABLE documents (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        payslip_id INT NOT NULL,
        filename VARCHAR(255) NOT NULL,
        content LONGBLOB NOT NULL,
        sha256 VARCHAR(64) NOT NULL,
        created_at VARCHAR(32) NOT NULL,
        UNIQUE KEY ux_documents_payslip (payslip_id),
        CONSTRAINT fk_documents_payslip FOREIGN KEY (payslip_id) REFERENCES payslips (id)
    ) {TABLE_OPTS}
    """,
    """
    CREATE TRIGGER trg_documents_immutable BEFORE UPDATE ON documents
    FOR EACH ROW
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Bulletin archivé : modification interdite.'
    """,
    """
    CREATE TRIGGER trg_documents_nodelete BEFORE DELETE ON documents
    FOR EACH ROW
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Bulletin archivé : suppression interdite.'
    """,
    f"""
    CREATE TABLE audit_log (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        ts VARCHAR(32) NOT NULL,
        actor VARCHAR(255) NOT NULL DEFAULT '',
        action VARCHAR(255) NOT NULL,
        entity VARCHAR(255) NOT NULL DEFAULT '',
        entity_id VARCHAR(255) NOT NULL DEFAULT '',
        details LONGTEXT NOT NULL DEFAULT ('')
    ) {TABLE_OPTS}
    """,
    """
    CREATE TRIGGER trg_audit_append_only BEFORE UPDATE ON audit_log
    FOR EACH ROW
    SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT = 'Journal en ajout seul.'
    """,
    "INSERT INTO schema_version (version) VALUES (1)",
]

def upgrade() -> None:
    bind = op.get_bind()
    for statement in STATEMENTS:
        bind.exec_driver_sql(statement)


def downgrade() -> None:
    raise RuntimeError("Le schéma paie ne se rétrograde pas (données de paie, R5).")
