# Prompt Claude Code — Sprint S4 : interface Vue 3

**Avant toute action**, lis `docs/claude-code/00_CADRE_COMMUN.md` (R0 et R8), `PROJECT_STATE.md`, `BACKLOG.md`, `docs/sprints/S3_RAPPORT.md` et la conception §5.
Maquettes de référence : `https://claude.ai/artifact/GXnwD88kS6TmRE7LKJ3cch`. Le propriétaire peut en fournir des captures dans `docs/maquettes/` si l'accès n'est pas possible.

> **R0** : le frontend n'effectue **aucun calcul de paie**. L'aperçu instantané, les totaux et les cumuls viennent de l'API, donc du noyau. Les montants sont affichés à partir des chaînes décimales reçues, avec le format français d'origine (`formatting.py`, éventuellement exposé par l'API). Les composants paie de SmartCompta (`views/payroll/`, `usePayroll.js`, `lf2026Defaults.json`) sont **interdits** : ils portent un autre moteur.

## Objectif
L'interface des maquettes : épurée, 6 entrées de menu, chaque fonction d'origine accessible.

## Autorisations
L1 uniquement.

## Socle (US-40)
- Vite + Vue 3 + TypeScript + Pinia + vue-router + Tailwind + axios, conventions SmartCompta (`shared/services/http.ts`, stores, `config/env.ts`). Servi à la racine `/`, sans base path codé en dur.
- Layout :
  - menu latéral de 6 entrées : Tableau de bord, Trésorerie, Paie du mois, Salariés, Bulletins & exports, Configuration ;
  - **barre de contexte** : période ‹ mois › et recherche de salarié, dans un store partagé et persistée dans l'URL (`?periode=2026-11&salarie=0001`) ;
  - bandeau « lecture seule » si l'API signale une erreur de stockage.
- Jetons Tailwind repris des maquettes :
  - encre `#16202E`, fond `#F5F6F8`, surfaces `#FFFFFF`, bordures `#E3E6EB` ;
  - primaire `#1F3864`, menu `#14213D`, accent `#F2B544` ;
  - police Inter ; cibles tactiles ≥ 44 px ; contraste ≥ 4,5:1.
- **Statuts** : un seul composant `StatusBadge` pour les deux modules :

  | Statut | Fond / texte |
  |---|---|
  | Brouillon, Non payé | `#EEF0F3` / `#3F4754` |
  | Calculée | `#E6EEFF` / `#1D4ED8` |
  | Clôturée, Payé – à temps | `#E3F4E8` / `#166534` |
  | Payé – retard | `#FDECD8` / `#8A3A00` |
  | En retard | `#FDE7E5` / `#B42318` |
  | À saisir, À venir | pointillé |
  | Remplacée | `#EFEAFB` / `#5B3FA8` |

- Rôles : pour `user`, les boutons d'écriture sont **absents** (pas seulement grisés). Connexion et déconnexion.
- Dialogues de confirmation pour : payer, dévalider, clôturer, rectifier (motif obligatoire), remplacer à l'import, restaurer.

## Écrans
| Story | Écran | Contenu |
|---|---|---|
| US-41 | Tableau de bord (maquette 1) | 4 indicateurs : salaires nets du mois, versés, CNSS, bulletins clôturés. Tableau par salarié : échéances en pastilles, versé / net, statut du bulletin, action. Blocs « À traiter » et « Prochaines échéances » |
| US-42 | Trésorerie (maquettes 2 et 5) | Onglets **À venir** (en retard puis les 6 prochaines) · **Mois** (Payé / Restant / Avancement, tableau par échéance, Payer / Dévalider) · **Rappels J-1** (tableau + export ICS) · **Récap & export** (indicateurs, répartition à temps / retard / avance, 3 téléchargements, tableau complet). Bouton « Déclarer <mois> », bloc Régularisation (mois passés), panneau Diagnostic (réconciliation). Mise en cartes sur téléphone |
| US-43 | Paie du mois (maquette 3) | Liste des salariés du mois avec statut. Panneau en étapes Saisie → Calcul → Contrôles → Clôture : champs de saisie d'origine (gains, jours, congés), bandeau « prérempli depuis… », aperçu via `POST /api/paie/preview` (requête retardée de 300 ms), rapprochement trésorerie (lecture seule), PDF provisoire, enregistrer, calculer, contrôles (erreurs bloquantes et avertissements à confirmer), clôturer, rectifier, versions |
| US-44 | Salariés (maquette 4) | Liste, recherche, filtre actifs, activation / désactivation, création (contrôles de doublons d'origine). Fiche à onglets : **Identité** (tous les champs d'origine ; CIN / CNSS / RIB masqués, affichage temporaire pour `superadmin`) · **Plan de versement** (versions datées, gabarit en lecture seule, cohérence avec le dernier bulletin) · **Bulletins** · **Virements** · **Cumuls** |
| US-45 | Bulletins & exports, Configuration | Archives PDF par période et par salarié avec versions ; livre de paie, récapitulatifs mensuel et annuel, CSV / Excel expurgés. Configuration : Entreprise (logo) · Paramètres de paie (liste des versions, création datée avec motif, **aucune modification d'une version existante**) · Gabarit d'échéancier (lecture seule) · Utilisateurs · Sauvegardes (S5) · Journal |

## Consignes
- Une seule action principale (bouton plein) par écran ; les actions secondaires en contour.
- Détail dans un panneau latéral plutôt qu'une nouvelle page.
- Tableaux larges : défilement horizontal dans leur cadre.
- Aucun libellé métier inventé : reprendre ceux des apps d'origine (types d'échéance, statuts, rubriques du bulletin).
- Tests : Vitest pour les stores et `StatusBadge` ; un test e2e léger (Playwright, en dev uniquement) du parcours « déclarer → payer → saisir → calculer → clôturer ».

## Definition of Done
- Checklist R2 : chaque fonction des diagnostics PAIE_DIAG_2 et PAIE_DIAG_3 est accessible à l'écran, avec un tableau de correspondance dans le rapport.
- Affichage correct à 390 px (trésorerie) et à 1280 px.
- Aucun calcul de paie dans `frontend/` : `grep` documenté dans le rapport.

## Livrable
`docs/sprints/S4_RAPPORT.md` (ligne R0, captures des 5 écrans). Mise à jour des fichiers de suivi. Tag `sprint-S4`.

## Point d'arrêt
STOP. Attends le « go S5 ».
