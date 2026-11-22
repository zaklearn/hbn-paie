# Changelog — HBN Paie

## v1.0.0 — Mise en service (22/11/2026)
- Recette fonctionnelle (checklist R2) validée par le propriétaire.

## S6 — Déploiement et reprise réelle (22/11/2026)
- Dockerfile multi-stage (SPA, test d'intégrité du noyau bloquant, runtime non root), compose de production, gen-env.sh.
- Mise en service https://paie.hbnfactory.cloud (Traefik, LE), MySQL dédié paie-db, superadmin.
- Import réel (paie-bulletins + trésorerie reconstituée) et reprise par reclôture ; R0.3 0 écart.
- Sauvegarde de production testée ; docs/EXPLOITATION.md ; checklist de recette S6_RECETTE.md.

## S5 — Sauvegarde, restauration et migration (22/11/2026, tag `sprint-S5`)
- Sauvegarde/restauration de la base paie : fichier .zip avec manifeste, validation avant action, sauvegarde de sécurité, CLI, API, écran.
- Outil de migration paie-bulletins (.db) : import à l'identique, ids conservés, R0.3 en lecture seule.
- Outil de migration ezzinecdi (data.json) : plan v1, simulation de la réconciliation, anomalies listées.
- Essai à blanc rejouable (sources de substitution) : `docs/sprints/S5_MIGRATION_DRYRUN.md`.
- Correctif : colonnes TEXT à valeur par défaut incluses dans les sauvegardes ; .gitignore limité aux dossiers de données.

## S4 — Interface Vue 3 (21/11/2026, tag `sprint-S4`)
- SPA Vite + Vue 3 + TS + Pinia + Tailwind : menu 6 entrées, barre de contexte (période, salarié) dans l'URL, rôles.
- Tableau de bord, Trésorerie (4 onglets, mobile), Paie du mois (étapes), Salariés (fiche à onglets), Bulletins & exports, Configuration.
- Aucun calcul en JS : aperçu, totaux, régularité et rapprochement fournis par l'API.
- Vitest (21), e2e Playwright de dev (3) et captures des 5 écrans ; SPA servie par FastAPI à la racine.

## S3 — Trésorerie multi-salariés (21/11/2026, tag `sprint-S3`)
- Legacy ezzinecdi (db_gen, integrity, rapport, dates) repris à l'identique ; 9/9 tests d'origine.
- Plans de versement par salarié versionnés et immuables ; échéances par salarié avec verrou optimiste.
- Déclarer (tous les actifs ou un salarié), payer (statut au jour), dévalider, régularisation, conflit 409.
- Réconciliation au plan en simulation ; exports Excel/ICS d'origine par salarié.
- Rapprochement versé/net et CNSS/cotisations en lecture seule, avertissement de clôture ; API /api/tresorerie/*.

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
