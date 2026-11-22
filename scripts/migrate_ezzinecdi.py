#!/usr/bin/env python3
"""Migration ezzinecdi (data.json) -> échéances du salarié désigné (S5 / US-52). Voir app/migration/ezzinecdi.py.

Usage : python scripts/migrate_ezzinecdi.py --source <copie data.json> --matricule <M> [--target <url>]
                                            [--dry-run] [--backups backup_*.json ...] [--json rapport.json]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.migration.ezzinecdi import run  # noqa: E402
from app.paie.repositories.db import Database  # noqa: E402
from app.paie.services.errors import PayrollError  # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--matricule", required=True)
    p.add_argument("--target", default=os.environ.get("PAIE_DB_URL"))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--backups", type=Path, nargs="*", default=[])
    p.add_argument("--json", type=Path)
    a = p.parse_args(argv)
    db = Database(a.target, pooled=False) if a.target else None
    try:
        report = run(a.source, a.matricule, db, a.dry_run, a.backups)
    except PayrollError as exc:
        print(f"REFUS : {exc}", file=sys.stderr)
        return 1
    if a.json:
        a.json.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(f"{'Simulation' if a.dry_run else 'Import'} : {len(report['importables'])} échéance(s) importable(s), "
          f"{len(report['rejetes'])} rejetée(s), {len(report['doublons_ecartes'])} doublon(s), "
          f"{len(report['incoherences'])} incohérence(s), {len(report['simulation']['corrections'])} correction(s) proposée(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
