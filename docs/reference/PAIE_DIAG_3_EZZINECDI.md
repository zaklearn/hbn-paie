# Diagnostic 3/3 — ezzinecdi v5 « Suivi virements salaires & CNSS »

Date : 21/11/2026 · Source : `github.com/zaklearn/ezzinecdi` (main) · En test : `ezzinecdi.streamlit.app`
Rôle dans la fusion : **source fonctionnelle de référence du module Virements**, à reproduire à l'identique.

## 1. Organisation (7 modules à plat, ~1 000 lignes)

| Fichier | Rôle |
|---|---|
| `app.py` | UI : porte d'authentification, barre latérale, 4 panneaux, rendu selon le rôle |
| `auth.py` | 2 mots de passe dans `st.secrets` → rôles `superadmin` (lecture/écriture) et `user` (lecture + export) |
| `dates.py` | `aujourdhui()` en fuseau Africa/Casablanca |
| `db_gen.py` | Barème, génération d'un mois, anti-doublon, tri et renumérotation (sans Streamlit) |
| `integrity.py` | Validation de schéma, réconciliation, régularité au jour, statut payé/non payé |
| `rapport.py` | Export Excel 8 colonnes, export ICS des rappels |
| `storage.py` | `data.json` sur Google Drive (service account, `drive.file`) avec repli local, verrou optimiste par révision, sauvegardes horodatées avec rotation, erreur → lecture seule |
| `tests/test_logic.py` | 9 tests |

## 2. Stack

Streamlit, openpyxl, google-api-python-client, google-auth, tzdata (`dropbox` listé mais inutilisé). Base = liste JSON.

## 3. Modèle de données

Un enregistrement par échéance (9 champs) : `n`, `date_echeance`, `mois` (« Juillet 2026 »), `type`, `montant` (entier DH), `statut`, `rappel_j1`, `observations`, `date_paiement` (technique, non exporté). Clé métier unique : (mois, type).

**Barème mensuel fixe (8 500 DH)** : le 10, salaire 1er versement 2 500 et CNSS 1 500 ; le 20, salaire 2e versement 2 500 ; le 30 (ou dernier jour du mois), salaire 3e versement 2 000. Rappel = échéance − 1 jour.

Statuts : `Non payé`, `Payé – à temps`, `Payé – retard`, `Payé – avance`. Régularité : retard si payé après l'échéance ; avance si l'échéance tombe un mois postérieur au paiement ; sinon à temps. Badge « en retard » (échu non payé) calculé à l'affichage, jamais stocké.

## 4. Fonctionnalités (spécification à conserver)

| Élément | Description exacte |
|---|---|
| Porte d'auth | Mot de passe → rôle ; sans bloc `[auth]` la connexion est impossible ; bouton déconnexion |
| Barre latérale | Rôle affiché ; alerte lecture seule ; mois courant (figé) ; navigation 4 panneaux ; bloc superadmin « Régularisation / nouveau mois » (année −2…+3, mois) : déclarer un mois absent, ou payer les échéances non payées d'un mois déjà déclaré ; Diagnostic (mode de persistance, révision, totaux, réparations au chargement, recharger) |
| Base vide | Accueil ; superadmin : déclarer le premier mois ; user : message d'attente |
| 🔜 À venir | Échues non payées (« En retard (n) ») puis 6 prochaines échéances non payées, en cartes avec bouton Payer |
| 📅 Mois courant | Déclarer le mois s'il manque ; métriques Payé / Restant / Avancement % ; cartes ; Dévalider (superadmin) |
| 🔔 Rappels | Tableau des non payées (rappel J-1, échéance, mois, type, montant, état) ; export `.ics` |
| 📊 Récap & export | KPI total payé, restant dû, échéances payées n/N, avancement + barre ; répartition à temps/retard/avance ; 3 téléchargements : `recap_paiements.xlsx` (payées), `base_complete.xlsx`, `rappels_salaires_cnss.ics` ; tableau complet |
| Payer / Dévalider | Dialogue de confirmation ; payer = saisie de `date_paiement` → statut recalculé ; dévalider → Non payé, date effacée |
| Import / Remplacer | Dialogue de confirmation avant remplacement ; validation montant = barème(type), mois = mois(date) ; la fusion conserve le payé |
| Réconciliation au chargement | Rejet hors schéma, dédoublonnage (le payé prime), correction rappel, montant, mois et cohérence statut ⇔ date_paiement, renumérotation, compte rendu |
| Excel | 8 colonnes, en-tête stylé, format `#,##0 "DH"`, ligne TOTAL, filtres, volets figés |

## 5. Déploiement constaté

Streamlit Community Cloud, secrets `[auth]` et `[gdrive]`, persistance Google Drive.

## 6. Points d'attention pour la fusion

- `db_gen`, `integrity`, `rapport` et `dates` sont purs : ils se portent directement en services FastAPI.
- Google Drive est remplacé par MySQL : le verrou optimiste devient une colonne `version`, les sauvegardes JSON tournantes deviennent la sauvegarde du module et le journal.
- Fait relevé : les 3 versements de salaire (2 500 + 2 500 + 2 000 = **7 000**) égalent le net à payer du bulletin de démonstration de paie-bulletins (7 000,00). C'est un point de jonction naturel entre les deux modules (voir conception).
- Le barème est codé en dur pour **un seul salarié**, sans lien avec l'entreprise ni la paie.
