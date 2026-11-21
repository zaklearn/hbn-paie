# Prompt Claude Code — Sprint S3 : module Trésorerie multi-salariés

**Avant toute action**, lis `docs/claude-code/00_CADRE_COMMUN.md` (R0 et R1), `PROJECT_STATE.md`, `BACKLOG.md`, `docs/sprints/S2_RAPPORT.md` et la conception §1 à §3.

> **R0** : la trésorerie ne touche jamais au calcul de paie. Les montants versés ne deviennent jamais une saisie de bulletin. Le rapprochement est un affichage en lecture seule plus un avertissement confirmable. Aucun fichier de `app/paie/core/` n'est modifié.

## Objectif
Porter ezzinecdi v5 à l'identique, puis l'étendre à plusieurs salariés. C'est la seule extension validée : identifiant unique par salarié, et plan de versement dont les montants sont propres à chaque salarié.

## Autorisations
L1 uniquement.

## Rappel des règles fonctionnelles (exactes)
- **Gabarit fixe, commun à tous**, défini dans le code et non modifiable depuis l'interface :
  - le 10 : `Salaire – 1er versement` et `CNSS – cotisation mensuelle` ;
  - le 20 : `Salaire – 2e versement` ;
  - le 30, ou le dernier jour du mois : `Salaire – 3e versement` ;
  - tri dans cet ordre ; `rappel_j1` = échéance − 1 jour.
- **Statuts** : `Non payé`, `Payé – à temps`, `Payé – retard`, `Payé – avance`. Régularité calculée au jour, par `integrity.regularite()` d'origine. Le badge « en retard » est calculé à l'affichage et jamais stocké.
- **Montants** : propres à chaque salarié, pris dans son **plan de versement en vigueur à la date d'échéance** (versionné par date d'effet).

## Stories
1. **US-30** : copie `db_gen.py`, `integrity.py`, `rapport.py` et `dates.py` dans `app/tresorerie/legacy/`. Sans Streamlit, ils se portent directement. Porte `tests/test_logic.py` : 9 tests verts sans changer d'attendu. Les adaptations multi-salariés se font dans `app/tresorerie/services/`, en enveloppant ces fonctions, et en ne modifiant le legacy que si c'est inévitable (diff justifiée dans le rapport).
2. **US-31** : table `payment_plans` (employee_id, valid_from `AAAA-MM`, s1, cnss, s2, s3 en **entiers DH** comme l'original, comment, created_by). Une version ne se modifie pas ; une nouvelle version n'affecte jamais une échéance existante. API et règles : un plan est obligatoire pour déclarer un mois pour un salarié.
3. **US-32** : table `echeances`. Les 9 champs d'origine, plus `employee_id`, `annee`, `mois_num`, `version` (verrou optimiste) et `source_ref`. `UNIQUE (employee_id, annee, mois_num, type)`. La numérotation `n` est par salarié, triée comme l'original.
4. **US-33** :
   - déclarer un mois pour tous les salariés actifs pendant ce mois (embauche ≤ fin de mois, sortie ≥ début de mois, `actif`), ou pour un seul ;
   - anti-doublon par salarié, compte rendu « n salariés, 4 échéances chacun, m ignorés » ;
   - payer : `date_paiement` → statut recalculé ;
   - dévalider : retour à « Non payé », date effacée ;
   - régularisation des mois passés (année −2 à +3, comme l'original) ;
   - conflit de version : HTTP 409 et message clair.
5. **US-34** : réconciliation d'origine adaptée : `montant == plan(salarié, type, date)` au lieu de `MONTANT_TYPE[type]`, le reste identique. Mode `simulate=True` : renvoie les corrections sans rien écrire (utilisé par l'import en S5). La fusion à l'import conserve toujours le payé.
6. **US-35** : `build_recap_xlsx` et `build_ics` d'origine, avec une feuille par salarié quand plusieurs sont exportés. La feuille d'un salarié reprend exactement les 8 colonnes, les styles, le format `#,##0 "DH"`, la ligne TOTAL, les filtres et les volets figés. ICS : nom du salarié dans l'intitulé. Mêmes noms de fichiers.
7. **US-36** : service `rapprochement(employee_id, année, mois)` en **lecture seule** :
   - versé salaire = somme des S1 + S2 + S3 payés ;
   - net = `net_a_payer` du bulletin (clôturé, sinon calculé) ;
   - CNSS versée comparée à `total_cotisations_salariales + total_cotisations_patronales` du résultat stocké ;
   - aucune écriture.
   
   Branche-le sur le point d'extension de `closure_checks` (S2) comme **avertissement** : « versements incomplets » ou « écart de x DH ». Test obligatoire : clôturer avec et sans écart donne un résultat de paie **identique chaîne par chaîne**.
8. **US-37** : API `/api/tresorerie/*` : plans, échéances (filtres : période, salarié, statut), à venir, rappels, déclarer, payer, dévalider, réconciliation, exports, rapprochement.

## Definition of Done
- Les 9 tests d'origine sont verts.
- Tests multi-salariés verts : 3 salariés, plans différents, entrée et sortie en cours de mois, conflit de version, changement de plan.
- Le test d'isolation R0 (US-36) est vert, l'intégrité du noyau est verte.

## Livrable
`docs/sprints/S3_RAPPORT.md` (ligne R0, diff du legacy s'il y en a). Mise à jour des fichiers de suivi. Tag `sprint-S3`.

## Point d'arrêt
STOP. Attends le « go S4 ».
