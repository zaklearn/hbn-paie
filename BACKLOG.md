# HBN Paie — Backlog produit

Version 1.0 · 21/11/2026 · Priorité = ordre des sprints. CA = critère d'acceptation. Statut initial : À faire.

## Statuts (mis à jour en fin de sprint)
| Story | Statut |
|---|---|
| US-01 | Fait |
| US-02 | Fait — remplacée par la décision Q1 : MySQL dédié `paie-db` (8.4), aucun compte à déposer ; test de connexion reporté au MySQL de dev (S1) |
| US-03 | Fait (local) ; push en attente de la clé de déploiement (Q2) |
| US-04 | Fait en Python 3.14 ; remesure en 3.12 dans `hbn-paie-dev` au début de S1 (Q3) |
| US-05 | Bloqué (fichiers sources et matricule à déposer par le propriétaire — Q4) ; ne bloque pas S1 |
| US-10 à US-64 | À faire |

## E0 — Cadrage (S0)
| ID | Story | CA |
|---|---|---|
| US-01 | Vérifier le DNS de `paie.hbnfactory.cloud`, l'accès VPS, la RAM et le disque | Rapport L0 |
| US-02 | Localiser le serveur MySQL et tester la connexion depuis le VPS ; relever la version et les droits (JSON, colonnes générées, `TRIGGER`) | Rapport ; blocage signalé si injoignable |
| US-03 | Créer le dépôt `zaklearn/hbn-paie` et son squelette, avec les sources gelées (paie-bulletins `df7ff12`, ezzinecdi `85354c9`) dans `upstream/`, exclues de l'image | Dépôt créé, SHA consignés |
| US-04 | Mesurer la référence : suites de tests d'origine exécutées telles quelles | Nombre de tests passés consigné |
| US-05 | Recevoir les sources de données (sauvegarde `.db` de paie-bulletins, `data.json` d'ezzinecdi, classeur Excel de référence si disponible), stockées 0600 hors Git, avec empreintes | Inventaire + SHA-256 |

## E1 — Socle et noyau paie gelé (S1)
| ID | Story | CA |
|---|---|---|
| US-10 | Squelette FastAPI (`core/`, `db/`, `paie/`, `tresorerie/`, `socle/`), config par variables d'environnement, `/health` | App démarre, test santé OK |
| US-11 | Noyau gelé copié (R0.1), `UPSTREAM.sha256`, `check_core_integrity.py`, test bloquant | Test intégrité vert ; une modification volontaire le fait échouer |
| US-12 | Tests du noyau portés (engine, écarts PDF, PDF, golden, référence Excel) sans changer d'attendu | 100 % verts, nombre = référence US-04 |
| US-13 | Environnement de dev : MySQL 8.4 en conteneur (dev/CI uniquement), Alembic initialisé | `alembic upgrade head` sur base vide OK |

## E2 — Paie sur MySQL (S2)
| ID | Story | CA |
|---|---|---|
| US-20 | Schéma : company, employees, parameter_sets, payslips, documents, audit_log, users, schema version ; valeurs de calcul en texte décimal exact (JSON) | Migration Alembic ; aucune colonne arrondissante pour le calcul |
| US-21 | Contraintes : matricule unique ; CIN/CNSS uniques si renseignés ; « une paie ouverte + une clôturée en vigueur par salarié × mois » via colonnes générées ; immuabilité (déclencheurs `SIGNAL` + contrôle en service) | Tests de violation |
| US-22 | Dépôts (repositories) MySQL équivalents à `repos.py`, transactions + `SELECT … FOR UPDATE` | Tests unitaires |
| US-23 | Services `master_data`, `payroll`, `reporting` portés en logique identique (brouillon → calculée → clôturée → rectification, contrôles, préremplissage, cumuls figés, PDF à la clôture dans la même transaction) | `test_workflow`, `test_non_regression`, `test_services_misc` portés et verts |
| US-24 | Comptes nominatifs, rôles `superadmin` / `user`, hachage PBKDF2 du noyau, sessions, journal = utilisateur connecté | `test_access_control` porté + tests rôles |
| US-25 | API REST `/api/paie/*` (entreprise, salariés, paramètres, saisie, aperçu, calcul, contrôles, clôture, rectification, documents, exports, tableau de bord) | Tests API |

## E3 — Trésorerie multi-salariés (S3)
| ID | Story | CA |
|---|---|---|
| US-30 | Logiques ezzinecdi portées à l'identique (`db_gen`, `integrity`, `rapport`, `dates`) | 9 tests d'origine verts |
| US-31 | Plan de versement par salarié, versionné par date d'effet (S1, S2, S3, CNSS ; v1 du salarié actuel = 2 500 / 2 500 / 2 000 / 1 500) | Un changement de plan ne modifie aucune échéance existante |
| US-32 | Échéances par salarié, UNIQUE (employee_id, année, mois, type), colonne `version` (verrou optimiste) | Tests conflit |
| US-33 | Déclarer un mois (tous les salariés actifs sur le mois, ou un seul) ; payer (date → statut calculé) ; dévalider ; régularisation d'un mois passé | Tests ; mêmes statuts que l'original |
| US-34 | Réconciliation : validation `montant == plan(salarié, type, date)`, dédoublonnage (le payé prime), compte rendu ; en mode simulation pour l'import | Tests |
| US-35 | Exports : `recap_paiements.xlsx`, `base_complete.xlsx` (8 colonnes, mise en forme identique), avec une feuille par salarié quand plusieurs sont exportés ; ICS rappels J-1 (nom du salarié dans l'intitulé de l'événement) | Feuille d'un salarié identique au format d'origine |
| US-36 | Rapprochement en **lecture seule** (R0.2) : versé / net, CNSS versée / cotisations ; avertissement confirmable à la clôture | Test : aucun effet sur le calcul ni sur les données de paie |
| US-37 | API REST `/api/tresorerie/*` | Tests API |

## E4 — Interface (S4)
| ID | Story | CA |
|---|---|---|
| US-40 | Socle Vue : layout menu 6 entrées, barre de contexte (période + salarié) partagée, connexion, rôles (écritures masquées pour `user`) | Conforme maquette 1 |
| US-41 | Tableau de bord | Maquette 1 |
| US-42 | Trésorerie : onglets À venir, Mois, Rappels, Récap & export ; dialogues Payer / Dévalider ; Déclarer ; Régularisation ; version mobile | Maquettes 2 et 5 |
| US-43 | Paie du mois : liste + panneau Saisie → Calcul → Contrôles → Clôture, aperçu via l'API, PDF provisoire, rectification | Maquette 3 ; aucun calcul en JS (R0) |
| US-44 | Salariés : liste, recherche, activation ; fiche à onglets (Identité, Plan de versement, Bulletins, Virements, Cumuls) ; masquage CIN/CNSS/RIB | Maquette 4 |
| US-45 | Bulletins & exports ; Configuration (Entreprise, Paramètres versionnés, Gabarit en lecture seule, Utilisateurs, Sauvegardes, Journal) | Checklist R2 |

## E5 — Exploitation et reprise (S5)
| ID | Story | CA |
|---|---|---|
| US-50 | Sauvegarde / restauration de la base `paie` depuis l'interface et en script (validation, sauvegarde auto avant restauration) | Restauration testée sur base de dev |
| US-51 | Outil de migration paie-bulletins (`.db` SQLite) → `paie`, import à l'identique (PDF, empreintes, versions, journal), mode `--dry-run` | Rapport de contrôles |
| US-52 | Outil de migration ezzinecdi (`data.json`) → échéances du salarié désigné, plan v1, `source_ref`, réconciliation en simulation | Rapport de contrôles |
| US-53 | Rapport de migration : décomptes, totaux par mois, empreintes PDF, recalcul R0.3 chaîne par chaîne, corrections proposées (jamais appliquées) | Exécuté sur une base de dev à partir de copies |

## E6 — Déploiement et bascule (S6)
| ID | Story | CA |
|---|---|---|
| US-60 | Dockerfile multi-stage, `compose.yaml` (Traefik : `websecure`, `le`, `hbn-secure-headers@file`, port 8000, réseau `hbn-proxy`), limite 512 Mo, `unless-stopped`, healthcheck | `docker compose config` OK |
| US-61 | **L3** Création du service `paie-db` (MySQL 8.4 dédié), de la base `paie` + utilisateur dédié, migrations, démarrage | HTTPS 200, aucun impact sur Tangerine ni le portfolio |
| US-62 | **L3** Import des données réelles + rapport de migration validé par le propriétaire | Validation écrite |
| US-63 | Recette fonctionnelle complète (checklist R2) et mesure mémoire | Checklist signée |
| US-64 | Bascule : apps Streamlit en lecture seule, documentation d'exploitation, mise à jour des fichiers d'état HBNFACTORY | Mise en service |
