# S5 — Rapport : sauvegarde, restauration et outils de migration (22/11/2026)

**R0 : intégrité du noyau OK (10 fichiers), golden OK (6 cas), Excel non fourni.**
- **R0.3 sur l'essai à blanc :** 5 paies clôturées ou remplacées recalculées en lecture seule, **0 écart** chaîne par chaîne. Les écarts seraient signalés, jamais corrigés.
- La migration **recopie** les données, sans recalcul.

**Suite complète : 298 réussis, 1 ignoré**, le classeur Excel absent. Les 2 tests de sauvegarde d'origine sont désormais actifs.

## Stories
| Story | Statut | Contenu / preuve |
|---|---|---|
| US-50 | Fait | Sauvegarde dans un `.zip` autonome. Le manifeste indique la révision, la version du schéma, les protections (déclencheurs, index d'unicité) et, pour chaque table, les colonnes, le décompte et le SHA-256. Les données sont exactes, PDF compris ; les sessions sont exclues. Fichiers en 0600 dans un dossier 0700, rétention `PAIE_BACKUP_RETENTION` (0 = toutes). **Restauration :** validation complète avant toute action, sauvegarde de sécurité, puis reconstruction (voir ci-dessous). Disponible en CLI (`scripts/paie-backup`, `scripts/paie-restore`, confirmation « RESTAURER »), dans l'API (superadmin) et dans l'écran Configuration › Sauvegardes (dialogue « Remplacer toute la base »). **Test :** sauvegarde → restauration → décomptes et empreintes identiques |
| US-51 | Fait | `scripts/migrate_paie_bulletins.py --source <copie.db> [--target url] [--dry-run]`. Source lue en lecture seule (voir contrôles ci-dessous). Ordre : company → employees → parameter_sets → payslips (toutes versions) → documents → audit_log, **ids d'origine conservés**. Une cible contenant des données métier est **refusée** |
| US-52 | Fait | `scripts/migrate_ezzinecdi.py --source <copie data.json> --matricule M [--dry-run] [--backups …]` : rattachement au matricule, plan v1 déduit, recopie des 9 champs (voir détails ci-dessous). Les `backup_*.json` sont seulement comparés |
| US-53 | Fait | `scripts/dev-migration-dryrun.sh [--sources dossier] [--matricule M]` travaille sur des copies (SHA-256 des originaux contrôlé avant et après). Il exécute la simulation, puis l'import dans **deux bases de dev neuves** : **rapports identiques** (rejouable). Rapport : `S5_MIGRATION_DRYRUN.md` |

**Détails US-50, restauration.**
- Validation complète avant toute action : empreintes, décomptes, protections attendues, unicités, références. **Un refus laisse la base intacte**, sans sauvegarde de sécurité créée.
- Reconstruction : le schéma est **recréé par les migrations**, donc les protections viennent toujours du code. Les données sont ensuite réinsérées en une transaction.
- **En cas d'échec en cours de route,** la sauvegarde de sécurité est rétablie (testé).

**Détails US-51, migration paie-bulletins.**
- **Contrôles de la source :** `integrity_check`, version 1, protections d'origine exactes, références, empreinte inchangée.
- **Déclencheurs actifs pendant tout l'import :** il n'y a que des INSERT, et les déclencheurs ne portent que sur UPDATE et DELETE. Les protections sont vérifiées ensuite.
- **Tests :** cible = source champ par champ, octets des PDF compris ; services portés lisant les données importées ; simulation sans écriture et rejouable ; source altérée refusée.

**Détails US-52, migration ezzinecdi.**
- **Plan v1 :** déduit du premier mois des données.
- **Réconciliation d'origine :** exécutée **en simulation** ; corrections listées, **jamais appliquées**.
- **Non importés et listés :** enregistrement hors schéma, doublon écarté (le payé prime), incohérence statut / date que la base refuse.
- **Import :** recopie des 9 champs, `n` d'origine conservé dans `source_ref`, numérotation d'origine.

**Détails US-53, contenu du rapport.** Décomptes, totaux par mois de la paie (brut, net, cotisations, statuts) et de la trésorerie (payées / non payées, montants), empreintes PDF, R0.3, corrections proposées, anomalies et points soumis au propriétaire.

**Tests reportés depuis S2 :** les 2 tests de sauvegarde de `test_services_misc` passent désormais **tels quels** (même interface `create_backup`, `list_backups`, `restore_backup`). `test_backup_integrity` est **porté en équivalent MySQL** : ses intentions d'origine sont reprises, sauf « déclencheur neutralisé », sans équivalent sur une sauvegarde `.zip` (voir le tableau). S'y ajoutent les tests propres au nouveau format : fichier altéré, doublon, échec en cours, exactitude, rétention et colonnes.

| Test d'origine | Équivalent MySQL |
|---|---|
| Sauvegarde altérée refusée, base intacte (5 altérations) | 4 altérations des protections du manifeste. La 5e, « déclencheur neutralisé », est sans objet, car le schéma n'est jamais repris du fichier |
| Références incohérentes refusées | Document vers une paie inexistante → « références » |
| Restauration valide : protections et archives | Identique, avec `DELETE` d'un bulletin refusé après restauration |
| Base de l'application conforme aux protections | `check_database_protections` |

## Écarts, corrections et décisions (à valider)
1. **Correctif US-50 :** MySQL marque `DEFAULT_GENERATED` les colonnes `TEXT DEFAULT ('')`, et mon premier filtre les excluait.
   - **Conséquence :** adresse, ville, prénom, fonction… n'auraient pas été sauvegardés.
   - **Corrigé avant toute utilisation réelle :** seules les colonnes réellement générées sont désormais exclues. Un test vérifie les colonnes et leurs valeurs après restauration.
   - **Même correctif pour la migration.** Le `.gitignore` excluait aussi par erreur `backend/app/migration` ; c'est corrigé.
2. **Cible « amorcée » acceptée** pour l'ordre de S6 (B base, C démarrage, D import).
   - **Ce qui est toléré :** la version de paramètres initiale non référencée, les comptes et le journal de démarrage.
   - **Comment :** la version initiale est remplacée par celle de la source, qui est identique, et le journal de la source est ajouté **à la suite**, avec des identifiants renumérotés (ordre et contenu conservés). Sur une cible vide, les ids du journal sont conservés.
3. **Échéances non importées** (hors schéma, doublon écarté, incohérence statut / date) : listées, jamais corrigées ni importées d'office. **À arbitrer** par vous sur les données réelles.
4. **Plan v1 :** montants des 4 types sur le **premier mois** des données, avec effet à ce mois. Un premier mois incomplet ou ambigu est refusé, et le plan est alors à saisir par vous.
5. **Restauration :**
   - elle ferme toutes les sessions (table recréée) ;
   - elle n'est pas atomique au niveau du schéma (DDL MySQL), d'où la sauvegarde de sécurité rétablie automatiquement en cas d'échec ;
   - **en S6**, `paie_app` aura besoin des droits de structure sur `paie.*` (CREATE, DROP, ALTER, INDEX, TRIGGER, REFERENCES).
6. **Sources réelles absentes :** l'essai porte sur des **sources de substitution** :
   - une base `.db` produite par l'application d'origine elle-même ;
   - un `data.json` synthétique.

   Le `data.json` public du dépôt ezzinecdi **n'a pas été utilisé** (R7). L'essai réel se rejouera avec la même commande dès le dépôt des fichiers :

   ```
   scripts/dev-migration-dryrun.sh --sources /opt/hbnfactory/platforms/paie/migration/sources --matricule <M>
   ```

## Questions au propriétaire
1. Déposez la sauvegarde `.db` de paie-bulletins, `data.json` avec ses `backup_*.json`, et donnez le matricule. US-05 reste bloquée ; c'est le préalable à la validation du dry-run réel, avant S6.
2. Validez-vous les points 2 à 5, en particulier le journal ajouté à la suite (2) et la règle du plan v1 (4) ?
3. Faut-il pousser `main` et le tag `sprint-S5` ?
