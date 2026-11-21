"""Comptes nominatifs, rôles et sessions (S2 / US-24). Nouveau module (sans équivalent d'origine).

- Hachage : ``app.socle.auth`` (auth.py de paie-bulletins repris tel quel, PBKDF2-SHA256 600 000).
- Rôles : ``superadmin`` (toutes opérations) et ``user`` (lecture et exports seulement).
- Sessions : jeton aléatoire remis au navigateur (cookie httpOnly), seul son SHA-256 est stocké ;
  expiration et révocation à la déconnexion.
- Journal : ``repos.log`` de la paie ; jamais de mot de passe, de hachage ni de jeton.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.paie.repositories import repos
from app.paie.repositories.db import Database
from app.paie.services.errors import PayrollError
from app.socle import auth

ROLE_SUPERADMIN = "superadmin"
ROLE_USER = "user"
ROLES = (ROLE_SUPERADMIN, ROLE_USER)
USERNAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,63}$")
HASH_ITERATIONS = auth.ITERATIONS          # abaissé uniquement par les tests
SESSION_HOURS = 8
# Hachage factice : même coût de vérification pour un identifiant inconnu (pas d'énumération).
_DUMMY_HASH = "pbkdf2_sha256$600000$AAAAAAAAAAAAAAAAAAAAAA==$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="


@dataclass(frozen=True)
class User:
    id: int
    username: str
    display_name: str
    role: str
    active: bool
    created_at: str
    last_login_at: str | None

    @property
    def actor(self) -> str:
        """Acteur inscrit au journal : l'identifiant du compte connecté."""
        return self.username


def _user(row) -> User:
    return User(row["id"], row["username"], row["display_name"], row["role"], bool(row["active"]),
                row["created_at"], row["last_login_at"])


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _check_username(username: str) -> str:
    username = username.strip().lower()
    if not USERNAME_RE.match(username):
        raise PayrollError("Identifiant invalide : 3 à 64 caractères (lettres minuscules, chiffres, . _ -).")
    return username


def _check_role(role: str) -> None:
    if role not in ROLES:
        raise PayrollError("Rôle inconnu.")


def _active_superadmins(conn) -> int:
    return conn.execute("SELECT COUNT(*) AS n FROM users WHERE role = ? AND active = 1",
                        (ROLE_SUPERADMIN,)).fetchone()["n"]


def create_user(db: Database, actor: str, username: str, display_name: str, role: str,
                password: str) -> int:
    username = _check_username(username)
    _check_role(role)
    try:
        password_hash = auth.hash_password(password, iterations=HASH_ITERATIONS)
    except ValueError as exc:
        raise PayrollError(str(exc)) from exc
    ts = repos.now_iso()
    with db.transaction() as conn:
        if conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone():
            raise PayrollError("Cet identifiant est déjà utilisé.")
        cur = conn.execute(
            "INSERT INTO users (username, display_name, role, password_hash, active, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 1, ?, ?)", (username, display_name.strip(), role, password_hash, ts, ts))
        user_id = int(cur.lastrowid)
        repos.log(conn, actor, "utilisateur.creation", "user", user_id, {"identifiant": username, "role": role})
    return user_id


def list_users(db: Database) -> list[User]:
    with db.read() as conn:
        return [_user(r) for r in conn.execute("SELECT * FROM users ORDER BY username")]


def get_user(db: Database, user_id: int) -> User | None:
    with db.read() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return _user(row) if row else None


def set_active(db: Database, actor: str, user_id: int, active: bool) -> None:
    with db.transaction() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ? FOR UPDATE", (user_id,)).fetchone()
        if row is None:
            raise PayrollError("Utilisateur introuvable.")
        if not active and row["role"] == ROLE_SUPERADMIN and row["active"] and _active_superadmins(conn) <= 1:
            raise PayrollError("Impossible de désactiver le dernier superadmin actif.")
        conn.execute("UPDATE users SET active = ?, updated_at = ? WHERE id = ?",
                     (1 if active else 0, repos.now_iso(), user_id))
        if not active:
            _revoke_all(conn, user_id)
        repos.log(conn, actor, "utilisateur.activation" if active else "utilisateur.desactivation",
                  "user", user_id, {"identifiant": row["username"]})


def set_role(db: Database, actor: str, user_id: int, role: str) -> None:
    _check_role(role)
    with db.transaction() as conn:
        row = conn.execute("SELECT * FROM users WHERE id = ? FOR UPDATE", (user_id,)).fetchone()
        if row is None:
            raise PayrollError("Utilisateur introuvable.")
        if row["role"] == ROLE_SUPERADMIN and role != ROLE_SUPERADMIN and row["active"] \
                and _active_superadmins(conn) <= 1:
            raise PayrollError("Impossible de retirer le rôle du dernier superadmin actif.")
        conn.execute("UPDATE users SET role = ?, updated_at = ? WHERE id = ?", (role, repos.now_iso(), user_id))
        repos.log(conn, actor, "utilisateur.role", "user", user_id, {"identifiant": row["username"], "role": role})


def set_password(db: Database, actor: str, user_id: int, password: str) -> None:
    try:
        password_hash = auth.hash_password(password, iterations=HASH_ITERATIONS)
    except ValueError as exc:
        raise PayrollError(str(exc)) from exc
    with db.transaction() as conn:
        row = conn.execute("SELECT username FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            raise PayrollError("Utilisateur introuvable.")
        conn.execute("UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                     (password_hash, repos.now_iso(), user_id))
        _revoke_all(conn, user_id)
        repos.log(conn, actor, "utilisateur.mot_de_passe", "user", user_id, {"identifiant": row["username"]})


# --- Connexion et sessions -------------------------------------------------------------------

def authenticate(db: Database, username: str, password: str) -> User | None:
    """Compte actif dont le mot de passe correspond, sinon None (message générique côté API)."""
    with db.read() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username.strip().lower(),)).fetchone()
    encoded = row["password_hash"] if row else _DUMMY_HASH
    ok = auth.verify_password(password, encoded)
    if not row or not ok or not row["active"]:
        return None
    return _user(row)


def open_session(db: Database, user: User, hours: int = SESSION_HOURS) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now()
    with db.transaction() as conn:
        conn.execute("INSERT INTO sessions (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
                     (_token_hash(token), user.id, now.isoformat(timespec="seconds"),
                      (now + timedelta(hours=hours)).isoformat(timespec="seconds")))
        conn.execute("UPDATE users SET last_login_at = ? WHERE id = ?", (now.isoformat(timespec="seconds"), user.id))
        repos.log(conn, user.actor, "connexion", "user", user.id)
    return token


def session_user(db: Database, token: str | None) -> User | None:
    if not token:
        return None
    with db.read() as conn:
        row = conn.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id "
            "WHERE s.token_hash = ? AND s.revoked_at IS NULL AND s.expires_at > ? AND u.active = 1",
            (_token_hash(token), repos.now_iso())).fetchone()
    return _user(row) if row else None


def close_session(db: Database, token: str | None) -> None:
    if not token:
        return
    with db.transaction() as conn:
        row = conn.execute("SELECT s.id, u.username, u.id AS uid FROM sessions s JOIN users u ON u.id = s.user_id "
                           "WHERE s.token_hash = ? AND s.revoked_at IS NULL", (_token_hash(token),)).fetchone()
        if row:
            conn.execute("UPDATE sessions SET revoked_at = ? WHERE id = ?", (repos.now_iso(), row["id"]))
            repos.log(conn, row["username"], "deconnexion", "user", row["uid"])


def _revoke_all(conn, user_id: int) -> None:
    conn.execute("UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                 (repos.now_iso(), user_id))
