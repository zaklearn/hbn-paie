"""Restauration : refus des sauvegardes altérées — équivalent MySQL de tests/test_backup_integrity.py d'origine.

Mêmes intentions que l'original (8 tests) : une sauvegarde dont les protections de la base diffèrent, dont les
données ont été modifiées ou dont les références sont incohérentes est refusée AVANT toute action (aucune
sauvegarde de sécurité créée, base inchangée) ; une sauvegarde valide restaure données, bulletins et
protections. Le format est propre à MySQL (zip + manifeste) : les altérations portent donc sur ce fichier.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile

import pytest

from app.paie.repositories.db import IntegrityError
from app.paie.services import demo, payroll
from app.paie.services.errors import PayrollError
from app.socle import backup

from .conftest import ACTOR


@pytest.fixture
def seeded(db, tmp_path):
    """Base de démonstration (3 paies clôturées) et une sauvegarde valide."""
    demo.seed_demo(db)
    saved = backup.create_backup(db, tmp_path / "backups", ACTOR)
    return db, saved, tmp_path


def _snapshot(db):
    conn = db.connect()
    try:
        return (conn.execute("SELECT COUNT(*) AS n FROM information_schema.TRIGGERS "
                             "WHERE TRIGGER_SCHEMA = DATABASE()").fetchone()["n"],
                conn.execute("SELECT COUNT(*) AS n FROM payslips").fetchone()["n"],
                conn.execute("SELECT COUNT(*) AS n FROM documents").fetchone()["n"])
    finally:
        conn.close()


def _rewrite(saved, mutate_manifest=None, mutate_table=None, rehash=True) -> bytes:
    """Copie de la sauvegarde, manifeste et/ou table modifiés (empreintes recalculées si ``rehash``)."""
    src = zipfile.ZipFile(io.BytesIO(saved.read_bytes()))
    manifest = json.loads(src.read("manifest.json"))
    files = {n: src.read(n) for n in src.namelist() if n != "manifest.json"}
    if mutate_table:
        table, fn = mutate_table
        files[f"tables/{table}.jsonl"] = fn(files[f"tables/{table}.jsonl"], manifest["tables"][table]["columns"])
        if rehash:
            data = files[f"tables/{table}.jsonl"]
            manifest["tables"][table]["sha256"] = hashlib.sha256(data).hexdigest()
            manifest["tables"][table]["rows"] = len(data.decode().splitlines())
    if mutate_manifest:
        mutate_manifest(manifest)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as zf:
        for name, data in files.items():
            zf.writestr(name, data)
        zf.writestr("manifest.json", json.dumps(manifest))
    return out.getvalue()


def _drop(kind, name):
    return lambda m: m["protections"][kind].remove(name)


ALTERATIONS = {
    "déclencheur supprimé": _drop("triggers", "trg_payslips_closed_immutable"),
    "tous les déclencheurs supprimés": lambda m: m["protections"].update(triggers=[]),
    "index d'unicité supprimé": _drop("uniques", "payslips.ux_payslips_closed"),
    "déclencheur ajouté": lambda m: m["protections"]["triggers"].append("trg_extra"),
}


@pytest.mark.parametrize("label", ALTERATIONS)
def test_altered_backup_is_rejected_and_current_data_untouched(seeded, label):
    db, saved, tmp_path = seeded
    before = _snapshot(db)
    altered = _rewrite(saved, mutate_manifest=ALTERATIONS[label])
    with pytest.raises(PayrollError, match="protections"):
        backup.restore_backup(db, altered, tmp_path / "backups", ACTOR)
    assert _snapshot(db) == before
    assert not list((tmp_path / "backups").glob("*avant_restauration*"))   # refus avant toute action


def _append_document(data: bytes, columns: list[str]) -> bytes:
    row = {"id": 999, "payslip_id": 999, "filename": "x.pdf", "content": {"$b64": "AA=="}, "sha256": "x",
           "created_at": "x"}
    return data + (json.dumps([row[c] for c in columns]) + "\n").encode()


def test_backup_with_broken_references_is_rejected(seeded):
    _, saved, _ = seeded
    altered = _rewrite(saved, mutate_table=("documents", _append_document))
    with pytest.raises(PayrollError, match="références"):
        backup.validate_backup(altered)


def test_tampered_table_is_rejected(seeded):
    """Montant modifié dans le fichier sans recalcul de l'empreinte : refusé (intégrité)."""
    db, saved, tmp_path = seeded
    altered = _rewrite(saved, mutate_table=("payslips", lambda d, _c: d.replace(b"7000", b"7001", 1)), rehash=False)
    with pytest.raises(PayrollError, match="empreinte"):
        backup.restore_backup(db, altered, tmp_path / "backups", ACTOR)
    assert not list((tmp_path / "backups").glob("*avant_restauration*"))


