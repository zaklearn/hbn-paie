# S2 — Rapport : module Paie sur MySQL (21/11/2026)

**R0 : intégrité du noyau OK (10 fichiers), golden OK (6 cas), Excel non fourni.** `app/paie/core/` est inchangé. Le noyau n'est appelé que depuis `payroll._compute`, comme dans l'original. Le **bulletin clôturé de la démo** (juillet à septembre 2026) a un texte PDF **identique à celui de l'original** exécuté tel quel ; résultat, cumuls et copies figées sont identiques chaîne par chaîne (`test_pdf_equivalence.py`).

**Suite complète : 222 réussis, 3 ignorés** (référence Excel absente, et 2 tests de sauvegarde reportés en S5).

## Stories
| Story | Statut | Contenu / preuve |
|---|---|---|
| US-20 | Fait | Alembic `0002`, transposition de `db.py` table par table. Le schéma paie est en version 1 (`schema_version`), comme l'original. Voir ci-dessous pour les types de colonnes et la collation |
| US-21 | Fait | `UNIQUE` et `CHECK` identiques. CIN et CNSS : `NULLIF(…,'')` + `UNIQUE`. `ux_payslips_open` et `ux_payslips_closed` : colonnes générées. **6 déclencheurs** `SIGNAL SQLSTATE '45000'`, avec les mêmes messages et la même condition (`IS` → `<=>`). **24 tests de violation**, un par contrainte et par déclencheur |
| US-22 | Fait | `Database` garde l'interface d'origine (`connect`, `transaction`, `read`, `migrate`) ; adaptateur : marqueurs `?`, lignes par nom, `IntegrityError`, isolation READ COMMITTED. `BEGIN IMMEDIATE` est remplacé par `SELECT … FOR UPDATE` sur la **ligne salarié** (voir écart 1). Test : 4 enregistrements simultanés du même mois donnent une seule version de travail, sans erreur |
| US-23 | Fait | `master_data`, `payroll`, `reporting`, `demo` et `errors` sont portés. **Écarts (tous réversibles, prouvés octet pour octet par `test_port_fidelity.py`) :** voir le tableau plus bas. `CLOSURE_WARNING_PROVIDERS` est le point d'extension unique ; il ne retient que les avertissements, et reste vide en S2 |
| US-24 | Fait | Tables `users` et `sessions` (Alembic `0003`). `auth.py` est repris tel quel : PBKDF2-SHA256, 600 000 itérations. Les sessions décrites plus bas tiennent dans un cookie httpOnly. CLI du premier superadmin, avec mot de passe saisi au clavier (`python -m app.socle.cli create-superadmin`). L'acteur du journal est le compte connecté. Le rôle `user` est **refusé côté API** (403, 12 écritures testées) |
| US-25 | Fait | API `/api/paie/*` et `/api/socle/*`. Montants en **chaînes décimales** ; une saisie en notation flottante est refusée (422). Les noms d'export d'origine sont conservés : `livre_de_paie_<période>.csv`, `recapitulatif_paie_<période>.xlsx` (3 feuilles) et `bulletin_AAAA-MM_NNNN[_vN].pdf`. 27 tests API |

**Détails US-20.**
- **Types de colonnes :**
  - JSON : `LONGTEXT` + `CHECK (JSON_VALID(…))`, avec la sérialisation `json.dumps` d'origine. Le texte est conservé exactement, sans aucune colonne `DECIMAL`, `FLOAT` ou `DOUBLE` (vérifié par un test).
  - PDF : `LONGBLOB` + `sha256`.
- **Dates en texte ISO (`VARCHAR`), et non en `DATETIME`.** Raisons :
  - le texte est identique à l'original, ce qui permet l'import octet pour octet en S5 ;
  - la comparaison `valid_from <= 'AAAA-MM'` reste inchangée ;
  - l'horodatage `now_iso()` est repris tel quel.
- **Collation `utf8mb4_bin` :** égalité, unicité et tri sont ceux de SQLite. Par exemple, `ab1` et `AB1` sont deux matricules distincts (testé).

**Détails US-24.** Chaque session est un jeton aléatoire, dont seul le SHA-256 est stocké. Le cookie `Secure` est en `SameSite=Strict`. Les sessions sont révoquées à la déconnexion, au changement de mot de passe et à la désactivation du compte. Un identifiant inconnu et un mauvais mot de passe donnent le même message. Le dernier superadmin ne peut être ni désactivé ni rétrogradé.

**Détails US-25.** Pour le rôle `user`, CIN, CNSS et compte sont masqués (`••••0000`), dans la fiche comme dans les copies figées des paies.

