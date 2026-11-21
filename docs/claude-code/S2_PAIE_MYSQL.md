# Prompt Claude Code — Sprint S2 : module Paie sur MySQL

**Avant toute action**, lis `docs/claude-code/00_CADRE_COMMUN.md` (R0 en premier), `PROJECT_STATE.md`, `BACKLOG.md` et `docs/sprints/S1_RAPPORT.md`.

> **R0** : tu changes le stockage, pas le calcul. `app/paie/core/` reste intact (test d'intégrité vert à chaque commit). Les services appellent le noyau exactement comme dans `upstream/paie-bulletins/src/services/`. Aucune formule, aucun arrondi, aucun paramètre n'est modifié ni aligné sur SmartCompta. Sinon, écart avec la comptabilité qui déclare et paie CNSS/AMO.

## Objectif
Reproduire sur MySQL la persistance, la procédure mensuelle, l'authentification et l'API du module Paie. Les comportements et les garde-fous restent ceux de paie-bulletins 1.4.0.

## Autorisations
L1 (dépôt + MySQL de test). Aucune action sur le VPS.

## Stories
1. **US-20, schéma** (révision Alembic) : transpose `upstream/paie-bulletins/src/repositories/db.py` table par table.
   - Tables : `company`, `employees`, `parameter_sets`, `payslips`, `documents`, `audit_log`, plus `users` (nouvelle).
   - InnoDB, utf8mb4.
   - Les colonnes JSON de l'original (`inputs`, `result`, `cumuls`, `parameters`, `employee_snapshot`, `company_snapshot`, `parameter_sets.data`) deviennent **`LONGTEXT` + `CHECK (JSON_VALID(...))`**. La sérialisation est celle des `to_dict` / `json.dumps` de l'original, pour garder le texte exact (R0.2 : pas de colonne arrondissante, pas de type JSON qui réordonne).
   - PDF : `LONGBLOB` + `sha256`.
   - Dates : mêmes formats texte que l'original, ou `DATETIME` si la conversion est sans perte. Justifie le choix dans le rapport.
2. **US-21, contraintes** :
   - mêmes `UNIQUE` et `CHECK` que l'original ;
   - CIN et CNSS uniques si non vides : colonne générée `NULLIF(cin,'')` + `UNIQUE` ;
   - `ux_payslips_open` / `ux_payslips_closed` : colonnes générées (`IF(status IN ('brouillon','calculee'),1,NULL)`, `IF(status='cloturee',1,NULL)`) + `UNIQUE (employee_id, year, month, <col>)` ;
   - les 6 déclencheurs transposés en `SIGNAL SQLSTATE '45000'`, avec les **mêmes messages** et la même condition (seule transition admise sur une paie figée : `cloturee → remplacee`, sans autre changement) ;
   - si le droit `TRIGGER` manque en production (cf. S0), les mêmes contrôles existent dans les dépôts (repositories). Ils sont actifs dans tous les cas.
3. **US-22, dépôts** : `app/paie/repositories/`, équivalent fonctionnel de `repos.py`. Requêtes paramétrées ; `BEGIN IMMEDIATE` remplacé par une transaction + `SELECT … FOR UPDATE` sur la ligne salarié × mois.
4. **US-23, services** : porte `master_data.py`, `payroll.py` et `reporting.py` avec une logique **identique**. Diffe chaque fonction avec l'original et explique tout écart non lié à la base dans le rapport. Doivent être identiques : préremplissage, contrôles de saisie et de clôture, recalcul de contrôle à la clôture, PDF généré et stocké dans la même transaction, rectification avec motif, cumuls sur les seules paies clôturées, nommage `bulletin_AAAA-MM_NNNN[_vN].pdf`, exports sans CIN, CNSS ni banque. `demo.py` et `PAIE_SEED_DEMO` sont repris tels quels. Ajoute **un seul point d'extension** dans `closure_checks` : une liste d'avertissements fournie par un callback (vide en S2, remplie en S3). Aucun autre changement.
5. **US-24, accès** :
   - table `users` (identifiant, nom, rôle `superadmin` ou `user`, hachage via `upstream/.../services/auth.py` repris tel quel en PBKDF2-SHA256 600 000) ;
   - sessions par cookie httpOnly signé, ou jeton court ;
   - premier superadmin créé par une commande CLI (mot de passe saisi, jamais par défaut) ;
   - l'acteur du journal est l'utilisateur connecté ;
   - le rôle `user` est en lecture et export seulement ; refus côté API, pas seulement dans l'interface.
6. **US-25, API** `/api/paie/*` : entreprise, salariés, paramètres (versions), saisie et brouillon, `preview` (aperçu calculé par le noyau), calcul, contrôles, clôture (`confirm_warnings`), rectification, suppression de brouillon, documents (téléchargement), journal de paie et récapitulatifs, tableau de bord. Schémas Pydantic : montants **en chaînes décimales** dans le JSON de l'API.

## Tests
Porte `test_workflow.py`, `test_non_regression.py` (partie base), `test_services_misc.py`, `test_access_control.py` et `test_backup_integrity.py` (si dépendant de SQLite, report en S5 avec mention), sur la base de test MySQL. **Aucune valeur attendue modifiée.** Ajoute des tests de violation pour chaque contrainte et chaque déclencheur, et des tests API par rôle.

## Definition of Done
`make test` vert, intégrité du noyau verte, golden vert. Pour la paie de démonstration de septembre 2026, le texte extrait du PDF clôturé est identique à celui produit par l'original (`upstream/`) avec les mêmes données.

## Livrable
`docs/sprints/S2_RAPPORT.md` (ligne R0, tableau « fonction d'origine → fonction portée → écart »). Mise à jour de `PROJECT_STATE.md`, `BACKLOG.md` et `CHANGELOG.md`. Tag `sprint-S2`.

## Point d'arrêt
STOP. Attends le « go S3 ».
