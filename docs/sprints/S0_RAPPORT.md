# S0 — Rapport de cadrage (21/11/2026)

**R0 : référence = 238 tests paie passés (+1 ignoré) / 9 tests trésorerie passés.** Aucun fichier de `upstream/` n'a été modifié : les tests ont tourné sur une copie, et `MANIFEST.sha256` reste inchangé.

## Résultats
| Story | Statut | Résultat |
|---|---|---|
| US-01 | Fait | DNS de `paie.hbnfactory.cloud` = **2.25.6.153** en local, via 1.1.1.1 et via 8.8.8.8, ce qui est l'IP publique du VPS. RAM : 3,8 Gio, dont 2,0 Gio disponibles ; 1 vCPU. Disque `/` : 23 Go libres sur 48 (53 % utilisés). 6 conteneurs « healthy » : traefik v3.7.19, socket-proxy, portfolio (wordpress et db mysql 8.4.13), tangerine et couchdb. Traefik : résolveur `le`, middleware `hbn-secure-headers@file`, réseau `hbn-proxy` présents. `http://paie…` → 301, `https://paie…` → 404 (aucun routeur, attendu) |
| US-02 | **Bloqué : réponse du propriétaire requise** | Fait vérifié : le MySQL de WordPress est le **conteneur `hbn-portfolio-db-1`** (mysql 8.4.13), uniquement sur le réseau `portfolio-internal`, sans port publié. Aucune connexion tentée, aucun compte utilisé : voir Q1 |
| US-03 | Fait en local, **création distante bloquée** | Dépôt local `/root/hbn-paie` (commit `S0/US-03`). `upstream/paie-bulletins@df7ff126…` : 78 fichiers. `upstream/ezzinecdi@85354c9c…` : 11 fichiers. Les deux dépôts sources sont publics et leur HEAD est égal aux commits gelés. `upstream/MANIFEST.sha256` (89 entrées) a pour SHA-256 `dabd124c54d178046fd10b562244119f69c9dab226822c64dc621ea987bf148d`. Exclus : `data.json` et `.streamlit/secrets.toml` (ezzinecdi), `.env.example` et `data/.gitkeep` (paie-bulletins). `zaklearn/hbn-paie` n'est pas créé sur GitHub : il n'y a ni `gh` ni identifiants sur le VPS (Q2) |
| US-04 | Fait (avec réserve) | `pytest -q` exécuté tel quel. **paie-bulletins** : 238 passés, 1 ignoré (`test_reference_excel.py:103`, `PAIE_REFERENCE_XLSX` non défini). **ezzinecdi** : 9 passés. Réserve : mesure faite en **Python 3.14.4**, la seule version présente, alors que la cible est 3.12. Versions dans `S0_reference_env.txt` : reportlab 5.1.0, pandas 3.1.1, openpyxl 3.1.5, streamlit 1.67.0 |
| US-05 | **Bloqué : dépôt des fichiers par le propriétaire** | `/opt/hbnfactory/platforms/paie/migration/sources/` créé (0700). En attente : (a) le `.db`, (b) `data.json` et `backup_*.json`, (c) le classeur Excel, (d) le matricule |

**Référence par fichier (paie-bulletins, 239 tests collectés)** :
- engine 40, reference_excel 39 (dont 1 ignoré), workflow 35, access_control 25, app_smoke 24 ;
- reset_production 15, supprimer_demo 13, services_misc 12, pdf 9, backup_integrity 8 ;
- ecarts_pdf 7, non_regression 7, mobile_download 5 ;
- golden : 6 scénarios.

## Actions exécutées
- **L1 :** dépôt local `/root/hbn-paie`, venv temporaire dans le scratchpad, supprimable.
- **L2 :** `/opt/hbnfactory/platforms/paie/` (0750), `migration/` (0750), `migration/sources/` (0700).
- **Pip :** pip a été initialisé dans le venv à partir de la wheel PyPI officielle, après vérification de son SHA-256. Raison : `ensurepip` est absent (paquet système `python3-venv`). Rien n'a été installé au niveau du système.
- **Non fait :** aucune base, aucun conteneur, aucune modification de Traefik, de Tangerine ou du portfolio.

## Alerte sécurité (hors périmètre, à traiter par le propriétaire)
Le dépôt **public** `zaklearn/ezzinecdi` versionne `.streamlit/secrets.toml` au commit `85354c9`.
- **Contenu :** `superadmin_password`, `user_password`, `app_key`, `app_secret`, `refresh_token` et `folder`. Les valeurs ont la longueur de vraies valeurs ; je ne les ai pas affichées.
- **Données personnelles :** `data.json` (12 échéances, avec montants et dates de paiement) y est aussi public.
- **Historique :** un commit `2c51091` avait retiré le fichier du suivi, mais il est revenu avec `v5`.
- **Recommandation :** révoquer le refresh token et régénérer le secret de l'app Dropbox, changer les deux mots de passe, passer le dépôt en privé, puis purger l'historique.

## Questions au propriétaire
1. **Q1 — MySQL.**
   - **Option A (conception D2) :** une base `paie` dans le conteneur `hbn-portfolio-db-1`. Elle impose de brancher le conteneur paie sur `portfolio-internal` et de faire porter le cycle de vie du portfolio par la paie (arrêts, sauvegardes, montées de version), ce qui frotte avec R6.
   - **Option B :** un MySQL 8.4 dédié dans `/opt/hbnfactory/platforms/paie/` (environ 300 à 400 Mo ; 2,0 Gio sont disponibles).
   - **Dans les deux cas :** déposer le compte d'administration dans `/opt/hbnfactory/platforms/paie/secrets/mysql-admin.env` (0600). Ce dossier `secrets/` n'est pas dans la liste L2 de S0 : je le crée en 0700 sur votre accord, ou vous le créez.
2. **Q2 — GitHub.** Créez le dépôt privé `zaklearn/hbn-paie` et donnez-moi un accès en écriture (clé de déploiement SSH ou jeton à droits limités, déposé en 0600), ou autorisez l'installation de `gh`. Le push du dépôt local et du tag `sprint-S0` se fera ensuite.
3. **Q3 — Python 3.12 pour S1.** S1 autorise sur le VPS un projet compose de dev `hbn-paie-dev` (256 Mo, sans port, arrêté après les tests). Je propose d'y exécuter les tests dans `python:3.12-slim`, puis de remesurer la référence en 3.12 pour la comparer à celle de 3.14. D'accord ?
4. **Q4 — Données (US-05).** Déposez les fichiers (a) à (c) dans `migration/sources/` et donnez le matricule (d). Je ferai ensuite l'inventaire : taille, SHA-256, et lignes par table sur une copie.
5. **Q5 — Documents.** `PAIE_DIAG_1/2/3_*.md` ne sont pas fournis. Ils sont nécessaires à la checklist R2 de S4 et S6.
