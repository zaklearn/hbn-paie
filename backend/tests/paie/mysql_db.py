"""Bases MySQL 8.4 de test (hbn-paie-dev) pour les tests d'origine portés.

``Database(chemin)`` remplace ``Database(fichier SQLite)`` des tests d'origine : chaque chemin
correspond à une base de test neuve, créée à la première utilisation sur le serveur de test
(``PAIE_TEST_DB_URL``) ; le même chemin redonne la même base (test « après redémarrage »).
Les bases de test sont supprimées à la fin de chaque test (``tests/conftest.py``) : serveur
de DEV éphémère sur tmpfs uniquement, jamais une base de production.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pymysql
from sqlalchemy.engine import make_url

from app.paie.repositories import db as _db

TEST_DB_PREFIX = "t_"
CREATED: list["Database"] = []


def server_url():
    raw = os.environ.get("PAIE_TEST_DB_URL", "")
    if not raw:
        raise RuntimeError("PAIE_TEST_DB_URL non défini : lancer les tests via scripts/dev-test.sh")
    return make_url(raw)


def admin_connection():
    url = server_url()
    return pymysql.connect(host=url.host, port=url.port or 3306, user=url.username,
                           password=url.password or "", charset="utf8mb4", autocommit=True)


class Database(_db.Database):
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.name = TEST_DB_PREFIX + hashlib.sha256(str(self.path).encode()).hexdigest()[:24]
        conn = admin_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(f"CREATE DATABASE IF NOT EXISTS `{self.name}` "
                            "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        finally:
            conn.close()
        url = server_url().set(database=self.name, query={"charset": "utf8mb4"})
        super().__init__(url.render_as_string(hide_password=False), pooled=False)
        CREATED.append(self)
