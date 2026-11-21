"""Socle : comptes nominatifs et sessions (S2 / US-24). Nouvelles tables, sans équivalent d'origine.

- users : identifiant unique, nom affiché, rôle superadmin|user, hachage PBKDF2-SHA256 (auth.py d'origine).
- sessions : jeton aléatoire stocké haché (SHA-256), expiration, révocation à la déconnexion.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-21
"""

from __future__ import annotations

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

TABLE_OPTS = "ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_bin"

STATEMENTS = [
    f"""
    CREATE TABLE users (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        username VARCHAR(64) NOT NULL,
        display_name VARCHAR(255) NOT NULL DEFAULT '',
        role VARCHAR(16) NOT NULL CHECK (role IN ('superadmin', 'user')),
        password_hash VARCHAR(255) NOT NULL,
        active TINYINT NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
        created_at VARCHAR(32) NOT NULL,
        updated_at VARCHAR(32) NOT NULL,
        last_login_at VARCHAR(32),
        UNIQUE KEY ux_users_username (username)
    ) {TABLE_OPTS}
    """,
    f"""
    CREATE TABLE sessions (
        id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
        token_hash CHAR(64) NOT NULL,
        user_id INT NOT NULL,
        created_at VARCHAR(32) NOT NULL,
        expires_at VARCHAR(32) NOT NULL,
        revoked_at VARCHAR(32),
        UNIQUE KEY ux_sessions_token (token_hash),
        KEY ix_sessions_user (user_id),
        CONSTRAINT fk_sessions_user FOREIGN KEY (user_id) REFERENCES users (id)
    ) {TABLE_OPTS}
    """,
]


def upgrade() -> None:
    bind = op.get_bind()
    for statement in STATEMENTS:
        bind.exec_driver_sql(statement)


def downgrade() -> None:
    raise RuntimeError("Le socle ne se rétrograde pas (R5).")
