"""Sauvegarde et restauration de la base ``paie`` (S5 / US-50), sur le modèle de ``backup.py`` d'origine.

Une sauvegarde est un fichier autonome ``paie_<horodatage>_<libellé>.zip`` (0600) contenant :
- ``manifest.json`` : format, révision Alembic, version du schéma paie, protections de la base
  (déclencheurs, index d'unicité), et pour chaque table : colonnes, nombre de lignes, SHA-256 ;
- ``tables/<table>.jsonl`` : une ligne JSON par enregistrement, valeurs exactes (texte, entiers,
  octets en base64). Bulletins PDF, paramètres, journal et comptes compris ; sessions exclues.

Validation avant toute action (``validate_backup``) : format, révision connue, protections attendues,
empreintes, décomptes, unicités et références entre tables. Restauration : sauvegarde automatique de
sécurité, schéma recréé par les migrations (déclencheurs et contraintes du code, jamais du fichier),
puis données réinsérées dans une transaction ; en cas d'échec, la sauvegarde de sécurité est rétablie.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path


from app import __version__
from app.paie.repositories import repos
from app.paie.repositories.db import SCHEMA_VERSION, Database
from app.paie.services.errors import PayrollError

FORMAT = "hbn-paie-backup/1"
# Ordre d'insertion compatible avec les clés étrangères (replaces_id : ids croissants).
TABLES = ["company", "employees", "parameter_sets", "payslips", "documents", "audit_log", "users",
          "payment_plans", "echeances"]
ORDER_BY = {t: "id" for t in TABLES}
EXCLUDED = {"sessions", "alembic_version", "schema_version"}
REQUIRED_TABLES = {"0003": TABLES[:7], "0004": TABLES}
EXPECTED_TRIGGERS = {
    "0003": {"trg_parameter_sets_immutable", "trg_payslips_closed_immutable", "trg_payslips_closed_nodelete",
             "trg_documents_immutable", "trg_documents_nodelete", "trg_audit_append_only"},
}
EXPECTED_TRIGGERS["0004"] = EXPECTED_TRIGGERS["0003"] | {"trg_payment_plans_immutable"}
EXPECTED_UNIQUES = {
    "0003": {"company.PRIMARY", "employees.PRIMARY", "employees.ux_employees_matricule", "employees.ux_employees_cin",
             "employees.ux_employees_cnss", "parameter_sets.PRIMARY", "parameter_sets.ux_parameter_sets_valid_from",
             "payslips.PRIMARY", "payslips.ux_payslips_version", "payslips.ux_payslips_open",
             "payslips.ux_payslips_closed", "documents.PRIMARY", "documents.ux_documents_payslip", "audit_log.PRIMARY",
             "users.PRIMARY", "users.ux_users_username", "sessions.PRIMARY", "sessions.ux_sessions_token",
             "alembic_version.PRIMARY"},
}
EXPECTED_UNIQUES["0004"] = EXPECTED_UNIQUES["0003"] | {
    "payment_plans.PRIMARY", "payment_plans.ux_payment_plans_effect", "echeances.PRIMARY", "echeances.ux_echeances_cle"}
HEAD = "0004"


# --- Encodage exact des valeurs ---------------------------------------------------------------

def _encode(value):
    if isinstance(value, (bytes, bytearray)):
        return {"$b64": base64.b64encode(bytes(value)).decode("ascii")}
    return value


def _decode(value):
    if isinstance(value, dict) and set(value) == {"$b64"}:
        return base64.b64decode(value["$b64"])
    return value


def _columns(conn, table: str) -> list[str]:
    rows = conn.execute(
        "SELECT COLUMN_NAME AS c FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
        "AND TABLE_NAME = ? AND EXTRA NOT IN ('VIRTUAL GENERATED', 'STORED GENERATED') ORDER BY ORDINAL_POSITION", (table,)).fetchall()
    return [r["c"] for r in rows]


def protections(conn) -> dict:
    """Déclencheurs et index d'unicité présents dans la base (comme ``_protections`` d'origine)."""
    triggers = {r["n"] for r in conn.execute(
        "SELECT TRIGGER_NAME AS n FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA = DATABASE()")}
    uniques = {f"{r['t']}.{r['n']}" for r in conn.execute(
        "SELECT DISTINCT TABLE_NAME AS t, INDEX_NAME AS n FROM information_schema.STATISTICS "
        "WHERE TABLE_SCHEMA = DATABASE() AND NON_UNIQUE = 0")}
    return {"triggers": sorted(triggers), "uniques": sorted(uniques)}


def _revision(conn) -> str:
    return conn.execute("SELECT version_num AS v FROM alembic_version").fetchone()["v"]


# --- Sauvegarde -----------------------------------------------------------------------------------

def _dump(db: Database) -> bytes:
    with db.read() as conn:
        revision = _revision(conn)
        manifest = {"format": FORMAT, "app_version": __version__, "created_at": repos.now_iso(),
                    "alembic_revision": revision,
                    "schema_version": conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()["v"],
                    "protections": protections(conn), "tables": {}}
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for table in REQUIRED_TABLES[revision]:
                cols = _columns(conn, table)
                lines = []
                for row in conn.execute(f"SELECT {', '.join(cols)} FROM {table} ORDER BY {ORDER_BY[table]}"):
                    lines.append(json.dumps([_encode(row[c]) for c in cols], ensure_ascii=False, separators=(",", ":")))
                data = ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")
                zf.writestr(f"tables/{table}.jsonl", data)
                manifest["tables"][table] = {"columns": cols, "rows": len(lines),
                                             "sha256": hashlib.sha256(data).hexdigest()}
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=1, sort_keys=True))
    return buffer.getvalue()


def _write_private(path: Path, content: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(content)


def create_backup(db: Database, backup_dir: Path, actor: str, label: str = "manuelle",
                  retention: int = 0) -> Path:
    """Sauvegarde complète. ``retention`` > 0 : ne garde que les N plus récentes (0 = toutes)."""
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    target = backup_dir / f"paie_{stamp}_{label}.zip"
    _write_private(target, _dump(db))
    with db.transaction() as conn:
        repos.log(conn, actor, "sauvegarde.creation", "backup", target.name)
    if retention > 0:
        for old in list_backups(backup_dir)[retention:]:
            old.unlink()
    return target


def list_backups(backup_dir: Path) -> list[Path]:
    backup_dir = Path(backup_dir)
    if not backup_dir.is_dir():
        return []
    return sorted(backup_dir.glob("paie_*.zip"), reverse=True)


# --- Validation (avant toute action) -------------------------------------------------------------

def _read(content: bytes) -> tuple[dict, dict[str, list[dict]]]:
    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
        manifest = json.loads(zf.read("manifest.json"))
    except (zipfile.BadZipFile, KeyError, ValueError) as exc:
        raise PayrollError("Ce fichier n'est pas une sauvegarde de paie valide.") from exc
    if manifest.get("format") != FORMAT:
        raise PayrollError("Ce fichier n'est pas une sauvegarde de paie valide.")
    revision = manifest.get("alembic_revision")
    if revision not in REQUIRED_TABLES or revision > HEAD or manifest.get("schema_version") != SCHEMA_VERSION:
        raise PayrollError("Version de schéma incompatible avec cette application.")
    prot = manifest.get("protections") or {}
    if set(prot.get("triggers", [])) != EXPECTED_TRIGGERS[revision] or \
            set(prot.get("uniques", [])) != EXPECTED_UNIQUES[revision]:
        raise PayrollError("Sauvegarde refusée : les protections de la base (déclencheurs ou index d'unicité) "
                           "ne correspondent pas au schéma attendu.")
    tables: dict[str, list[dict]] = {}
    if set(manifest.get("tables", {})) != set(REQUIRED_TABLES[revision]):
        raise PayrollError("Sauvegarde refusée : tables manquantes ou inattendues.")
    for table, meta in manifest["tables"].items():
        try:
            data = zf.read(f"tables/{table}.jsonl")
        except KeyError as exc:
            raise PayrollError(f"Sauvegarde refusée : table {table} absente du fichier.") from exc
        if hashlib.sha256(data).hexdigest() != meta.get("sha256"):
            raise PayrollError(f"Sauvegarde refusée : empreinte de la table {table} incorrecte (fichier altéré).")
        cols = meta["columns"]
        rows = [dict(zip(cols, [_decode(v) for v in json.loads(line)])) for line in data.decode("utf-8").splitlines()]
        if len(rows) != meta.get("rows") or any(len(r) != len(cols) for r in rows):
            raise PayrollError(f"Sauvegarde refusée : décompte de la table {table} incorrect.")
        tables[table] = rows
    _check_consistency(tables)
    return manifest, tables


def _dupes(values) -> bool:
    counts = Counter(v for v in values if v is not None)
    return any(n > 1 for n in counts.values())


def _check_consistency(t: dict[str, list[dict]]) -> None:
    """Unicités et références, contrôlées sur le contenu du fichier AVANT toute modification de la base."""
    ids = {name: {r["id"] for r in rows} for name, rows in t.items()}
    refs = [
        ("payslips", "employee_id", "employees"), ("payslips", "parameter_set_id", "parameter_sets"),
        ("payslips", "replaces_id", "payslips"), ("documents", "payslip_id", "payslips"),
        ("payment_plans", "employee_id", "employees"), ("echeances", "employee_id", "employees"),
    ]
    for table, column, target in refs:
        if table in t and any(r[column] is not None and r[column] not in ids[target] for r in t[table]):
            raise PayrollError("Sauvegarde refusée : références incohérentes entre les tables.")
    for name, rows in t.items():
        if _dupes(r["id"] for r in rows):
            raise PayrollError("Sauvegarde refusée : identifiants en double.")
    e, p = t["employees"], t["payslips"]
    checks = [
        _dupes(r["matricule"] for r in e), _dupes(r["cin"] or None for r in e), _dupes(r["cnss"] or None for r in e),
        _dupes(r["valid_from"] for r in t["parameter_sets"]),
        _dupes((r["employee_id"], r["year"], r["month"], r["version"]) for r in p),
        _dupes((r["employee_id"], r["year"], r["month"]) for r in p if r["status"] in ("brouillon", "calculee")),
        _dupes((r["employee_id"], r["year"], r["month"]) for r in p if r["status"] == "cloturee"),
        _dupes(r["payslip_id"] for r in t["documents"]), _dupes(r["username"] for r in t["users"]),
    ]
    if "echeances" in t:
        checks += [_dupes((r["employee_id"], r["annee"], r["mois_num"], r["type"]) for r in t["echeances"]),
                   _dupes((r["employee_id"], r["valid_from"]) for r in t["payment_plans"])]
    if any(checks):
        raise PayrollError("Sauvegarde refusée : doublons contraires aux règles d'unicité de la base.")
    if len(t["company"]) > 1 or any(r["id"] != 1 for r in t["company"]):
        raise PayrollError("Sauvegarde refusée : fiche entreprise invalide.")


def validate_backup(content: bytes) -> dict:
    """Contrôle complet d'un fichier de sauvegarde ; renvoie son manifeste."""
    manifest, _ = _read(content)
    return manifest