def test_duplicate_closed_payslip_is_rejected_before_any_action(seeded):
    db, saved, tmp_path = seeded

    def duplicate_closed(data: bytes, columns: list[str]) -> bytes:
        rows = [json.loads(line) for line in data.decode().splitlines()]
        clone = list(rows[-1])
        clone[columns.index("id")] = 999
        clone[columns.index("version")] = 9
        return data + (json.dumps(clone) + "\n").encode()

    altered = _rewrite(saved, mutate_table=("payslips", duplicate_closed))
    with pytest.raises(PayrollError, match="unicité"):
        backup.restore_backup(db, altered, tmp_path / "backups", ACTOR)
    assert not list((tmp_path / "backups").glob("*avant_restauration*"))


def test_failure_during_restore_brings_back_safety_backup(seeded):
    """Violation d'un CHECK non visible à la validation : la base est rétablie depuis la sauvegarde de sécurité."""
    db, saved, tmp_path = seeded
    before = _snapshot(db), [s.result for s in payroll.list_payslips(db)]
    altered = _rewrite(saved, mutate_table=(
        "payslips", lambda d, _c: re.sub(rb',2026,', b',1999,', d, count=1)))
    with pytest.raises(IntegrityError):
        backup.restore_backup(db, altered, tmp_path / "backups", ACTOR)
    assert (_snapshot(db), [s.result for s in payroll.list_payslips(db)]) == before
    backup.check_database_protections(db)


def test_valid_backup_restores_with_protections_and_archives(seeded):
    db, saved, tmp_path = seeded
    before = _snapshot(db)
    backup.restore_backup(db, saved.read_bytes(), tmp_path / "backups", ACTOR)
    assert _snapshot(db) == before
    closed = [s for s in payroll.list_payslips(db) if s.status == "cloturee"]
    assert len(closed) == 3 and all(payroll.get_document(db, s.id) for s in closed)
    conn = db.connect()
    try:
        with pytest.raises(IntegrityError):
            conn.execute("DELETE FROM documents WHERE payslip_id = ?", (closed[0].id,))
    finally:
        conn.close()


def test_restore_is_exact_and_files_are_private(seeded):
    """Décomptes et empreintes identiques après sauvegarde -> restauration (US-50) ; fichiers 0600."""
    db, saved, tmp_path = seeded
    backup.restore_backup(db, saved.read_bytes(), tmp_path / "backups", ACTOR)
    again = backup.create_backup(db, tmp_path / "backups", ACTOR, label="verification")
    first = json.loads(zipfile.ZipFile(saved).read("manifest.json"))["tables"]
    second = json.loads(zipfile.ZipFile(again).read("manifest.json"))["tables"]
    for table in first:
        if table == "audit_log":                               # le journal trace la restauration elle-même
            assert second[table]["rows"] == first[table]["rows"] + 1    # « sauvegarde.restauration »
            continue
        assert second[table] == first[table], table
    assert all(oct(p.stat().st_mode & 0o777) == "0o600" for p in backup.list_backups(tmp_path / "backups"))
    assert oct((tmp_path / "backups").stat().st_mode & 0o777) == "0o700"


def test_application_database_matches_expected_protections(seeded):
    """La base créée par les migrations est elle-même conforme au contrôle."""
    db, _, _ = seeded
    backup.check_database_protections(db)


def test_retention_keeps_the_most_recent(seeded):
    db, _, tmp_path = seeded
    for _ in range(3):
        backup.create_backup(db, tmp_path / "r", ACTOR, retention=2)
    assert len(backup.list_backups(tmp_path / "r")) == 2


def test_every_stored_column_is_saved_and_restored(seeded):
    """Toutes les colonnes stockées (y compris TEXT à valeur par défaut) ; seules les colonnes générées sont exclues."""
    db, saved, tmp_path = seeded
    manifest = json.loads(zipfile.ZipFile(saved).read("manifest.json"))["tables"]
    assert {"adresse", "ville", "raison_sociale"} <= set(manifest["company"]["columns"])
    assert {"prenom", "fonction", "banque", "adresse"} <= set(manifest["employees"]["columns"])
    assert "cin_key" not in manifest["employees"]["columns"] and "open_key" not in manifest["payslips"]["columns"]
    assert {"rectification_reason", "inputs", "result"} <= set(manifest["payslips"]["columns"])
    from app.paie.services import master_data
    company, employee = master_data.get_company(db), master_data.list_employees(db)[0]
    backup.restore_backup(db, saved.read_bytes(), tmp_path / "backups", ACTOR)
    assert master_data.get_company(db) == company and master_data.list_employees(db)[0] == employee
    assert company.adresse == "12, rue de l'Exemple" and employee.prenom == "Salarié"
