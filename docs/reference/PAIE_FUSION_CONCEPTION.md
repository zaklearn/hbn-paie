# Conception théorique v2 — « HBN Paie » (fusion paie-bulletins + ezzinecdi)

Date : 21/11/2026 · Version 2.1 · Statut : **CONCEPTION VALIDÉE par le propriétaire le 21/11/2026** · Exécution : pack Claude Code `PAIE_CLAUDE_CODE_PACK.md`
Entrées : PAIE_DIAG_1/2/3 + réponses du propriétaire du 21/11/2026.
Maquettes : canvas « HBN Paie — maquettes de l'application » (5 écrans).

## 0. Décisions

| # | Sujet | Décision | Statut |
|---|---|---|---|
| D1 | Adresse | `paie.hbnfactory.cloud`, DNS configuré par le propriétaire | DÉCISION VALIDÉE (DNS à vérifier en S0) |
| D2 | Base | Nouvelle base `paie` sur le serveur MySQL existant (celui de WordPress), utilisateur MySQL dédié | DÉCISION VALIDÉE |
| D3 | Plateforme | Autonome (`/opt/hbnfactory/platforms/paie/`, dépôt propre) | DÉCISION VALIDÉE |
| D4 | Lien entre modules | Les deux modules forment une chaîne : la trésorerie verse, la paie documente | DÉCISION VALIDÉE |
| D5 | Coefficients | Fixes et communs à tous les salariés ; application à plusieurs salariés, chacun avec un identifiant unique | DÉCISION VALIDÉE |
| D6 | Données | Reprise des données existantes sans altération | DÉCISION VALIDÉE |
| D7 | Interface | Ergonomie soignée, sans encombrement | DÉCISION VALIDÉE |
| **D8** | **Formules du bulletin** | **Reprises telles quelles : jamais modifiées ni « rapprochées » d'un autre moteur (SmartCompta compris), sinon écart entre les bulletins et la comptabilité qui déclare et paie CNSS/AMO/IR. Noyau gelé (paie-bulletins `df7ff12`), contrôle d'intégrité bloquant, tests golden inchangés, recalcul de vérification à la migration. Règle R0 de tous les prompts** | **DÉCISION VALIDÉE — point crucial** |
| D9 | Conception v2 | Validée, y compris Q1 = A (montants du plan saisis par salarié) et Q2 = une échéance CNSS par salarié avec un total affiché | DÉCISION VALIDÉE |

## 1. La chaîne fonctionnelle

```
Fiche salarié (id unique + matricule + plan de versement)
        │
        ▼
Déclaration du mois M ──► Trésorerie : 4 échéances par salarié actif
        │                  (10 : 1er versement + CNSS · 20 : 2e · 30/fin : 3e)
        │                        │ virement saisi (date) → statut calculé à temps / retard / avance
        ▼                        ▼
Paie du mois M : saisie → calcul ──► rapprochement « versé / net à payer », « CNSS versée / cotisations »
        │                                    (information + avertissement à la clôture, jamais bloquant)
        ▼
Clôture → bulletin PDF archivé (SHA-256) → cumuls figés → exports
```

- **Trésorerie (ex-ezzinecdi)** : constitue et suit les fonds versés au salarié (salaire en 3 versements) et à la CNSS.
- **Paie (ex-paie-bulletins)** : produit le bulletin du salaire perçu, avec ses règles inchangées.
- Fait vérifié dans les deux dépôts : pour le salarié de démonstration, la somme des 3 versements (7 000) égale le net à payer (7 000,00), et la CNSS du plan (1 500) est proche des cotisations salariales + patronales (1 513,00).

## 2. Plusieurs salariés sans conflit

