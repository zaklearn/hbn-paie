# HBN Paie — état du projet

| Champ | Valeur |
|---|---|
| Sprint courant | S5 — Sauvegarde et migration **terminé** — tag `sprint-S5` |
| Prochaine action autorisée | Validation du rapport d'essai à blanc réel par le propriétaire, puis « go S6 » |

## Décisions validées
- Conception v2.1 (D1–D9), `docs/reference/PAIE_FUSION_CONCEPTION.md` ; cadre R0–R9, `docs/claude-code/00_CADRE_COMMUN.md`.

## Décisions du propriétaire
- **S4 (21/11/2026)** : écarts 1–4 validés (observation automatique, onglets en haut sur mobile, nets du mois = plans, taux en décimal exact).
- **S3 (21/11/2026)** : écarts 1–6 validés (date de paiement saisie, régularisation −2/+2, CNSS en information, UID ICS, import/remplacement en S5, montants du gabarit au plan).
- **S2 (21/11/2026)** : `PAIE_SEED_DEMO=0` par défaut validé ; scripts reset_production / supprimer_demo (Windows, SQLite) abandonnés.

### Sur le rapport S0 (21/11/2026)
- **Q1 — DÉCISION VALIDÉE, remplace D2** : MySQL **dédié** `paie-db` (`mysql:8.4`) dans le compose de la plateforme paie ; réseau `paie-internal` seul, aucun port publié, volume `data/mysql` ; `innodb_buffer_pool_size=128M`, `performance_schema=OFF`, `max_connections=30`, `mem_limit: 384m` (consommation au repos à mesurer). Identifiants root et `paie_app` générés par `scripts/gen-env.sh` dans `.env` (0600), jamais affichés ; pas de dossier `secrets/`. Jusqu'à S5 : MySQL 8.4 de test dans `hbn-paie-dev` uniquement ; MySQL de production = étape L3 de S6. Portfolio et `portfolio-internal` jamais touchés. S6 adapté (`docs/claude-code/S6_DEPLOIEMENT.md`).
- **Q2 — DÉCISION VALIDÉE** : clé de déploiement SSH ed25519 `/root/.ssh/hbn-paie-deploy` (écriture), dépôt privé `zaklearn/hbn-paie` créé par le propriétaire ; pas de `gh`.
- **Q3 — DÉCISION VALIDÉE** : tests en `python:3.12-slim` dans `hbn-paie-dev` ; dépendances figées aux versions de la mesure (reportlab 5.1.0, pandas 3.1.1, openpyxl 3.1.5) si disponibles en 3.12, sinon signaler avant de choisir ; remesure attendue 238 + 1 ignoré / 9 ; tout écart 3.14 ↔ 3.12 sur les tests paie = STOP (R0).
- **Q4** : US-05 reste Bloqué jusqu'au dépôt des fichiers et du matricule ; ne bloque pas S1.
- **Q5 — FAIT** : `docs/reference/` (diagnostics 1–3, conception, maquettes) versionné.
- **Alerte ezzinecdi** : traitée par le propriétaire. **La référence gelée reste celle de `upstream/` et de `upstream/MANIFEST.sha256`, même si l'historique GitHub d'ezzinecdi est réécrit** (le commit `85354c9c…` pourra ne plus exister sur GitHub).

