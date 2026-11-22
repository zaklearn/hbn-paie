# S5 — Essai à blanc de la migration (base de dev)

**Sources : substitution.** Les fichiers du propriétaire n'étant pas encore déposés dans `migration/sources/`, l'essai porte sur des sources de SUBSTITUTION : une base .db produite par l'application paie-bulletins d'origine (démo fictive, rectification, second salarié, brouillon) et un data.json synthétique au format ezzinecdi. L'essai sur les vraies données est à rejouer dès leur dépôt (même commande).

**R0.3 : 5 paie(s) clôturée(s) ou remplacée(s) recalculée(s) en lecture seule, 0 écart(s) chaîne par chaîne.** Rejouabilité : deux exécutions complètes sur deux bases neuves → rapports IDENTIQUES.

## 1. Sources (copies ; originaux inchangés)
| Fichier | SHA-256 avant | SHA-256 après |
|---|---|---|
| `paie_bulletins_sauvegarde.db` | `3aafebfd7b5536a0cb5fab2fc2c86d9d233ab09dcb7a76429c74123cfe0c01ca` | `3aafebfd7b5536a0cb5fab2fc2c86d9d233ab09dcb7a76429c74123cfe0c01ca` |
| `data.json` | `53ddc0e3425f1894e712d8f1e97bf072705b5822fb7c105049d3528b77507067` | `53ddc0e3425f1894e712d8f1e97bf072705b5822fb7c105049d3528b77507067` |
| `backup_20261101.json` | `113adbdd84e33943e5cb4bf345513f29624ea5583f6278ecebbfdd464d1e4187` | `113adbdd84e33943e5cb4bf345513f29624ea5583f6278ecebbfdd464d1e4187` |

## 2. Décomptes source → cible
| Table | Source | Cible |
|---|---|---|
| company | 1 | 1 |
| employees | 2 | 2 |
| parameter_sets | 1 | 1 |
| payslips | 6 | 6 |
| documents | 5 | 5 |
| audit_log | 21 | 22 (+1 : trace `migration.ezzinecdi`) |
| payment_plans | 1 (plan v1 déduit) | 1 |
| echeances | 22 enregistrements | 19 |

Écarts cible/source champ par champ (paie-bulletins) : **aucun**. Échéances : 19 importées / 19 attendues, différentes : aucune. Journal identifiants conservés ; protections de la base vérifiées après import.

## 3. Totaux par mois — paie (paies faisant foi)
| Période | Statuts | Brut | Net | Cot. salariales | Cot. patronales |
|---|---|---|---|---|---|
| 2026-07 | cloturee 2 | 17296.51 | 16220 | 816.03 | 2654.17 |
| 2026-08 | cloturee 1 | 7366.51 | 7000 | 366.43 | 1146.57 |
| 2026-09 | cloturee 1, remplacee 1 | 7436.51 | 7070 | 366.43 | 1146.57 |
| 2026-10 | brouillon 1 | 0 | 0 | 0 | 0 |

## 4. Totaux par mois — trésorerie (après import)
| Période | Payées | Non payées | Montant payé (DH) | Montant non payé (DH) |
|---|---|---|---|---|
| 2026-07 | 4 | 0 | 8 500 | 0 |
| 2026-08 | 4 | 0 | 8 500 | 0 |
| 2026-09 | 4 | 0 | 8 500 | 0 |
| 2026-10 | 1 | 3 | 2 500 | 6 000 |
| 2026-11 | 1 | 2 | 1 500 | 4 500 |

## 5. Bulletins PDF : empreintes recalculées = stockées
5 PDF ; empreintes différentes : **aucune**.

| Fichier | SHA-256 |
|---|---|
| `bulletin_2026-07_0001.pdf` | `be4da8b86b313f989fca0c73e6e888d8205138af5d2b0128315a4d1915b1284e` |
| `bulletin_2026-07_0002.pdf` | `32203bd9a6ee3ec5aeae969cb96b14bbcb62d5fe084833d7e463d00fb0287620` |
| `bulletin_2026-08_0001.pdf` | `c94934f36ec458e55e6124c92abd043236a4197f5b2e8a97ec12f790990c54af` |
| `bulletin_2026-09_0001.pdf` | `6972cbfe1b8dd10a5fd0614ac273d5086c3158c398dbe4d072cb03855f962a6d` |
| `bulletin_2026-09_0001_v2.pdf` | `62db1af9d988015be643b45a0c799f6d9883b5b1601556f5df2397f77e3a8c6a` |

## 6. R0.3 — recalcul de vérification
- Paies vérifiées : 5 ; écarts : aucun (jamais corrigés).
- Cumuls différents de ceux qu'on calculerait aujourd'hui (information, attendu après une rectification d'un mois antérieur : les bulletins conservent les cumuls tels qu'émis) : aucun.

## 7. ezzinecdi — plan v1, simulation de la réconciliation, anomalies
- Plan v1 (premier mois) : effet 2026-07, 1er versement 2 500, CNSS 1 500, 2e 2 500, 3e 2 000 DH.
- Compte rendu de la réconciliation d'origine (simulation) : {"recus": 22, "rejetes": 1, "doublons": 1, "rappels_corriges": 0, "montants_corriges": 0, "mois_corriges": 0, "statuts_corriges": 1, "total": 20, "payes": 14, "non_payes": 6, "en_retard": 5, "modifie": true}.
- Corrections qu'elle ferait (NON appliquées) : 1.
  - n° 19 Novembre 2026 / Salaire – 2e versement : date_paiement '2026-11-19' → None
- Non importés : hors schéma 1, doublons écartés (le payé prime) 1, incohérences statut/date 1.
  - Novembre 2026 / Salaire – 2e versement : statut « Non payé » avec date 2026-11-19
- `backup_20261101.json` comparé à data.json : 16 enregistrements, seulement dans data.json 4, seulement dans le backup 0, différents 0.

## 8. Simulation (--dry-run) : aucune écriture
Simulation paie-bulletins : cible inchangée ; rapport de simulation identique au rapport d'import sur les contrôles source (R0.3, PDF, totaux) : oui.

## 9. Points soumis au propriétaire
1. Déposer la sauvegarde .db, data.json + backup_*.json et le matricule : l'essai sera rejoué sur ces copies.
2. Valider les éventuelles corrections proposées par la réconciliation (aucune n'est appliquée).
3. Les enregistrements non importés (hors schéma, doublon écarté, incohérence) restent à arbitrer.
