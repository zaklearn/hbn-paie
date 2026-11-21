# S1 — Rapport : socle backend et noyau paie gelé (21/11/2026)

**R0 : intégrité du noyau OK (10 fichiers), golden OK (6 cas + contrôle de couverture), Excel non fourni (1 test ignoré, comme la référence).**

## Résultats
| Story | Statut | Preuve |
|---|---|---|
| Q3 | Fait | Remesure en **Python 3.12.16**, image `hbn-paie-dev-ref`, versions de S0 imposées et identiques. paie-bulletins : **238 réussis, 1 ignoré**. ezzinecdi : **9 réussis**. Résultats **identiques test par test** à 3.14 (`S1_reference_py312.txt`) |
| US-10 | Fait | `backend/app/` contient `core/` (config `PAIE_*` pydantic-settings, secrets en `SecretStr`, logs, erreurs), `db/` (SQLAlchemy 2, `pool_pre_ping`, `pool_recycle=3600`), `paie/`, `tresorerie/`, `socle/` et `main.py`. Uvicorn, 1 worker : `/health` → 200 `{"status":"ok"}`, `/api/health` → 200 |
| US-11 | Fait | 10 fichiers copiés : seul `from src.` → `from app.paie.core.` (14 imports réécrits), rien d'autre. `UPSTREAM.sha256` est calculé sur `df7ff12`. `scripts/check_core_integrity.py` refuse aussi les fichiers ajoutés dans le noyau et les `__init__.py` modifiés, et vérifie `UPSTREAM.sha256` contre `upstream/`. **Démonstration** : `engine.py` l. 36, `, 2)` → `, 3)`, donne « MODIFIÉ : calculations/engine.py », 1 échec ; après restauration, 3 réussis (`S1_integrity_tamper_demo.txt`) |
| US-12 | Fait, **sauf `test_pdf.py`** (reporté) | `tests/paie/` : `test_engine` 40, `test_ecarts_pdf` 7, `test_reference_excel` 39 (dont 1 ignoré), `test_non_regression` 7, `golden_scenarios.py` et `golden/results.json` (identique octet pour octet). Total : **92 réussis et 1 ignoré, avec les mêmes identifiants** que la référence 3.12. **Aucune valeur attendue modifiée** : `test_port_fidelity.py` inverse la table d'imports et compare chaque fichier octet pour octet à l'original (8 tests) |
| US-13 | Fait | `docker-compose.dev.yml` (projet `hbn-paie-dev`) : MySQL **8.4.13** et Python 3.12 sur un réseau interne, aucun port, 256 Mo par service, données sur tmpfs, arrêt systématique. `alembic init` + révision `0001` vide ; `alembic upgrade head` sur base vide testé. Commande unique : `scripts/dev-test.sh`, que `make test` appelle (`make` est absent du VPS) |

**Suite complète (`scripts/dev-test.sh`) : 107 réussis, 1 ignoré.** Elle se décompose ainsi :
- 92 tests du noyau ;
- 8 tests de fidélité du portage ;
- 3 tests d'intégrité ;
- 2 tests de santé ;
- 2 tests MySQL / Alembic ;
- 1 test ignoré : la référence Excel.

## Écarts et décisions d'exécution (à valider)
1. **`test_pdf.py` (9 tests) est reporté en S2 (ACTION REPORTÉE).**
   - **Le problème :** le prompt S1 le classe parmi les tests « sans Streamlit ni SQLite ». Or tous ses tests utilisent la fixture `september`, qui clôture des paies via `payroll` et `master_data` sur SQLite. Ces services ne seront portés qu'en S2.
   - **Ce qui sera fait :** il sera porté en S2 avec les services, sans changer d'attendu.
   - **Conséquence :** pour les fichiers listés en S1, 93 tests sont portés sur les 102 de la référence. Les 9 manquants sont tous ceux de `test_pdf`.
2. **Constantes de démonstration.**
   - **Le problème :** `golden_scenarios.py` et les fixtures importent `REFERENCE_INPUT` depuis `services/demo.py`, qui dépend de SQLite.
   - **La solution :** les 3 constantes sont recopiées à l'identique dans `tests/paie/demo_reference.py`. Un test vérifie leur AST contre l'original. Le `conftest.py` ne reprend que les fixtures sans base (`ACTOR`, `params`, `ref_input`, `money`), elles aussi contrôlées par AST.
   - **En S2 :** quand `demo.py` sera porté tel quel, les imports y reviendront et ce fichier sera supprimé.
3. **MySQL de dev.**
   - **Mesure :** 225 Mio au repos sur 256, sans aucun OOM. Le processus occupe ≈116 Mio ; le tmpfs des données ≈103 Mio, et ce tmpfs est compté dans la mémoire du conteneur.
   - **Réglages propres au dev :** pour tenir dans 256 Mo, `innodb_buffer_pool_size=64M` (la production gardera vos 128M) et journal redo de 8 Mo.
   - **Production :** `paie-db` aura un volume disque. Sa consommation réelle sera mesurée en S6.
4. **Avertissement non bloquant :** Starlette signale que son `TestClient` basé sur `httpx` est déprécié. C'est sans effet aujourd'hui ; à surveiller lors d'une future montée de version.

## Sécurité et périmètre
- **Aucun secret versionné :** le mot de passe MySQL de test est aléatoire, éphémère et jamais affiché.
- **Aucune action hors du dépôt et de `hbn-paie-dev` :** Traefik, Tangerine, le portfolio et `/opt/hbnfactory/platforms/paie/` sont inchangés. Plus aucun conteneur `hbn-paie-dev` ne tourne.
- **Images de dev présentes :** `hbn-paie-dev-ref` (1,09 Go), `hbn-paie-dev-test` (571 Mo), `mysql:8.4` (1,12 Go) et `python:3.12-slim`. Il reste 20 Go libres sur le disque.

## Questions au propriétaire
1. Validez-vous le report de `test_pdf.py` en S2 et la solution `demo_reference.py` (points 1 et 2) ?
2. Le push n'est pas fait : faut-il pousser `main` et le tag `sprint-S1` ?
