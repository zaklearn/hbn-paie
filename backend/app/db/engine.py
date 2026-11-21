"""Moteur SQLAlchemy 2 (MySQL via PyMySQL), créé à la demande."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings


class DatabaseNotConfigured(RuntimeError):
    pass


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    if settings.db_url is None:
        raise DatabaseNotConfigured("PAIE_DB_URL n'est pas défini")
    return create_engine(
        settings.db_url.get_secret_value(),
        pool_pre_ping=True,
        pool_recycle=settings.db_pool_recycle,
        future=True,
    )


def get_sessionmaker() -> sessionmaker:
    return sessionmaker(bind=get_engine(), autoflush=False, expire_on_commit=False)


def ping() -> bool:
    """Vrai si la base répond à ``SELECT 1``."""
    with get_engine().connect() as conn:
        return conn.execute(text("SELECT 1")).scalar() == 1
