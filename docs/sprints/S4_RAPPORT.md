# S4 — Rapport : interface Vue 3 (21/11/2026)

**R0 : intégrité du noyau OK (10 fichiers), golden OK (6 cas), Excel non fourni.** Le frontend **ne calcule rien** : aperçu, totaux, cumuls, rapprochement, régularité et indicateurs viennent de l'API. Preuve `grep` ci-dessous.

**Tests :**
- backend : 269 réussis, 3 ignorés (+4 tests des endpoints S4) ;
- **Vitest** : 21 réussis (`StatusBadge`, stores, formatage) ;
- **e2e Playwright** de dev : 3 réussis.
  - Parcours « déclarer → payer → saisir → calculer → clôturer » sur octobre 2026 de la démo fictive.
  - Trésorerie à 390 px, sans défilement horizontal.
  - Rôle `user` sans aucun bouton d'écriture.

## Stories
| Story | Statut | Contenu |
|---|---|---|
| US-40 | Fait | Vite 6, Vue 3.5, TS 5.6, Pinia 2, vue-router 4, Tailwind 3.4, axios (versions exactes, `package-lock.json`). Menu de 6 entrées, barre de contexte période ‹ › + recherche de salarié (store partagé, URL `?periode=2026-11&salarie=0001`), bandeau « lecture seule ». Jetons des maquettes, police Inter **embarquée** (OFL), cibles ≥ 44 px. **Un seul `StatusBadge`** avec le code couleur S4. Boutons d'écriture **absents** pour `user`. Dialogues : payer, dévalider, clôturer, rectifier (motif), supprimer un brouillon. SPA servie à la racine par FastAPI (`PAIE_STATIC_DIR`, repli vers `index.html`) |
| US-41 | Fait | Maquette 1 : 4 indicateurs, tableau par salarié (pastilles, versé / net, bulletin, action), « À traiter », « Prochaines échéances ». Ajout de la **section annuelle d'origine** : mois ouverts et clôturés, alertes, dernières paies. Tous les totaux sont **calculés côté serveur** (`/api/paie/tableau-de-bord-mois`) |
| US-42 | Fait | Maquettes 2 et 5 : onglets À venir, Mois, Rappels J-1, Récap & export ; Déclarer ; Régularisation ; Diagnostic ; **mise en cartes au téléphone**. Le statut calculé du dialogue « Payer » est donné par l'API (`/regularite`, règle d'origine) |
| US-43 | Fait | Maquette 3 : liste du mois, étapes Saisie → Calcul → Contrôles → Clôture. Libellés de saisie **d'origine**, bandeau de préremplissage, aperçu via `POST /api/paie/apercu` (300 ms), contrôles d'origine en direct, rapprochement en lecture seule, PDF provisoire, clôture, rectification, versions |
| US-44 | Fait | Maquette 4 : liste, recherche, filtre actifs, activation, création et modification avec les doublons signalés par l'API. Fiche à onglets Identité / Plan / Bulletins / Virements / Cumuls ; CIN, CNSS et RIB masqués, affichage 30 s pour le superadmin |
| US-45 | Fait | Archives PDF par période et salarié, avec versions. Livre de paie et récapitulatifs mensuel et annuel. CSV et Excel aux noms d'origine. Configuration : Entreprise (logo), Paramètres (versions, création datée avec motif, aucune modification), Gabarit (lecture seule), Utilisateurs, Sauvegardes (S5), Journal |

