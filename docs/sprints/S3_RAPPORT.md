# S3 — Rapport : Trésorerie multi-salariés (21/11/2026)

**R0 : intégrité du noyau OK (10 fichiers), golden OK (6 cas), Excel non fourni.**
- Aucun fichier de `app/paie/core/` n'est modifié.
- **Test d'isolation (US-36) :** clôturer juillet à septembre 2026 avec puis sans écart de trésorerie donne une paie **identique chaîne par chaîne** : résultat, cumuls, saisie, paramètres, copies figées, statut, version et texte du PDF.
- La trésorerie n'écrit jamais dans les tables de paie (empreinte de `payslips` et `documents` inchangée).

**Suite complète : 265 réussis, 3 ignorés** (inchangés depuis S2). Le test d'origine `test_logic.py` passe **9/9 sans changement d'attendu**.

## Stories
| Story | Statut | Contenu / preuve |
|---|---|---|
| US-30 | Fait | `db_gen`, `integrity`, `rapport` et `dates` copiés dans `app/tresorerie/legacy/`. **Diff du legacy : uniquement les 3 imports** entre modules (`import db_gen` → `from app.tresorerie.legacy import db_gen`, etc.). C'était inévitable : ce sont des modules de premier niveau à l'origine. L'identité est prouvée octet pour octet (`test_legacy_fidelity.py`) |
| US-31 | Fait | `payment_plans` : employee_id, `valid_from` AAAA-MM, S1 / CNSS / S2 / S3 en **entiers DH**, commentaire, auteur. Les versions sont **immuables** (déclencheur, comme les paramètres de paie). Un plan est obligatoire pour déclarer un mois. Un nouveau plan ne modifie aucune échéance existante (testé) |
| US-32 | Fait | `echeances` : les 9 champs d'origine, plus employee_id, annee, mois_num, `version` (verrou optimiste) et `source_ref`. Clé `UNIQUE (salarié, année, mois, type)`. Les types et statuts d'origine sont imposés par `CHECK`, ainsi que « payé ⇔ date de paiement ». La numérotation `n` est faite par salarié, avec le tri d'origine (`trier_renumeroter`) |
| US-33 | Fait | La déclaration couvre tous les salariés actifs du mois, ou un seul. Un salarié est actif s'il est embauché avant la fin du mois, sorti après le début du mois, et si sa fiche est active. Anti-doublon par salarié ; compte rendu « n salarié(s), 4 échéances chacun, m ignoré(s) » avec motif. Payer recalcule le statut au jour, et dévalider remet à « Non payé » en effaçant la date et l'observation. Un conflit de version donne une erreur 409. Les mois passés se régularisent sur les années `range(an − 2, an + 3)` |
| US-34 | Fait | `reconcile_plan` est une copie de `integrity.reconcile` où **une seule ligne** change : `MONTANT_TYPE[type]` devient `plan(salarié, type, date)`. Un test le vérifie, et un autre montre qu'avec le barème d'origine le résultat est égal à l'original. `simulate()` n'écrit rien, ne modifie pas son entrée et liste les corrections ; la fusion garde le payé |
| US-35 | Fait | Mêmes noms de fichiers : `recap_paiements.xlsx`, `base_complete.xlsx`, `rappels_salaires_cnss.ics`. Pour un salarié seul, le fichier est celui d'origine. Pour plusieurs, une feuille par salarié est produite par la fonction d'origine puis recopiée à l'identique : valeurs, `#,##0 "DH"`, TOTAL, filtres, volets et largeurs (testé feuille à feuille). L'ICS d'origine est fusionné, avec le nom du salarié dans l'intitulé (voir écart 4) |
| US-36 | Fait | Rapprochement **en lecture seule** : le versé (S1 + S2 + S3 payés) est comparé au net (bulletin clôturé, sinon calculé), la CNSS versée aux cotisations salariales + patronales. Sur la démo, on retrouve bien 7 000 = 7 000 et 1 500 face à 1 513,00 (conception §1). Il est branché sur `CLOSURE_WARNING_PROVIDERS` comme **avertissement confirmable** : « Versements incomplets … » ou « Écart de x DH … » |
| US-37 | Fait | `/api/tresorerie/*` : gabarit, plans, échéances (filtres période, salarié, payé), à venir, rappels, récap, déclarer, payer, dévalider, diagnostic (réconciliation simulée), rapprochement et 3 exports. Le badge « en retard » est calculé, jamais stocké. Le rôle `user` est en lecture seule (403 sur les 4 écritures) |

**Tests ajoutés :** 24 tests de service et 5 tests d'API. Ils couvrent 3 salariés aux plans différents, une sortie au 05/10 et une entrée au 15/10, février au 28, le conflit de version, le changement de plan et la renumérotation. Ils couvrent aussi l'immuabilité, `CHECK` compris, la vue « à venir » (en retard puis 6 prochaines), les exports et l'isolation R0.

## Écarts et décisions d'exécution (à valider)
1. **Payer avec une date saisie.** La date de paiement est facultative et vaut aujourd'hui par défaut, comme l'original, qui ne connaissait que la date du jour. Elle ne peut pas être dans le futur. L'observation reste celle d'origine : « Payé le jj/mm/aaaa (régularité) ». Raison : le backlog dit « payer (date → statut calculé) », et la régularisation des mois passés en a besoin.
2. **Plage de régularisation :** de l'année − 2 à l'année + 2. Cela correspond au `range(an − 2, an + 3)` de l'original, dont la borne haute est exclue. Le pack indique « −2 à +3 », mais j'ai suivi le code d'origine.
3. **Avertissement de clôture.**
   - Il n'est émis que pour un salarié suivi en trésorerie, c'est-à-dire ayant un plan en vigueur sur le mois. Sans cela, il ne serait que du bruit, et les tests de paie d'origine ne changent pas.
   - La CNSS est **affichée pour information** dans le rapprochement, et ne déclenche pas d'avertissement (conception §3). Sinon, l'écart structurel de 1 500 contre 1 513,00 avertirait à chaque mois.
4. **ICS :**
   - l'intitulé devient « Prénom NOM · type — montant DH » ;
   - l'UID devient `uuid5(matricule|date|intitulé)@hbn-paie`, au lieu de `uuid5(date-type)@ezzinecdi`, pour rester unique entre salariés. **Conséquence :** un calendrier qui avait déjà importé les rappels d'ezzinecdi les verra une fois en double.
5. **Fonctions d'origine non reprises en S3 :**
   - « Import / Remplacer toute la base » relève de l'outil de migration de S5 (US-52) ;
   - la réconciliation « au chargement », qui réparait et enregistrait silencieusement les données, est remplacée par les contraintes de la base et par un diagnostic en simulation. Conception §4 : rien n'est corrigé d'office.
   - **À confirmer pour la checklist R2.**
6. **Gabarit :** jours, types et ordre viennent du `BAREME` d'origine ; ses montants ne servent plus, puisque ce sont ceux du plan de chaque salarié.

## Questions au propriétaire
1. Validez-vous les écarts 1 à 6, en particulier la date de paiement saisie (1), la CNSS en information seule (3) et l'UID des rappels ICS (4) ?
2. Faut-il pousser `main` et le tag `sprint-S3` ?
