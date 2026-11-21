#!/usr/bin/env python3
"""Données de l'e2e de DEV (hbn-paie-dev) : base neuve, démo fictive d'origine, comptes et plan de versement.

Variables : E2E_SERVER_URL (serveur MySQL de dev), E2E_DB (nom de base), E2E_ADMIN_PW, E2E_USER_PW.
Jamais utilisé hors de l'environnement de dev éphémère.
"""

from __future__ import annotations

import os

import pymysql
from sqlalchemy.engine import make_url

from app.paie.repositories.db import Database
from app.paie.services import demo, master_data
from app.socle import users
from app.tresorerie.services import echeancier

server = make_url(os.environ["E2E_SERVER_URL"])
name = os.environ.get("E2E_DB", "paie_e2e")
assert name.startswith("paie_e2e")
conn = pymysql.connect(host=server.host, port=server.port or 3306, user=server.username, password=server.password or "",
                       autocommit=True)
with conn.cursor() as cur:
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
conn.close()
db = Database(server.set(database=name, query={"charset": "utf8mb4"}).render_as_string(hide_password=False))
db.migrate()
master_data.ensure_initial_parameters(db)
assert demo.seed_demo(db) is True
users.create_user(db, "e2e", "admin", "Administrateur", users.ROLE_SUPERADMIN, os.environ["E2E_ADMIN_PW"])
users.create_user(db, "e2e", "lecteur", "Lecteur", users.ROLE_USER, os.environ["E2E_USER_PW"])
emp = master_data.list_employees(db)[0]
echeancier.create_plan(db, "e2e", emp.id, "2026-07", 2500, 1500, 2500, 2000, "plan v1 (démo)")
print("e2e : base prête")