## Tableau des écarts (fonction d'origine → fonction portée → écart)
Les autres fonctions sont reprises **sans aucun changement** hors imports. Cela couvre les 37 fonctions et classes de `repos.py`, 12 de `master_data`, 26 de `payroll`, 8 de `reporting`, 1 de `demo` et 2 d'`errors`.

| Fonction d'origine | Fonction portée | Écart (raison) |
|---|---|---|
| `repos.save_company` | idem | `ON CONFLICT … excluded` → `AS new ON DUPLICATE KEY UPDATE` (dialecte, même effet) |
| `repos.find_duplicates` | idem | `id IS NOT ?` → `NOT (id <=> ?)` (dialecte) |
| `repos.list_employees` | idem | `LIKE` → `LOWER(…) LIKE LOWER(?)`, pour rester insensible à la casse comme SQLite malgré la collation binaire |
| — | `repos.lock_employee`, `repos.lock_payslip_employee` | Nouvelles fonctions `FOR UPDATE` (US-22) |
| `master_data.create_parameter_version` | idem | `printf('%04d-%02d')` → `CONCAT(LPAD…)`, même chaîne AAAA-MM |
| `payroll.save_draft`, `calculate`, `close`, `open_rectification`, `delete_draft` | idem | Une ligne ajoutée en tête de transaction : verrou salarié |
| `payroll._closure_checks` | idem | Appel de `CLOSURE_WARNING_PROVIDERS` (vide en S2, donc comportement d'origine) |
| `repos.py` (en-tête) | idem | Annotations `sqlite3.Connection`/`Row` → `Connection`/`Row` de l'adaptateur |

## Tests portés (aucune valeur attendue modifiée)
- **Résultats :** `test_workflow` 35/35, `test_pdf` 9/9 (reporté de S1), `test_services_misc` 10/12, et les tests S1 du noyau 92 + 1 ignoré. **Les identifiants sont identiques à la référence 3.12.**
- **Écarts du portage (listés dans `scripts/port_tests.py`) :**
  - `Database(chemin)` pointe vers une base MySQL de test neuve, et le même chemin redonne la même base (test « après redémarrage ») ;
  - `sqlite3.IntegrityError` devient `db.IntegrityError` ;
  - `auth` est importé depuis le socle ;
  - `demo_reference.py` est **retiré**, comme prévu en S1.
- **Ignorés avec motif :** les 2 tests de sauvegarde de `test_services_misc` (`backup.py` est propre à SQLite), reportés en S5. `test_backup_integrity` (8 tests) est reporté en S5 pour la même raison.

## Écarts et points à valider
1. **Verrou à la granularité du salarié, et non « salarié × mois » :** aucune ligne n'existe pour un mois pas encore saisi. Ce verrou est aussi plus sûr, car les cumuls d'un mois dépendent des autres mois du même salarié.
2. **`PAIE_SEED_DEMO` vaut 0 par défaut**, contre 1 dans l'original. Le comportement du réglage est inchangé ; seule sa valeur par défaut diffère. Raison : en S6, l'import réel exige une base vide, et une démo créée au démarrage la bloquerait. **À valider.**
3. **Tests d'origine non portés, car propres à Streamlit ou aux scripts Windows :**
   - `test_access_control` (25 tests) : mot de passe partagé et pages Streamlit. Ses principes sont couverts par les tests API : connexion obligatoire, refus sans session, déconnexion effective ;
   - `test_app_smoke` (24) et `test_mobile_download` (5) : l'interface arrive en S4, et le téléchargement passe par l'API ;
   - `test_reset_production` (15) et `test_supprimer_demo` (13) : scripts `.bat` de remise à zéro et de suppression de la démo. Ils sont inutiles si la démo n'est jamais créée en production (point 2).
   - **À confirmer pour la checklist R2.**
4. **Bases de test :** chaque test crée sa base sur le MySQL de **dev** éphémère (tmpfs), puis la supprime (`DROP DATABASE` limité au préfixe `t_`). Ce n'est jamais une base de production.
5. **Production (S6) :** créer les 6 déclencheurs avec un compte non root exigera `log_bin_trust_function_creators=1`, ou le binlog désactivé, sur `paie-db`. Le choix sera fait en S6.

## Questions au propriétaire
1. Validez-vous `PAIE_SEED_DEMO=0` par défaut et l'abandon des scripts de remise à zéro et de suppression de la démo (points 2 et 3) ?
2. Faut-il pousser `main` et le tag `sprint-S2` ?
