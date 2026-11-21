"""Socle : connexion, déconnexion, compte courant, gestion des utilisateurs (superadmin)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.api.deps import SESSION_COOKIE, current_user, get_db, superadmin
from app.api.serialize import user_out
from app.core.config import get_settings
from app.paie.repositories.db import Database
from app.socle import users

router = APIRouter()


class LoginIn(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=1024)


class UserIn(BaseModel):
    username: str = Field(max_length=64)
    display_name: str = Field(default="", max_length=255)
    role: str
    password: str = Field(max_length=1024)


class ActiveIn(BaseModel):
    active: bool


class RoleIn(BaseModel):
    role: str


class PasswordIn(BaseModel):
    password: str = Field(max_length=1024)


@router.post("/api/auth/connexion")
def login(body: LoginIn, response: Response, db: Database = Depends(get_db)) -> dict:
    user = users.authenticate(db, body.username, body.password)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Identifiant ou mot de passe incorrect.")
    settings = get_settings()
    token = users.open_session(db, user, hours=settings.session_hours)
    response.set_cookie(SESSION_COOKIE, token, max_age=settings.session_hours * 3600, httponly=True,
                        secure=settings.cookie_secure, samesite="strict", path="/")
    return user_out(user)


@router.post("/api/auth/deconnexion")
def logout(request: Request, response: Response, db: Database = Depends(get_db)) -> dict:
    users.close_session(db, request.cookies.get(SESSION_COOKIE))
    response.delete_cookie(SESSION_COOKIE, path="/")
    return {"ok": True}


@router.get("/api/auth/moi")
def me(user: users.User = Depends(current_user)) -> dict:
    return user_out(user)


@router.get("/api/socle/utilisateurs")
def list_users(_: users.User = Depends(superadmin), db: Database = Depends(get_db)) -> list[dict]:
    return [user_out(u) for u in users.list_users(db)]


@router.post("/api/socle/utilisateurs", status_code=201)
def create_user(body: UserIn, admin: users.User = Depends(superadmin), db: Database = Depends(get_db)) -> dict:
    user_id = users.create_user(db, admin.actor, body.username, body.display_name, body.role, body.password)
    return user_out(users.get_user(db, user_id))


@router.post("/api/socle/utilisateurs/{user_id}/activation")
def set_active(user_id: int, body: ActiveIn, admin: users.User = Depends(superadmin),
               db: Database = Depends(get_db)) -> dict:
    users.set_active(db, admin.actor, user_id, body.active)
    return user_out(users.get_user(db, user_id))


@router.post("/api/socle/utilisateurs/{user_id}/role")
def set_role(user_id: int, body: RoleIn, admin: users.User = Depends(superadmin),
             db: Database = Depends(get_db)) -> dict:
    users.set_role(db, admin.actor, user_id, body.role)
    return user_out(users.get_user(db, user_id))


@router.post("/api/socle/utilisateurs/{user_id}/mot-de-passe")
def set_password(user_id: int, body: PasswordIn, admin: users.User = Depends(superadmin),
                 db: Database = Depends(get_db)) -> dict:
    users.set_password(db, admin.actor, user_id, body.password)
    return {"ok": True}
