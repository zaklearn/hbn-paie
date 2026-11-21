# HBN Paie — état du projet

| Champ | Valeur |
|---|---|
| Sprint courant | S0 — cadrage **terminé** (US-02, US-05 bloquées en attente du propriétaire) — tag `sprint-S0` |
| Prochaine action autorisée | Push de `main` + `sprint-S0` via la clé de déploiement (Q2), puis S1 (feu vert donné, conditionné au push) |

## Décisions validées
- Conception v2.1 (D1–D9), `docs/reference/PAIE_FUSION_CONCEPTION.md` ; cadre R0–R9, `docs/claude-code/00_CADRE_COMMUN.md`.

## Décisions du propriétaire sur le rapport S0 (21/11/2026)
- **Q1 — DÉCISION VALIDÉE, remplace D2** : MySQL **dédié** `paie-db` (`mysql:8.4`) dans le compose de la plateforme paie ; réseau `paie-internal` seul, aucun port publié, volume `data/mysql` ; `innodb_buffer_pool_size=128M`, `performance_schema=OFF`, `max_connections=30`, `mem_limit: 384m` (consommation au repos à mesurer). Identifiants root et `paie_app` générés par `scripts/gen-env.sh` dans `.env` (0600), jamais affichés ; pas de dossier `secrets/`. Jusqu'à S5 : MySQL 8.4 de test dans `hbn-paie-dev` uniquement ; MySQL de production = étape L3 de S6. Portfolio et `portfolio-internal` jamais touchés. S6 adapté (`docs/claude-code/S6_DEPLOIEMENT.md`).
- **Q2 — DÉCISION VALIDÉE** : clé de déploiement SSH ed25519 `/root/.ssh/hbn-paie-deploy` (écriture), dépôt privé `zaklearn/hbn-paie` créé par le propriétaire ; pas de `gh`.
- **Q3 — DÉCISION VALIDÉE** : tests en `python:3.12-slim` dans `hbn-paie-dev` ; dépendances figées aux versions de la mesure (reportlab 5.1.0, pandas 3.1.1, openpyxl 3.1.5) si disponibles en 3.12, sinon signaler avant de choisir ; remesure attendue 238 + 1 ignoré / 9 ; tout écart 3.14 ↔ 3.12 sur les tests paie = STOP (R0).
- **Q4** : US-05 reste Bloqué jusqu'au dépôt des fichiers et du matricule ; ne bloque pas S1.
- **Q5 — FAIT** : `docs/reference/` (diagnostics 1–3, conception, maquettes) versionné.
- **Alerte ezzinecdi** : traitée par le propriétaire. **La référence gelée reste celle de `upstream/` et de `upstream/MANIFEST.sha256`, même si l'historique GitHub d'ezzinecdi est réécrit** (le commit `85354c9c…` pourra ne plus exister sur GitHub).

## Faits vérifiés (21/11/2026)
- DNS `paie.hbnfactory.cloud` → 2.25.6.153 = IP du VPS (local, 1.1.1.1, 8.8.8.8).
- VPS : 3,8 Gio RAM (2,0 disponibles), 1 vCPU, 23 Go libres. Traefik v3.7.19 : résolveur `le`, middleware `hbn-secure-headers@file`, réseau `hbn-proxy`.
- MySQL WordPress = conteneur `hbn-portfolio-db-1` (mysql 8.4.13), réseau `portfolio-internal` seul, aucun port publié.
- Sources gelées : paie-bulletins `df7ff126…` (78 fichiers), ezzinecdi `85354c9c…` (11 fichiers) ; `upstream/MANIFEST.sha256` = `dabd124c…148d`.
- Référence R0.3 (Python 3.14.4) : paie-bulletins 238 passés + 1 ignoré (Excel absent) ; ezzinecdi 9 passés ; golden 6 scénarios.
- Dossiers VPS : `/opt/hbnfactory/platforms/paie/` (0750), `migration/sources/` (0700).

## À confirmer
- Ajout de la clé publique de déploiement (écriture) dans GitHub par le propriétaire, puis push.
- Q4 : fichiers sources + matricule (US-05).