- **Reprise des données — DÉCISIONS VALIDÉES (22/11/2026)** :
  - data.json d'ezzinecdi PERDU (application en stockage local sans [gdrive], disque éphémère Streamlit). Trésorerie **reconstituée sur déclaration** du propriétaire : juillet → novembre 2026 (embauche 01/07/2026), plan 2 500 / 1 500 / 2 500 / 2 000 ; payés : tous les versements de juillet à octobre, et 1er + CNSS + 2e de novembre ; 3e de novembre (30/11) à venir ; date de paiement = date d'échéance (« Payé – à temps ») avec mention « reconstitué sur déclaration du propriétaire du 22/11/2026 ». Fichier : `migration/sources/data_reconstitue_20261122.json` (+ provenance), généré par `scripts/reconstituer_ezzinecdi.py` (fonctions d'origine).
  - Paie : import de la sauvegarde du 27/10 puis **reclôture dans HBN Paie** (juillet–septembre recalculés si nécessaire selon la procédure d'origine puis clôturés ; octobre créé avec la saisie de septembre et clôturé). Les 4 PDF d'origine (clôturés le 06/11/2026) sont archivés comme **référence** (`migration/sources/reference/`, SHA256SUMS).

## Faits vérifiés (21/11/2026)
- DNS `paie.hbnfactory.cloud` → 2.25.6.153 = IP du VPS (local, 1.1.1.1, 8.8.8.8).
- VPS : 3,8 Gio RAM (2,0 disponibles), 1 vCPU, 23 Go libres. Traefik v3.7.19 : résolveur `le`, middleware `hbn-secure-headers@file`, réseau `hbn-proxy`.
- MySQL WordPress = conteneur `hbn-portfolio-db-1` (mysql 8.4.13), réseau `portfolio-internal` seul, aucun port publié.
- Sources gelées : paie-bulletins `df7ff126…` (78 fichiers), ezzinecdi `85354c9c…` (11 fichiers) ; `upstream/MANIFEST.sha256` = `dabd124c…148d`.
- Référence R0.3 (Python 3.14.4) : paie-bulletins 238 passés + 1 ignoré (Excel absent) ; ezzinecdi 9 passés ; golden 6 scénarios.
- Dossiers VPS : `/opt/hbnfactory/platforms/paie/` (0750), `migration/sources/` (0700).

- **S1 (21/11/2026)** : référence remesurée en Python 3.12.16 = 238 + 1 ignoré / 9, identique test par test à 3.14. Noyau gelé copié (10 fichiers, 14 imports réécrits) ; `UPSTREAM.sha256` + test bloquant ; altération détectée. Tests noyau portés : 92 + 1 ignoré, identifiants identiques à la référence. Suite complète : 107 + 1 ignoré. `/health` 200 sous Uvicorn. MySQL dev 8.4.13 : 225 Mio / 256 au repos (processus ≈116 Mio), 0 OOM.

- **S2 (21/11/2026)** : schéma MySQL (Alembic 0002/0003), 6 déclencheurs SIGNAL aux messages d'origine, dépôts et services portés (écarts listés et réversibles, `scripts/port_sources.py`), comptes/rôles/sessions, API `/api/paie/*`. Suite : 222 passés + 3 ignorés. Bulletins de la démo juillet–septembre 2026 : texte PDF, résultats, cumuls et copies figées identiques à l'original.

- **S3 (21/11/2026)** : legacy ezzinecdi copié (imports seuls modifiés), 9/9 tests d'origine ; plans de versement immuables, échéances par salarié (version, source_ref) ; réconciliation au plan en simulation ; exports d'origine par salarié ; rapprochement en lecture seule branché en avertissement. Test R0 : paie clôturée identique avec et sans écart de trésorerie. Suite : 265 passés + 3 ignorés.

- **S4 (21/11/2026)** : SPA Vue 3 (6 menus, barre de contexte URL, StatusBadge commun, rôles), 5 écrans des maquettes, aucun calcul en JS (grep documenté), totaux du tableau de bord côté serveur ; Vitest 21, e2e Playwright 3 (parcours complet, 390 px, rôle user), captures dans `docs/sprints/S4_captures/` ; backend 269 + 3 ignorés.

- **S5 (22/11/2026)** : sauvegarde/restauration (.zip, manifeste, validation avant action, sécurité, CLI/API/écran) ; outils `migrate_paie_bulletins.py` et `migrate_ezzinecdi.py` (simulation et import, ids conservés, R0.3) ; essai à blanc rejouable sur sources de substitution : 5 paies vérifiées, 0 écart ; suite 298 + 1 ignoré.

- **US-05 (22/11/2026), source (a) reçue** : `migration/sources/paie_20261027_003333_147569_manuelle.db` (0600, 94 208 octets, SHA-256 `18adadc1d55f6397221e8160d86e373fdce91cd91d9eaa7f90b06dc539ecfef0`). Sauvegarde paie-bulletins du 27/10/2026 00:33 : schéma v1, intègre, protections d'origine exactes ; 1 entreprise réelle (logo), 1 salarié (matricule 181159983, embauche 01/07/2026), 1 version de paramètres (2000-01, défaut), 3 paies juillet–septembre 2026 **calculées, non clôturées**, 0 PDF, 9 entrées de journal. Acceptée par `migrate_paie_bulletins.py` (simulation) ; recalcul des 3 paies identique chaîne par chaîne. Points : sauvegarde possiblement ancienne (à refaire si activité après le 27/10) ; matricule ezzinecdi présumé 181159983 (à confirmer).

- **US-05 (22/11/2026), pièces complémentaires analysées** (copies, lecture seule, non versionnées) : 4 bulletins PDF `bulletin_2026-07…10_181159983.pdf` — **clôturés le 06/11/2026**, version 1, jeu de paramètres n° 1, net 7 000,00 chacun ; `recapitulatif_paie_2026 (2).xlsx` — 4 paies clôturées juillet–octobre, cumuls 2026 : brut 29 466,04, net 28 000,00. **Le noyau gelé, à partir des saisies de la sauvegarde .db, refait le texte des 4 bulletins à l'identique** (hors date d'édition ; octobre = même saisie que septembre). Conclusion : la sauvegarde .db du 27/10 est **antérieure** à l'état réel (juillet–octobre clôturés le 06/11, PDF archivés). `data.json` d'ezzinecdi : introuvable selon le propriétaire.

- **Essai à blanc RÉEL (22/11/2026)** : sources du propriétaire (copies, originaux inchangés), deux exécutions identiques. Paie : 1 entreprise, 1 salarié, 1 version de paramètres, 3 paies importées à l'identique ; reclôture → 4 paies clôturées (net 7 000 chacune), 4 bulletins dont le **texte est identique aux PDF d'origine** (hors dates de clôture et d'édition). Trésorerie : 20 échéances importées (19 payées, 1 à venir), 0 correction, 0 rejet. Rapport complet (matricule masqué) hors dépôt : `/opt/hbnfactory/platforms/paie/migration/rapports/S5_MIGRATION_DRYRUN_REEL.md` (0600).

## Actions reportées
- Déclencheurs en production par un compte non root : `log_bin_trust_function_creators` ou binlog désactivé sur `paie-db` → S6.

## À confirmer
- Validation S5 : journal de la source ajouté à la suite sur une cible amorcée, règle du plan v1, échéances non importées à arbitrer, droits de structure de `paie_app` en S6 ; push de `sprint-S5`.
- Essai à blanc RÉEL : `scripts/dev-migration-dryrun.sh --sources /opt/hbnfactory/platforms/paie/migration/sources --matricule <M>` dès le dépôt des fichiers.
- Q4 / US-05 : data.json + backup_*.json (b), classeur Excel (c), confirmation du matricule 181159983 (d) ; éventuelle sauvegarde .db plus récente.
