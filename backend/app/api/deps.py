"""Dépendances FastAPI : base, utilisateur connecté, contrôle des rôles (refus côté API)."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status

from app.paie.repositories.db import Database
from app.socle import users

SESSION_COOKIE = "hbn_paie_session"


def get_db(request: Request) -> Database:
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Base de données non configurée.")
    return db


def current_user(request: Request, db: Database = Depends(get_db)) -> users.User:
    user = users.session_user(db, request.cookies.get(SESSION_COOKIE))
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Connexion requise.")
    return user


def superadmin(user: users.User = Depends(current_user)) -> users.User:
    """Écritures : réservées au rôle superadmin (le rôle « user » est en lecture et export seulement)."""
    if user.role != users.ROLE_SUPERADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Action réservée au rôle superadmin.")
    return user


def reveal(user: users.User) -> bool:
    return user.role == users.ROLE_SUPERADMIN
