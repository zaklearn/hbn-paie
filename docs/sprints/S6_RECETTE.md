# S6 — Recette fonctionnelle (checklist R2) — à signer par le propriétaire

Application : https://paie.hbnfactory.cloud · compte `zak` (superadmin) · données réelles importées le 22/11/2026.
Cocher chaque ligne (OK / KO + remarque). Les actions de test marquées ↩ sont annulées dans la foulée.

## Paie (paie-bulletins)
| # | Fonction d'origine | Où / comment vérifier | OK/KO |
|---|---|---|---|
| P1 | Tableau de bord (entreprise, salariés, mois ouverts/clôturés, dernières paies, alertes) | Tableau de bord, période 10/2026 et section « Année 2026 » | |
| P2 | Entreprise (fiche unique, logo) | Configuration › Entreprise | |
| P3 | Salariés (fiche, unicités, recherche, activation, masquage CIN/CNSS/RIB) | Salariés › fiche 181159983 (onglets) | |
| P4 | Paramètres versionnés, motif, immuables | Configuration › Paramètres de paie (version 2000-01) | |
| P5 | Saisie mensuelle, préremplissage, contrôles, aperçu instantané | Paie du mois, période 11/2026 : bandeau « repris d'octobre », aperçu (ne pas clôturer si non souhaité) | |
| P6 | Calcul, contrôles de clôture, PDF provisoire, clôture, rectification | Paie du mois 11/2026 : Calculer, Aperçu PDF provisoire ; (rectification : seulement si souhaitée) | |
| P7 | Bulletins archivés + SHA-256, téléchargement (mobile compris) | Bulletins & exports : télécharger juillet → octobre ; **comparer au PDF d'origine** | |
| P8 | Livre de paie, récap mensuel/annuel, CSV/Excel sans CIN/CNSS/banque | Bulletins & exports : CSV et Excel ouverts ; cumul annuel 28 000,00 net | |
| P9 | Sauvegarde, restauration, journal | Configuration › Sauvegardes (créer, télécharger) ; Journal | |

## Trésorerie (ezzinecdi)
| # | Fonction d'origine | Où / comment vérifier | OK/KO |
|---|---|---|---|
| T1 | Authentification, rôle, déconnexion | Connexion / Déconnexion ; rôle affiché | |
| T2 | À venir (en retard, 6 prochaines, Payer) | Trésorerie › À venir (3e versement de novembre) | |
| T3 | Mois : déclarer, Payé / Restant / Avancement, cartes, dévalider | Trésorerie › Mois 11/2026 : 6 500 payés, 2 000 restants | |
| T4 | Payer / Dévalider avec dialogue ↩ | Payer le 3e versement de novembre puis **Dévalider** (journal : paiement + dévalidation) | |
| T5 | Rappels J-1 + export .ics | Trésorerie › Rappels J-1 : exporter, ouvrir dans un agenda | |
| T6 | Récap & export : 3 téléchargements, régularité | Trésorerie › Récap & export : recap_paiements.xlsx, base_complete.xlsx, .ics | |
| T7 | Régularisation d'un mois passé | Bloc « Régularisation » (consultation) | |
| T8 | Diagnostic (réconciliation) | Bloc « Diagnostic » avec le salarié choisi : 0 correction | |
| T9 | Téléphone (390 px) | Trésorerie sur téléphone : cartes, bouton Payer | |

## Rapprochement (nouveau)
| # | Fonction | Où | OK/KO |
|---|---|---|---|
| R1 | Versé / net, CNSS / cotisations (lecture seule) | Paie du mois 10/2026 : 7 000 / 7 000 ; CNSS 1 500 · cotisations 1 513,00 | |

**Recette validée par le propriétaire (Zakaria Benhoumad) le 22/11/2026 : « Recette OK, tag v1.0.0 » (validation écrite dans la session Claude Code).**
