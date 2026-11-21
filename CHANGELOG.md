# Changelog — HBN Paie

## S2 — Paie sur MySQL (21/11/2026, tag `sprint-S2`)
- Schéma paie MySQL 8.4 (Alembic 0002) : contraintes, colonnes générées, 6 déclencheurs SIGNAL ; socle users/sessions (0003).
- Dépôts et services de paie-bulletins portés en logique identique (écarts listés, réversibles, testés).
- Comptes nominatifs superadmin/user, sessions httpOnly, CLI du premier superadmin.
- API REST paie et socle ; montants en chaînes décimales ; rôle user refusé côté API.
- Tests : workflow 35, pdf 9, services 10 (+2 → S5), 24 violations, 27 API, équivalence PDF avec l'original.

## S1 — socle backend et noyau gelé (21/11/2026, tag `sprint-S1`)
- Remesure de la référence en Python 3.12 : 238 + 1 ignoré / 9, identique à 3.14.
- Squelette FastAPI (`/health`, `/api/health`), config `PAIE_*`, moteur SQLAlchemy.
- Noyau paie gelé (10 fichiers) + `UPSTREAM.sha256` + contrôle d'intégrité bloquant.
- Tests du noyau portés (92 + 1 ignoré) + preuve de fidélité du portage ; `test_pdf` reporté en S2.
- Environnement de dev `hbn-paie-dev` (Python 3.12, MySQL 8.4), Alembic (révision 0001 vide), `scripts/dev-test.sh`.

## S0 — cadrage (21/11/2026, tag `sprint-S0`)
- Squelette du dépôt, sources gelées dans `upstream/` (+ `MANIFEST.sha256`), pack de prompts dans `docs/claude-code/`.
- Référence de tests mesurée : 238 + 1 ignoré (paie), 9 (trésorerie).
- Dossiers L2 `/opt/hbnfactory/platforms/paie/` et `migration/sources/`.
- Bloqué : US-02 (MySQL), US-05 (données), création GitHub.
