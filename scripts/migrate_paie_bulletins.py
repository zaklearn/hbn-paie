#!/usr/bin/env python3
"""Migration paie-bulletins (.db) -> base paie (S5 / US-51). Voir app/migration/paie_bulletins.py.

Usage : python scripts/migrate_paie_bulletins.py --source <copie.db> [--target <url>] [--dry-run] [--json rapport.json]
        (--target par défaut : PAIE_DB_URL ; jamais affiché)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.migration.paie_bulletins import run  # noqa: E402
from app.paie.repositories.db import Database  # noqa: E402
from app.paie.services.errors import PayrollError  # noqa: E402


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--target", default=os.environ.get("PAIE_DB_URL"))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--json", type=Path)
    a = p.parse_args(argv)
    db = Database(a.target, pooled=False) if a.target else None
    try:
        report = run(a.source, db, a.dry_run)
    except PayrollError as exc:
        print(f"REFUS : {exc}", file=sys.stderr)
        return 1
    text = json.dumps(report, ensure_ascii=False, indent=1, default=str)
    if a.json:
        a.json.write_text(text, encoding="utf-8")
    gaps = report["r0_recalcul"]["ecarts"]
    print(f"{'Simulation' if a.dry_run else 'Import'} : {report['decomptes_source']} ; R0.3 : "
          f"{report['r0_recalcul']['paies_verifiees']} paie(s) vérifiée(s), {len(gaps)} écart(s)")
    return 0 if not gaps else 3


if __name__ == "__main__":
    sys.exit(main())