def validate_backup_file(path: Path) -> dict:
    return validate_backup(Path(path).read_bytes())


def check_database_protections(db: Database) -> None:
    """La base de l'application porte exactement les protections attendues (contrôle d'origine)."""
    with db.read() as conn:
        revision, prot = _revision(conn), protections(conn)
    if set(prot["triggers"]) != EXPECTED_TRIGGERS[revision] or set(prot["uniques"]) != EXPECTED_UNIQUES[revision]:
        raise PayrollError("Les protections de la base ne correspondent pas au schéma attendu.")


# --- Restauration ------------------------------------------------------------------------------------

def _drop_all(db: Database) -> None:
    """Supprime les tables de la base ``paie`` (avant reconstruction par les migrations)."""
    with db.read() as conn:
        names = [r["n"] for r in conn.execute(
            "SELECT TABLE_NAME AS n FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE()")]
        conn.execute("SET FOREIGN_KEY_CHECKS = 0")
        try:
            for name in names:
                conn.execute(f"DROP TABLE IF EXISTS `{name}`")
        finally:
            conn.execute("SET FOREIGN_KEY_CHECKS = 1")


def _rebuild(db: Database, revision: str) -> None:
    from alembic import command
    from alembic.config import Config

    from app.paie.repositories.db import ALEMBIC_DIR

    cfg = Config(str(ALEMBIC_DIR.parent / "alembic.ini"))
    cfg.set_main_option("script_location", str(ALEMBIC_DIR))
    with db._engine.begin() as connection:
        cfg.attributes["connection"] = connection
        command.upgrade(cfg, revision)


