# Diagnostic 2/3 — paie-bulletins v1.4.0

Date : 21/11/2026 · Source : `github.com/zaklearn/paie-bulletins` (main) · En test : `paie-bulletins.streamlit.app`
Rôle dans la fusion : **source fonctionnelle de référence du module Paie** (règles, calcul, PDF, procédure) à reproduire **à l'identique**.

## 1. Organisation (couches strictes `views → ui → services → calculations/repositories/pdf/validation → models`)

```
app.py                 Streamlit : login + st.navigation (9 pages)
views/                 dashboard, entreprise, salaries, saisie, calcul, archives, exports, parametres, administration
src/models/            parameters.py (PayrollParameters, IRBracket, méthode des totaux), payroll.py, entities.py
src/calculations/      engine.py (1 fonction = 1 ligne de la feuille Calcul), money.py (excel_round), defaults.py, cumuls.py
src/validation/        validators.py (erreurs bloquantes / avertissements)
src/repositories/      db.py (SQLite, WAL, BEGIN IMMEDIATE, migrations, déclencheurs), repos.py (SQL paramétré)
src/services/          master_data, payroll (procédure), reporting, backup, auth (PBKDF2), demo
src/pdf/bulletin.py    ReportLab A4 (mise en forme seule, aucun calcul)
tests/                 ~139 fonctions / 162 cas pytest, golden/results.json, comparaison au classeur Excel
scripts/ docs/         hash_password, backup_db, reset_production, supprimer_demo, update_golden ; 5 docs
```

## 2. Stack

Python ≥ 3.10, Streamlit ≥ 1.65, ReportLab, pandas, openpyxl, SQLite (stdlib). Montants en `Decimal`, stockés en texte décimal exact.

## 3. Fonctionnalités (spécification à conserver)

| Écran | Description exacte |
|---|---|
| Tableau de bord | Entreprise active, nb salariés, mois ouverts/clôturés de l'année, dernières paies, alertes |
| Entreprise | Fiche unique (id = 1) : raison sociale, adresse, ville, ICE, CNSS employeur, RC, IF, téléphone, email, logo |
| Salariés | Matricule unique ; nom, prénom, naissance, CIN et CNSS uniques si renseignés, situation familiale, nb personnes à charge, embauche/sortie, fonction, département, CIMR, catégorie, banque, compte, adresse, mode de paiement ; recherche ; activation/désactivation (jamais supprimés) ; CIN/CNSS/compte masqués |
| Paramètres | Versions datées (`valid_from` = AAAA-MM), motif obligatoire, validation, historique, **immuables**, jamais rétroactives sur une paie clôturée. Taux CNSS/AMO sal. et pat., plafond CNSS, participation AMO, formation pro, AF, frais pro (seuil, 2 taux, plafond), déduction/personne + max, parts imposables par rubrique, barème IR annuel, méthode des totaux (somme des lignes / taux cumulé) |
| Saisie mensuelle | Tout mois/année ; préremplissage depuis le dernier mois clôturé (signalé) ; base, jours, HS, panier, transport, représentation, autre prime, congés (reliquat, acquis, pris) ; contrôles ; aperçu instantané |
| Calcul et validation | Brouillon → Calculée → Clôturée ; contrôles de clôture (recalcul identique, mois antérieurs non ouverts…) ; aperçu PDF provisoire ; clôture confirmée ; **rectification** avec motif → ancienne version « Remplacée », PDF `_v2` |
| Bulletins et archives | PDF archivé en base + SHA-256, `bulletin_AAAA-MM_0001.pdf`, non modifiable/non supprimable ; consultation, téléchargement (y compris mobile) |
| Récapitulatifs et exports | Livre de paie, récap mensuel/annuel, CSV/Excel **sans CIN, CNSS ni banque** |
| Sauvegardes et administration | Sauvegarde, liste, restauration vérifiée précédée d'une sauvegarde auto, journal des opérations (ajout seul) |

Règles garanties par la base : une seule paie de travail et une seule clôturée en vigueur par salarié × mois ; paies clôturées, documents, versions de paramètres et journal non modifiables. Chaque paie fige en JSON la saisie, le résultat, les cumuls, et des copies des paramètres, de la fiche salarié et de la fiche entreprise. Cumuls annuels calculés sur les seules paies clôturées, figés à l'émission.

Calcul : brut = Σ 6 rubriques ; assiette = base + HS + autre prime ; CNSS sur assiette plafonnée ; RBI = base + Σ rubrique × part imposable ; frais pro selon RBI×12 ≤ seuil ; IR annuel = NI×12×taux − déduction, mensualisé /12 ; net arrondi au dirham (ligne « arrondi ») ; coût employeur ; solde congés. Arrondi = `ROUND` d'Excel (demi vers l'extérieur).

## 4. Déploiement constaté

Streamlit Community Cloud, SQLite dans `data/` (système de fichiers **éphémère** : données de test seulement), mot de passe unique en hachage PBKDF2 dans les secrets, `PAIE_SEED_DEMO`.

## 5. Points d'attention pour la fusion

- Le moteur, les modèles, les validateurs et `bulletin.py` sont indépendants de Streamlit : ils se **reprennent tels quels**, puis on recâble les dépôts sur MySQL.
- SQLite vers MySQL : index uniques partiels (`WHERE`) absents en MySQL → colonnes générées ; déclencheurs à réécrire avec `SIGNAL SQLSTATE '45000'` (droit `TRIGGER` requis) ; `BEGIN IMMEDIATE` → `SELECT … FOR UPDATE` ; sauvegarde via l'API SQLite → export/import des tables du module.
- Les tests golden et de comparaison au classeur servent de **critère d'acceptation** : mêmes résultats au centime, PDF identiques.
- Mono-utilisateur aujourd'hui (opérateur déclaratif) : à passer en comptes nominatifs avec rôles.
