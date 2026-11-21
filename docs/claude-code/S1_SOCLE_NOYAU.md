# Prompt Claude Code — Sprint S1 : socle backend et noyau paie gelé

**Avant toute action**, lis `docs/claude-code/00_CADRE_COMMUN.md` (R0 en premier), `PROJECT_STATE.md`, `BACKLOG.md` et `docs/sprints/S0_RAPPORT.md`.

> **R0 en une phrase** : le noyau de calcul de paie-bulletins est copié octet pour octet, seuls les imports `src.` changent. Il n'est ni corrigé, ni optimisé, ni harmonisé avec SmartCompta. Toute divergence ferait sortir les bulletins des montants déclarés en comptabilité (CNSS, AMO, IR).

## Objectif
Un backend FastAPI qui démarre, avec le noyau paie gelé, protégé par un contrôle d'intégrité bloquant, et ses tests d'origine au vert.

## Autorisations
L1 uniquement (dépôt + environnement de dev). MySQL de test : conteneur `mysql:8.4` (Q1) sur la machine de développement. Si le seul environnement disponible est le VPS : projet compose `hbn-paie-dev`, limite 256 Mo, aucun port public, arrêté après les tests. Signale-le dans le rapport.

## Stories
1. **US-10** : arborescence `backend/app/` :
   - `core/` : config pydantic-settings (variables `PAIE_DB_URL`, `PAIE_SECRET_KEY`, `PAIE_SEED_DEMO`…), logs, erreurs ;
   - `db/` : moteur SQLAlchemy, `pool_pre_ping`, `pool_recycle` ;
   - `paie/`, `tresorerie/`, `socle/` ;
   - `main.py` avec `/health` et `/api/health`.
   
   Reprends les conventions de structure de SmartCompta, **pas son code paie ni son authentification** (R0.2, R7).
2. **US-11** : copie les 10 fichiers listés en R0.1 depuis `upstream/paie-bulletins/src/` vers `backend/app/paie/core/` (arborescence conservée : `calculations/`, `models/`, `validation/`, `pdf/`, `formatting.py`). Seule modification : `from src.` → `from app.paie.core.`. Génère `UPSTREAM.sha256` (contenu normalisé). Écris `scripts/check_core_integrity.py` et `tests/test_core_integrity.py`. Démontre dans le rapport qu'une modification volontaire d'un caractère dans `engine.py` fait échouer le test, puis annule-la.
3. **US-12** : porte dans `backend/tests/paie/` les tests qui ne dépendent ni de Streamlit ni de SQLite : `test_engine.py`, `test_ecarts_pdf.py`, `test_pdf.py`, `test_reference_excel.py`, `golden_scenarios.py` + `golden/results.json`, et la partie moteur de `test_non_regression.py`. Seuls les imports changent. **Interdit de modifier une valeur attendue.** Si un test échoue, la cause est dans le portage, jamais dans l'attendu. Si `PAIE_REFERENCE_XLSX` est fourni (S0, US-05), le test Excel doit passer.
4. **US-13** : `alembic init`, première révision vide, `docker-compose.dev.yml` (MySQL 8.4 de test), commande unique `make test` (ou script équivalent).

## Consignes
- Dépendances de calcul aux versions compatibles avec l'original : ReportLab `>=4.0,<6`, pandas, openpyxl. Fige les versions dans `requirements.txt`.
- Aucun calcul de paie hors de `app/paie/core/`.

## Definition of Done
- `make test` est vert.
- Le test d'intégrité passe.
- Le nombre de tests du noyau portés est égal à celui de la référence S0 pour ces fichiers.
- `/health` répond 200.

## Livrable
`docs/sprints/S1_RAPPORT.md` avec la ligne « R0 : intégrité du noyau OK (10 fichiers), golden OK (n cas), Excel OK / non fourni ». Mise à jour de `PROJECT_STATE.md`, `BACKLOG.md` et `CHANGELOG.md`. Tag `sprint-S1`.

## Point d'arrêt
STOP. Attends le « go S2 ».
