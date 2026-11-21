"""Connexion MySQL 8.4, transactions et migrations du schéma (remplace le db.py SQLite d'origine).

L'interface de ``Database`` est celle de paie-bulletins (``connect``, ``transaction``, ``read``,
``migrate``) afin que les dépôts et services soient repris à l'identique :

- ``Connection.execute(sql, params)`` accepte les marqueurs ``?`` de l'original (convertis en
  ``%s`` pour PyMySQL) et renvoie des lignes adressables par nom (``row["col"]``, ``dict(row)``) ;
- les violations de contrainte et les ``SIGNAL SQLSTATE '45000'`` des déclencheurs lèvent
  ``IntegrityError`` avec le message de la base, comme ``sqlite3.IntegrityError`` ;
- ``transaction()`` : tout ou rien. Le verrou ``BEGIN IMMEDIATE`` de SQLite (base entière) est
  remplacé par ``SELECT … FOR UPDATE`` sur la ligne salarié, posé par les services de paie
  (``repos.lock_employee`` / ``repos.lock_payslip_employee``) ;
- isolation READ COMMITTED : chaque lecture voit le dernier état validé, comme SQLite.

Les montants restent du texte décimal exact (JSON texte en LONGTEXT) : aucune colonne arrondissante.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pymysql
from sqlalchemy import create_engine, event, pool, text

SCHEMA_VERSION = 1
ALEMBIC_DIR = Path(__file__).resolve().parents[3] / "alembic"

# Codes MySQL traités comme des violations d'intégrité (équivalents de sqlite3.IntegrityError).
INTEGRITY_ERRNOS = {
    1048,   # colonne NOT NULL
    1062,   # doublon UNIQUE
    1216, 1217, 1451, 1452,  # clé étrangère
    1644,   # SIGNAL SQLSTATE '45000' (déclencheurs d'immuabilité)
    3819,   # contrainte CHECK
}


class IntegrityError(Exception):
    """Violation d'une règle d'intégrité portée par la base (message de la base)."""


class Row(dict):
    """Ligne adressable par nom de colonne, comme ``sqlite3.Row``."""


class Cursor:
    def __init__(self, cursor) -> None:
        self._cursor = cursor

    @property
    def lastrowid(self) -> int:
        return self._cursor.lastrowid

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    def fetchone(self) -> Row | None:
        row = self._cursor.fetchone()
        return Row(row) if row is not None else None

    def fetchall(self) -> list[Row]:
        return [Row(r) for r in self._cursor.fetchall()]

    def __iter__(self) -> Iterator[Row]:
        return iter(self.fetchall())


def _to_pymysql(sql: str, params: Sequence[Any] | None) -> tuple[str, tuple | None]:
    """Marqueurs ``?`` -> ``%s`` (PyMySQL). Sans paramètre, la requête est transmise telle quelle."""
    if not params:
        return sql, None
    return sql.replace("%", "%%").replace("?", "%s"), tuple(params)


class Connection:
    """Connexion courte, interface proche de ``sqlite3.Connection``."""

    def __init__(self, raw) -> None:
        self._raw = raw

    def execute(self, sql: str, params: Sequence[Any] = ()) -> Cursor:
        statement, args = _to_pymysql(sql, params)
        cursor = self._raw.cursor(pymysql.cursors.DictCursor)
        try:
            cursor.execute(statement, args)
        except pymysql.err.MySQLError as exc:
            errno = exc.args[0] if exc.args else None
            if isinstance(exc, pymysql.err.IntegrityError) or errno in INTEGRITY_ERRNOS:
                message = exc.args[1] if len(exc.args) > 1 else str(exc)
                raise IntegrityError(message) from exc
            raise
        return Cursor(cursor)

    def begin(self) -> None:
        self._raw.begin()

    def commit(self) -> None:
        self._raw.commit()

    def rollback(self) -> None:
        self._raw.rollback()

    def close(self) -> None:
        self._raw.close()


class Database:
    """Accès à la base ``paie`` (MySQL 8.4). Une connexion courte par opération."""

    def __init__(self, url: str, *, pooled: bool = True) -> None:
        self.url = url
        options: dict[str, Any] = {"pool_pre_ping": True, "future": True}
        if pooled:
            options.update(pool_size=5, max_overflow=5, pool_recycle=3600)
        else:
            options["poolclass"] = pool.NullPool
        self._engine = create_engine(url, **options)
        event.listen(self._engine, "connect", _on_connect)

    def connect(self) -> Connection:
        raw = self._engine.raw_connection()
        raw.dbapi_connection.autocommit(True)
        return Connection(raw)

    @contextmanager
    def transaction(self) -> Iterator[Connection]:
        """Transaction : tout ou rien. Le verrouillage fin est posé par les services (FOR UPDATE)."""
        conn = self.connect()
        try:
            conn.begin()
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def read(self) -> Iterator[Connection]:
        conn = self.connect()
        try:
            yield conn
        finally:
            conn.close()

    def migrate(self) -> int:
        """Applique les migrations Alembic manquantes ; renvoie la version du schéma paie."""
        from alembic import command
        from alembic.config import Config

        cfg = Config(str(ALEMBIC_DIR.parent / "alembic.ini"))
        cfg.set_main_option("script_location", str(ALEMBIC_DIR))
        with self._engine.begin() as connection:
            cfg.attributes["connection"] = connection
            command.upgrade(cfg, "head")
        with self._engine.connect() as connection:
            return int(connection.execute(text("SELECT MAX(version) FROM schema_version")).scalar() or 0)

    def dispose(self) -> None:
        self._engine.dispose()


def _on_connect(dbapi_connection, _record) -> None:
    with dbapi_connection.cursor() as cur:
        cur.execute("SET SESSION TRANSACTION ISOLATION LEVEL READ COMMITTED")
        cur.execute("SET SESSION sql_mode = 'STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,"
                    "ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION,ONLY_FULL_GROUP_BY'")
