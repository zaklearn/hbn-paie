# Prompt Claude Code — Sprint S6 : déploiement, reprise réelle et mise en service

**Avant toute action**, lis `docs/claude-code/00_CADRE_COMMUN.md` (R0, R3 à R6), `PROJECT_STATE.md`, `BACKLOG.md`, `docs/sprints/S5_RAPPORT.md`, le dry-run S5 validé, et `TANGERINE_PROJECT_STATE.md` pour les conventions Traefik du VPS.

> **R0** : l'image de production contient le noyau vérifié (test d'intégrité exécuté au build). L'import réel recopie sans recalculer. Le contrôle R0.3 est rejoué sur la production avant la mise en service. Sans 0 écart, ou sans écarts acceptés par écrit par le propriétaire, pas de mise en service.

> **Amendement Q1 (21/11/2026, décision du propriétaire, remplace D2)** : MySQL **dédié** `paie-db` dans le projet compose de la plateforme paie. Le MySQL du portfolio (`hbn-portfolio-db-1`) et son réseau `portfolio-internal` ne sont **jamais** utilisés ni modifiés.

## Objectif
Mettre HBN Paie en service sur `https://paie.hbnfactory.cloud` avec les données réelles, sans impact sur le reste du VPS.

## Autorisations (étape par étape)
| Étape | Niveau | Condition |
|---|---|---|
| A. Construire l'image, préparer `/opt/hbnfactory/platforms/paie/` | L2 | « go S6 » |
| B. Créer le service MySQL de production `paie-db`, la base `paie` et l'utilisateur dédié | **L3** | Accord explicite au moment de l'exécuter |
| C. Démarrer le conteneur | **L3** | Accord explicite |
| D. Importer les données réelles | **L3** | Dry-run S5 validé + nouvel accord |
| E. Recette, puis bascule | L0 / L2 | Validation du propriétaire |

## Étapes
**A — US-60**
- `Dockerfile` multi-stage sur le modèle de SmartCompta : `node:20-alpine` pour le build Vue, puis `python:3.12-slim`, avec `pytest tests/test_core_integrity.py` exécuté pendant le build (échec = image refusée). Utilisateur non root, `HEALTHCHECK /health`, 1 worker Uvicorn.
- `compose.yaml` (projet `hbn-paie`) :
  - service `paie`, `restart: unless-stopped`, `mem_limit: 512m`, **aucun port publié**, réseaux : externe `hbn-proxy` + interne `paie-internal` ;
  - service `paie-db` : image `mysql:8.4`, `restart: unless-stopped`, `mem_limit: 384m`, réseau `paie-internal` **uniquement** (`internal: true`), **aucun port publié**, volume `data/mysql` (0700), healthcheck `mysqladmin ping` ; réglages basse mémoire `--innodb-buffer-pool-size=128M --performance-schema=OFF --max-connections=30` ; `paie` dépend de `paie-db` (`condition: service_healthy`) ;
  - labels Traefik :
    ```
    traefik.enable=true
    traefik.http.routers.paie.rule=Host(`paie.hbnfactory.cloud`)
    traefik.http.routers.paie.entrypoints=websecure
    traefik.http.routers.paie.tls.certresolver=le
    traefik.http.routers.paie.middlewares=hbn-secure-headers@file
    traefik.http.services.paie.loadbalancer.server.port=8000
    ```
  - volumes : `data/mysql` (0700, `paie-db`), `data/backups` (0700), `data/logs`.
- `.env` (0600) généré par `scripts/gen-env.sh` : secrets forts, dont `MYSQL_ROOT_PASSWORD` et le mot de passe de `paie_app`, jamais affichés. Aucun compte à déposer, pas de dossier `secrets/`. `docker compose config -q` OK.

**B — US-61**
- `docker compose up -d paie-db` ; mesure de la consommation mémoire réelle au repos (`docker stats --no-stream`), consignée dans le rapport.
- `CREATE DATABASE paie CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci`.
- Utilisateur `paie_app` limité à `paie.*`, avec le droit `TRIGGER` (MySQL dédié : accordé). Le compte root sert uniquement à cette initialisation.
- `alembic upgrade head`.
- **Retour arrière** : `docker compose stop paie-db` puis suppression de `data/mysql`, possible seulement tant qu'aucune donnée réelle n'est importée, et avec accord (R5).

**C**
- `docker compose up -d`.
- Contrôles :
  - `http://` → 301, `https://` → 200, en-têtes de `hbn-secure-headers` ;
  - certificat `le` émis ;
  - aucun port hôte nouveau ;
  - Tangerine et portfolio toujours en 200 ; `portfolio-internal` inchangé (aucun conteneur paie connecté) ;
  - mémoire au repos relevée.
- Création du premier superadmin en CLI.

**D — US-62**
- Sauvegarde de la base vide (`paie-backup` : `mysqldump` exécuté dans `paie-db`, fichier 0600 dans `data/backups`).
- Le propriétaire passe les apps Streamlit en lecture seule, ou les gèle.
- Nouvelles copies des sources (SHA-256 consignés), puis `migrate_paie_bulletins.py` et `migrate_ezzinecdi.py` sans `--dry-run`.
- Rapport de migration de production, au même format que S5. Il doit être identique au dry-run, sauf données ajoutées entre-temps, et R0.3 à 0 écart.
- **Retour arrière** : restauration de la sauvegarde de la base vide dans `paie-db` (`paie-restore`, sauvegarde automatique avant).

**E — US-63, US-64**
- Recette avec le propriétaire, sur la checklist R2 complète (une ligne par fonction des diagnostics) :
  - un bulletin réel clôturé, téléchargé, puis comparé au PDF d'origine ;
  - un mois déclaré, une échéance payée puis dévalidée ;
  - les exports Excel et ICS ouverts.
- Mesures : mémoire, temps de génération d'un PDF.
- Une **sauvegarde de production** de `paie-db` est réalisée et testée par une restauration sur le MySQL 8.4 de `hbn-paie-dev`.
- Documentation `docs/EXPLOITATION.md` : état des services `paie` et `paie-db`, redémarrage (`docker compose restart`, jamais `down -v`), sauvegarde, restauration, création d'utilisateur, nouvelle version de paramètres.
- Mise à jour de `PROJECT_STATE.md` et, côté HBNFACTORY, ajout de la plateforme `paie` à l'état du VPS.

## Definition of Done
Service en HTTPS, données réelles importées avec R0.3 à 0 écart, recette signée, sauvegarde de production testée, aucun impact sur Tangerine ni sur le portfolio.

## Livrable
`docs/sprints/S6_RAPPORT.md` (ligne R0, tableau des opérations avec niveau, date et résultat). Tag `v1.0.0`.

## Point d'arrêt
STOP après la mise en service. Toute évolution ultérieure passe par un nouveau sprint validé.