**Captures** (`docs/sprints/S4_captures/`, produites par l'e2e) :
- `1-tableau-de-bord-1280.png`
- `2-tresorerie-mois-1280.png`
- `3-paie-du-mois-1280.png`
- `4-fiche-salarie-1280.png`
- `5-tresorerie-mobile-390.png`

## R0 — aucun calcul de paie dans `frontend/`
```
grep -rnE "parseFloat|parseInt|Number\(|toFixed|Math\.(round|floor|ceil|min|max)|\*\s*[0-9.]|reduce\(" frontend/src
  KpiCard.vue:10        Math.min/Math.max : largeur de la barre de progression (pourcentage reçu de l'API)
  shared/format.ts:19   Math.max : complète « ,00 » (mise en forme de texte, aucun arrondi)
  stores/context.ts:8,17,18  Number / Math.floor : navigation entre périodes (mois ± 1)
grep -rnE "(net_a_payer|salaire|montant|cotisation|brut|cumul|ir_)[a-z_]*\s*[-+*/]\s*[a-z0-9(]" frontend/src  → aucun
```
`fmtMoney` ne fait que de la mise en forme de texte, sans conversion numérique, et le test « ne tronque ni n'arrondit jamais » le vérifie. Les composants paie de SmartCompta ne sont pas utilisés.

## Checklist R2 — chaque fonction d'origine a son équivalent
| Origine | Fonction | Écran HBN Paie |
|---|---|---|
| paie | Tableau de bord : entreprise, salariés, mois ouverts/clôturés, dernières paies, alertes | Tableau de bord, section « Année — paie », et indicateurs du mois |
| paie | Entreprise : fiche unique, logo | Configuration › Entreprise |
| paie | Salariés : tous les champs, unicités, recherche, activation (jamais supprimés), masquage | Salariés (liste et fiche) |
| paie | Paramètres : versions datées, motif, historique, immuables, barème, méthode des totaux | Configuration › Paramètres de paie |
| paie | Saisie : tout mois, préremplissage signalé, 10 champs, contrôles, aperçu instantané | Paie du mois (barre de contexte, bandeau, contrôles en direct, aperçu) |
| paie | Calcul et validation : statuts, contrôles de clôture, PDF provisoire, clôture confirmée, rectification avec motif, `_v2` | Paie du mois (étapes, contrôles, dialogues, versions) |
| paie | Bulletins et archives : PDF + SHA-256, consultation, téléchargement (mobile compris) | Bulletins & exports, Paie du mois et fiche ; téléchargement par lien, compatible mobile |
| paie | Récapitulatifs et exports sans CIN, CNSS ni banque | Bulletins & exports (livre, mensuel, annuel, CSV, Excel) |
| paie | Sauvegardes et administration | Configuration › Sauvegardes (**S5**) et › Journal (fait) |
| ezzinecdi | Porte d'authentification, rôle, déconnexion | Connexion, rôle affiché dans le menu, Déconnexion |
| ezzinecdi | Barre latérale : rôle, alerte lecture seule, mois courant, navigation 4 panneaux, régularisation, diagnostic | Menu et barre de contexte, bandeau lecture seule, onglets de la Trésorerie, blocs Régularisation et Diagnostic |
| ezzinecdi | Base vide : superadmin déclare le 1er mois, user voit un message d'attente | Trésorerie › Mois : message, et bouton Déclarer pour le superadmin |
| ezzinecdi | À venir : en retard (n), puis 6 prochaines, en cartes avec Payer | Trésorerie › À venir |
| ezzinecdi | Mois courant : déclarer, Payé / Restant / Avancement, cartes, dévalider | Trésorerie › Mois |
| ezzinecdi | Rappels : tableau des non payées et export `.ics` | Trésorerie › Rappels J-1 |
| ezzinecdi | Récap & export : indicateurs, régularité, 3 téléchargements, tableau complet | Trésorerie › Récap & export |
| ezzinecdi | Payer / dévalider avec dialogue | Dialogues Confirmer le paiement et Dévalider |
| ezzinecdi | Import / remplacement de la base | **S5** (outil de migration US-52) |
| ezzinecdi | Réconciliation au chargement | Trésorerie › Diagnostic (simulation, conception §4) |
| ezzinecdi | Excel : 8 colonnes, TOTAL, filtres, volets | Exports d'origine (S3), boutons Recap et Base complète |

## Écarts et décisions (à valider)
1. **Dialogue « Payer » :**
   - Le champ libre « Observation » de la maquette n'est pas repris : l'observation reste celle d'origine, automatique (« Payé le jj/mm/aaaa (régularité) »), en vertu de R1. **À trancher** si vous le voulez.
   - La date du virement est saisie, et le statut calculé est montré avant confirmation.
2. **Trésorerie au téléphone :** les 4 onglets sont en haut de l'écran, et non dans la barre inférieure de la maquette 5. Les cartes, le bouton Payer de 44 px, l'en-tête et l'absence de défilement horizontal sont conformes.
3. **« Salaires nets du mois »** est le total des plans de versement, comme le sous-titre de la maquette. Les nets réels figurent dans le tableau (versé / net).
4. **Paramètres :** les taux se saisissent en texte décimal exact (0.0448) et non en %. L'original convertissait en flottant `rate × 100`, ce qui serait un calcul dans le navigateur.
5. **Police Inter embarquée**, sans appel à Google Fonts. Raisons : confidentialité, et rendu identique sur toutes les machines.
6. **Outillage de dev :**
   - l'e2e Chromium dispose de 1 Go (256 Mo ne suffisent pas), en dev seulement ;
   - `npm` avertit que deux dépendances indirectes de dev (`abbrev`, `nopt`) préfèrent Node 22, alors que la compilation fonctionne en Node 20. Le Dockerfile de S6 prévoit `node:20-alpine` ; Node 22 serait possible.
7. **Images Docker ajoutées en dev :** `node:20-alpine` et `mcr.microsoft.com/playwright:v1.65.1-noble`, environ 2 Go en tout. Il reste ~18 Go libres.

## Questions au propriétaire
1. Validez-vous les écarts 1 à 4, en particulier l'observation automatique du paiement (1) et les onglets en haut sur mobile (2) ?
2. Faut-il pousser `main` et le tag `sprint-S4` ?