| Règle | Contenu |
|---|---|
| Identifiant | `employee_id` : entier interne, unique, jamais réutilisé, référencé partout. `matricule` : identifiant visible, unique |
| Clés d'unicité | Bulletin : (employee_id, année, mois, version). Échéance : (employee_id, année, mois, type). Plan : (employee_id, date d'effet) |
| Fixe, commun à tous | Paramètres de paie (taux, plafonds, barème IR, frais pro, méthode des totaux), versionnés par date d'effet comme aujourd'hui. Gabarit d'échéancier : 4 types, jours 10/10/20/30-ou-fin, rappel J-1, règles de régularité |
| Propre à chaque salarié | Fiche, saisie mensuelle, **montants** du plan de versement (versionnés par date d'effet : un changement ne touche jamais les échéances déjà déclarées) |
| Déclarer un mois | Génère les échéances de tous les salariés actifs sur ce mois (embauche ≤ fin du mois, sortie ≥ début du mois). Les échéances existantes sont ignorées (anti-doublon par salarié). Option : un seul salarié |
| Contrôle d'import | `montant == plan(salarié, type, date)` (au lieu de `== barème(type)`) ; `mois == mois(date)` inchangé |

## 3. Rapprochement entre trésorerie et paie (nouveau, non bloquant)

Il est calculé pour chaque salarié et chaque mois. Il est affiché sur le tableau de bord, la paie du mois et la fiche salarié.

- Versé au salarié = somme des versements de salaire payés. Comparé au net à payer du bulletin (aperçu ou clôturé).
- CNSS versée comparée aux cotisations salariales + patronales du bulletin, à titre d'information.
- À la clôture : un écart ou des versements incomplets ajoutent un **avertissement confirmable**. Ce mécanisme existe déjà dans paie-bulletins (`confirm_warnings`).
- Le rapprochement ne modifie jamais un calcul ni un statut.

## 4. Reprise des données existantes

| Source | Récupération | À noter |
|---|---|---|
| paie-bulletins | Fichier de sauvegarde `.db` téléchargé depuis « Sauvegardes et administration » de l'app Streamlit | Le disque de Streamlit Cloud est éphémère : **faire cette sauvegarde dès maintenant** |
| ezzinecdi | `data.json` (et `backup_*.json`) du dossier Google Drive | Ne pas utiliser l'export Excel : il ne contient pas `date_paiement` |

Principes :

1. **Originaux gelés** : copies conservées avec leur empreinte SHA-256. Les apps Streamlit passent en lecture seule pendant la bascule.
2. **Import à l'identique** : paies clôturées, versions remplacées, PDF (octets et empreinte), versions de paramètres, copies figées JSON et journal sont recopiés tels quels, sans recalcul ni réécriture. Les numéros des bulletins (`bulletin_AAAA-MM_0001.pdf`, `_v2`) sont conservés.
3. **Rattachement** : toutes les échéances ezzinecdi sont rattachées au salarié concerné (matricule à confirmer). Le plan v1 de ce salarié reçoit les montants actuels (2 500 / 1 500 / 2 500 / 2 000). L'ancien `n` est conservé (`source_ref`).
4. **Contrôles avant mise en service** :
   - nombre de lignes par table ;
   - totaux par mois (brut, net, cotisations, versé) ;
   - empreintes des PDF recalculées = empreintes stockées ;
   - recalcul de vérification des bulletins en lecture seule (écart signalé, jamais corrigé) ;
   - `reconcile()` ezzinecdi en simulation : toute correction qu'il ferait est listée et soumise, jamais appliquée d'office.
5. **Retour arrière** : l'import se fait dans la base `paie`, neuve et vide. Annuler revient à la vider, rien d'autre n'est touché.
6. **Validation** : un rapport de migration est remis au propriétaire, qui valide avant la mise en service. Les deux apps Streamlit restent consultables pendant la recette.

## 5. Interface

### Principes
1. **6 entrées de menu** au lieu des 13 écrans cumulés des deux apps.
2. **Barre de contexte unique** : période (‹ Novembre 2026 ›) et recherche d'un salarié, partagées par tous les écrans. On ne ressaisit jamais le mois.
3. **Une action principale par écran** (bouton plein). Les confirmations (payer, clôturer, rectifier, dévalider, restaurer) passent par un dialogue.
4. **Un code couleur de statut** commun aux deux modules : gris = brouillon / non payé ; bleu = calculée ; vert = clôturée / payé à temps ; orange = payé en retard ; rouge = échu non payé ; pointillé = à saisir / à venir.
5. **Détail dans un panneau latéral** plutôt qu'une page de plus. Les tableaux défilent horizontalement sur petit écran.
6. CIN, CNSS et RIB masqués par défaut. Le rôle `user` ne voit pas les boutons d'écriture.
7. **La trésorerie se pilote au téléphone** (cartes, bouton Payer de 44 px) ; la paie est optimisée pour l'ordinateur.

### Menu et correspondance avec les écrans d'origine

| Menu | Contenu | Écrans d'origine repris |
|---|---|---|
| Tableau de bord | Indicateurs du mois, suivi par salarié (échéances, versé/net, bulletin), à traiter, prochaines échéances | paie : Tableau de bord · ezzinecdi : Diagnostic |
| Trésorerie | Onglets À venir · Mois · Rappels J-1 (ICS) · Récap & export (2 Excel + ICS) ; Déclarer un mois ; Régularisation ; Payer / Dévalider | ezzinecdi : les 4 panneaux et la barre latérale |
| Paie du mois | Liste des salariés du mois et leur statut ; panneau Saisie → Calcul → Contrôles → Clôture ; aperçu instantané ; PDF provisoire ; Rectifier | paie : Saisie mensuelle, Calcul et validation |
| Salariés | Liste, recherche, activation ; fiche à onglets Identité · Plan de versement · Bulletins · Virements · Cumuls | paie : Salariés · nouveau : plan de versement |
| Bulletins & exports | Archives PDF (versions), livre de paie, récap mensuel/annuel, CSV/Excel expurgés | paie : Bulletins et archives, Récapitulatifs et exports |
| Configuration | Entreprise · Paramètres de paie (versions) · Gabarit d'échéancier (lecture seule) · Utilisateurs · Sauvegardes · Journal | paie : Entreprise, Paramètres, Sauvegardes et administration · ezzinecdi : auth |

## 6. Architecture (rappel, inchangée sur le fond)

1 conteneur (FastAPI + SPA Vue 3, stack SmartCompta) sur `paie.hbnfactory.cloud`, derrière Traefik, sans port exposé, limite 512 Mo. La base `paie` est sur le serveur MySQL existant. Les modules `paie/` et `tresorerie/` sont séparés dans le code ; le socle (auth, journal, sauvegarde) est commun. Le moteur et le PDF de paie-bulletins sont repris sans modification de logique, et les tests d'origine servent de critère d'acceptation.

## 7. Points encore ouverts (traités en S0)

| # | Question | Statut |
|---|---|---|
| Q1 | Montants du plan | **Tranché : A**, saisis par salarié |
| Q2 | CNSS | **Tranché** : une échéance par salarié, avec un total affiché |
| Q3 | Matricule du salarié d'ezzinecdi ; données réelles ou démonstration dans paie-bulletins | À CONFIRMER, S0 / US-05 |
| Q4 | Emplacement du serveur MySQL et connexion depuis le VPS | À CONFIRMER, S0 / US-02 (test avant tout code) |

Note de stockage (conséquence de D8) : les valeurs de calcul ne sont jamais stockées dans des colonnes qui arrondissent. Saisies, résultats, cumuls et paramètres sont gardés en texte décimal exact (JSON texte), comme dans l'original. Cela remplace la mention `DECIMAL(14,2)` de la v1.
