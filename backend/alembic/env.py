"""Environnement Alembic de HBN Paie.

L'URL de connexion vient de ``PAIE_DB_URL`` (config pydantic-settings) et n'est jamais
écrite dans ``alembic.ini`` ni journalisée (R4).
"""

from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import get_settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None  # schéma introduit en S2 (US-20)


def _url() -> str:
    url = get_settings().db_url
    if url is None:
        raise RuntimeError("PAIE_DB_URL n'est pas défini")
    return url.get_secret_value()


def run_migrations_offline() -> None:
    context.configure(url=_url(), target_metadata=target_metadata, literal_binds=True,
                      dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(_url(), poolclass=pool.NullPool, future=True)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
