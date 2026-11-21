# Prompt Claude Code — Sprint S6 : déploiement, reprise réelle et mise en service

**Avant toute action**, lis `docs/claude-code/00_CADRE_COMMUN.md` (R0, R3 à R6), `PROJECT_STATE.md`, `BACKLOG.md`, `docs/sprints/S5_RAPPORT.md`, le dry-run S5 validé, et `TANGERINE_PROJECT_STATE.md` pour les conventions Traefik du VPS.

> **R0** : l'image de production contient le noyau vérifié (test d'intégrité exécuté au build). L'import réel recopie sans recalculer. Le contrôle R0.3 est rejoué sur la production avant la mise en service. Sans 0 écart, ou sans écarts acceptés par écrit par le propriétaire, pas de mise en service.

## Objectif
Mettre HBN Paie en service sur `https://paie.hbnfactory.cloud` avec les données réelles, sans impact sur le reste du VPS.

## Autorisations (étape par étape)
| Étape | Niveau | Condition |
|---|---|---|
| A. Construire l'image, préparer `/opt/hbnfactory/platforms/paie/` | L2 | « go S6 » |
| B. Créer la base `paie` et l'utilisateur dédié | **L3** | Accord explicite au moment de l'exécuter |
| C. Démarrer le conteneur | **L3** | Accord explicite |
| D. Importer les données réelles | **L3** | Dry-run S5 validé + nouvel accord |
| E. Recette, puis bascule | L0 / L2 | Validation du propriétaire |

## Étapes
**A — US-60**
- `Dockerfile` multi-stage sur le modèle de SmartCompta : `node:20-alpine` pour le build Vue, puis `python:3.12-slim`, avec `pytest tests/test_core_integrity.py` exécuté pendant le build (échec = image refusée). Utilisateur non root, `HEALTHCHECK /health`, 1 worker Uvicorn.
- `compose.yaml` (projet `hbn-paie`) :
  - service `paie`, `restart: unless-stopped`, `mem_limit: 512m`, **aucun port publié**, réseau externe `hbn-proxy` (et le réseau MySQL si S0 a établi que MySQL tourne en conteneur sur le VPS) ;
  - labels Traefik :
    ```
    traefik.enable=true
    traefik.http.routers.paie.rule=Host(`paie.hbnfactory.cloud`)
    traefik.http.routers.paie.entrypoints=websecure
    traefik.http.routers.paie.tls.certresolver=le
    traefik.http.routers.paie.middlewares=hbn-secure-headers@file
    traefik.http.services.paie.loadbalancer.server.port=8000
    ```
  - volumes : `data/backups` (0700), `data/logs`.
- `.env` (0600) généré par `scripts/gen-env.sh` : secrets forts, jamais affichés. `docker compose config -q` OK.

**B — US-61**
- `CREATE DATABASE paie CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci`.
- Utilisateur `paie_app` limité à `paie.*`, avec le droit `TRIGGER` si l'hébergeur l'accorde. Le compte d'administration sert une seule fois.
- `alembic upgrade head`.
- **Retour arrière** : `DROP DATABASE paie` + `DROP USER`, possible seulement tant qu'aucune donnée réelle n'est importée, et avec accord.

**C**
- `docker compose up -d`.
- Contrôles :
  - `http://` → 301, `https://` → 200, en-têtes de `hbn-secure-headers` ;
  - certificat `le` émis ;
  - aucun port hôte nouveau ;
  - Tangerine et portfolio toujours en 200 ;
  - mémoire au repos relevée.
- Création du premier superadmin en CLI.

**D — US-62**
- Sauvegarde de la base vide.
- Le propriétaire passe les apps Streamlit en lecture seule, ou les gèle.
- Nouvelles copies des sources (SHA-256 consignés), puis `migrate_paie_bulletins.py` et `migrate_ezzinecdi.py` sans `--dry-run`.
- Rapport de migration de production, au même format que S5. Il doit être identique au dry-run, sauf données ajoutées entre-temps, et R0.3 à 0 écart.
- **Retour arrière** : restauration de la sauvegarde de la base vide.

**E — US-63, US-64**
- Recette avec le propriétaire, sur la checklist R2 complète (une ligne par fonction des diagnostics) :
  - un bulletin réel clôturé, téléchargé, puis comparé au PDF d'origine ;
  - un mois déclaré, une échéance payée puis dévalidée ;
  - les exports Excel et ICS ouverts.
- Mesures : mémoire, temps de génération d'un PDF.
- Une **sauvegarde de production** est réalisée et testée par une restauration sur une base de dev.
- Documentation `docs/EXPLOITATION.md` : état, redémarrage (`docker compose restart`, jamais `down -v`), sauvegarde, restauration, création d'utilisateur, nouvelle version de paramètres.
- Mise à jour de `PROJECT_STATE.md` et, côté HBNFACTORY, ajout de la plateforme `paie` à l'état du VPS.

## Definition of Done
Service en HTTPS, données réelles importées avec R0.3 à 0 écart, recette signée, sauvegarde de production testée, aucun impact sur Tangerine ni sur le portfolio.

## Livrable
`docs/sprints/S6_RAPPORT.md` (ligne R0, tableau des opérations avec niveau, date et résultat). Tag `v1.0.0`.

## Point d'arrêt
STOP après la mise en service. Toute évolution ultérieure passe par un nouveau sprint validé.