def _load(db: Database, manifest: dict, tables: dict[str, list[dict]]) -> None:
    with db.transaction() as conn:
        for table in REQUIRED_TABLES[manifest["alembic_revision"]]:
            cols = manifest["tables"][table]["columns"]
            sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)})"
            for row in tables[table]:
                conn.execute(sql, [row[c] for c in cols])


def _restore_content(db: Database, manifest: dict, tables: dict[str, list[dict]]) -> None:
    _drop_all(db)
    _rebuild(db, manifest["alembic_revision"])
    _load(db, manifest, tables)
    _rebuild(db, "head")


def restore_backup(db: Database, content: bytes, backup_dir: Path, actor: str) -> Path:
    """Remplace le contenu de la base par la sauvegarde fournie. Renvoie la sauvegarde de sécurité."""
    manifest, tables = _read(content)                       # refus avant toute action
    safety = create_backup(db, backup_dir, actor, label="avant_restauration")
    try:
        _restore_content(db, manifest, tables)
    except Exception:
        safety_manifest, safety_tables = _read(safety.read_bytes())
        _restore_content(db, safety_manifest, safety_tables)
        raise
    check_database_protections(db)
    with db.transaction() as conn:
        repos.log(conn, actor, "sauvegarde.restauration", "backup", safety.name)
    return safety
