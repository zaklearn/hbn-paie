#!/usr/bin/env python3
"""Reconstitution d'un data.json ezzinecdi À PARTIR D'UNE DÉCLARATION DU PROPRIÉTAIRE (le fichier d'origine
étant perdu : stockage local éphémère de Streamlit Cloud, sans Google Drive).

Format d'origine (9 champs), produit par les fonctions du legacy : ``db_gen.ajouter_mois`` (gabarit, montants,
rappel J-1, numérotation) et ``integrity.regularite`` / ``statut_paye`` (statut au jour).
Règle déclarée : une échéance est payée si sa date est <= ``--payees-jusqu-au`` ; date de paiement = date
d'échéance (« à temps ») ; observation d'origine suivie de la mention de reconstitution.

Usage : python scripts/reconstituer_ezzinecdi.py --debut 2026-07 --fin 2026-11 --payees-jusqu-au 2026-11-22 \
            --declaration 2026-11-22 --out data_reconstitue.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.tresorerie.legacy import db_gen, integrity  # noqa: E402


def months(start: str, end: str):
    y, m = map(int, start.split("-"))
    ey, em = map(int, end.split("-"))
    while (y, m) <= (ey, em):
        yield y, m
        y, m = (y + (m == 12), m % 12 + 1)


def main(argv=None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--debut", required=True)
    p.add_argument("--fin", required=True)
    p.add_argument("--payees-jusqu-au", required=True, type=dt.date.fromisoformat)
    p.add_argument("--declaration", required=True, type=dt.date.fromisoformat)
    p.add_argument("--out", required=True, type=Path)
    a = p.parse_args(argv)
    data = db_gen.base_vide()
    for y, m in months(a.debut, a.fin):
        data, ok, msg = db_gen.ajouter_mois(data, y, m)
        assert ok, msg
    mention = f"reconstitué sur déclaration du propriétaire du {a.declaration.strftime('%d/%m/%Y')}"
    for rec in data:
        if rec["date_echeance"] <= a.payees_jusqu_au.isoformat():
            reg = integrity.regularite(rec["date_echeance"], rec["date_echeance"])
            rec["statut"] = integrity.statut_paye(reg)
            rec["date_paiement"] = rec["date_echeance"]
            d = dt.date.fromisoformat(rec["date_echeance"]).strftime("%d/%m/%Y")
            rec["observations"] = f"Payé le {d} ({reg}) — {mention}"
    clean, rep = integrity.reconcile([dict(r) for r in data], a.declaration)
    assert not rep["modifie"], rep                      # fichier conforme aux règles d'origine
    fd = a.out.open("x", encoding="utf-8")
    with fd:
        json.dump(data, fd, ensure_ascii=False, indent=1)
    a.out.chmod(0o600)
    payes = sum(1 for r in data if integrity.est_paye(r))
    print(f"{a.out.name} : {len(data)} échéances, {payes} payées, {len(data) - payes} non payées")
    return 0


if __name__ == "__main__":
    sys.exit(main())
