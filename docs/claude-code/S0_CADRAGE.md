# Prompt Claude Code — Sprint S0 : cadrage et vérifications

Tu es l'exécutant technique du projet **HBN Paie**, la fusion de paie-bulletins et d'ezzinecdi. Tu as un accès live au VPS HBNFACTORY.

**Avant toute action**, lis `00_CADRE_COMMUN.md` en entier, puis `01_BACKLOG.md`. La règle **R0** prime sur tout. Les formules du bulletin de paie sont reprises telles quelles, jamais modifiées ni « rapprochées » d'un autre moteur, sinon les bulletins s'écartent des calculs comptables qui servent aux déclarations et aux paiements CNSS/AMO.

## Objectif
Vérifier les prérequis, créer le dépôt avec les sources gelées, mesurer la référence de tests et inventorier les données à reprendre. **Aucun code applicatif dans ce sprint.**

## Autorisations
L0 partout. L1 pour le dépôt `zaklearn/hbn-paie`. L2 uniquement pour créer `/opt/hbnfactory/platforms/paie/` (0750) et son sous-dossier `migration/sources/` (0700). **Interdit** : créer la base MySQL, lancer un conteneur sur le VPS, toucher à Traefik, Tangerine ou au portfolio.

## Stories
1. **US-01** : résolution DNS de `paie.hbnfactory.cloud` (local, 1.1.1.1, 8.8.8.8) comparée à l'IP du VPS ; RAM et disque libres ; conteneurs en cours (`docker ps`, sans les variables d'environnement) ; état de Traefik (lecture seule).
2. **US-02** : demande au propriétaire où tourne le serveur MySQL de WordPress (hôte, port) et de déposer un compte d'administration MySQL dans `/opt/hbnfactory/platforms/paie/secrets/mysql-admin.env` (0600). Ne l'affiche jamais. Puis, depuis le VPS : test de connexion, `SELECT VERSION()`, `SHOW GRANTS` (résumé sans secret), support de JSON, des colonnes générées et des déclencheurs (droit `TRIGGER`, `log_bin_trust_function_creators`), `max_allowed_packet` (PDF en BLOB). **Lecture seule : aucune création.** Si la connexion échoue, STOP : rapport et options (accès distant à autoriser chez l'hébergeur, tunnel SSH, MySQL sur le VPS).
3. **US-03** : crée le dépôt privé `zaklearn/hbn-paie`. Squelette : `backend/`, `frontend/`, `docs/claude-code/` (copie de ce pack de prompts), `docs/sprints/`, `scripts/`, `upstream/`. Dans `upstream/` : `paie-bulletins@df7ff126fdbb3d3c0a509480507361eec6b2b842` et `ezzinecdi@85354c9c1f1d79d71d215f75dc8131186bafc054` (copie des fichiers suivis, sans `.git`, sans données), plus `upstream/MANIFEST.sha256`. `.gitignore` : `.env*`, `data/`, `migration/`, `*.db`, `secrets/`. `.dockerignore` : exclut `upstream/`. Crée `PROJECT_STATE.md`, `BACKLOG.md` (copie de `01_BACKLOG.md`) et `CHANGELOG.md`.
4. **US-04** : dans un venv temporaire, lance `pytest -q` sur `upstream/paie-bulletins` et sur `upstream/ezzinecdi`, sans rien modifier. Consigne le nombre de tests passés et ignorés (avec la raison, par exemple `PAIE_REFERENCE_XLSX` absent). Ce sont les chiffres de référence de R0.3.
5. **US-05** : demande au propriétaire de déposer dans `migration/sources/` :
   - (a) la sauvegarde `.db` de paie-bulletins, téléchargée depuis « Sauvegardes et administration » ;
   - (b) le `data.json` d'ezzinecdi et ses `backup_*.json` (dossier Google Drive) ;
   - (c) le classeur `paie_exemple_EXEMPLE_SARL.xlsx` s'il est disponible ;
   - (d) le matricule du salarié suivi dans ezzinecdi.
   
   Inventaire : taille, SHA-256, et pour le `.db` le nombre de lignes par table et la version du schéma (lecture seule, via `sqlite3` sur une **copie**). Les fichiers ne sont jamais versionnés.

## Definition of Done
Les 5 stories sont faites, ou bloquées avec leur raison. Le dépôt est créé, `upstream/` et ses SHA sont consignés, les chiffres de référence sont relevés, l'inventaire des données est fait. `PROJECT_STATE.md` contient les faits vérifiés et les points à confirmer.

## Livrable
`docs/sprints/S0_RAPPORT.md` (1 page) : résultats US-01 à US-05, ligne « R0 : référence = n tests paie / 9 tests trésorerie », blocages, questions au propriétaire. Tag `sprint-S0`.

## Point d'arrêt
STOP après le rapport. Attends le « go S1 ».
