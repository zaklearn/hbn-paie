# S6 — Rapport : déploiement, reprise réelle et mise en service (22/11/2026)

**R0 : intégrité du noyau OK (10 fichiers), vérifiée au build de l'image. L'image est refusée si le noyau est altéré (démontré). R0.3 en production : 4 paies clôturées recalculées, 0 écart chaîne par chaîne.**
- Bulletins de production : **texte identique aux 4 PDF d'origine** (hors « Paie clôturée le … » et « édité le … »).
- L'import recopie les données, sans recalcul.

## Opérations
| Heure (UTC) | Étape | Niveau | Opération | Résultat |
|---|---|---|---|---|
| 20:5x | A | L2 | Build `hbn-paie:cc896555c9d7` (multi-stage : SPA, test d'intégrité bloquant, runtime non root) | OK, 521 Mo ; build volontairement altéré → refusé |
| 20:55 | A | L2 | `/opt/hbnfactory/platforms/paie/` : `compose.yaml`, `.env` 0600 (`gen-env.sh`), `data/{mysql,backups,logs}` | `docker compose config -q` OK |
| 20:58 | B | **L3** | `up -d paie-db` | Sain en 15 s, 217 Mio |
| 20:59 | B | **L3** | Migrations Alembic (`paie_app`) | Base `paie` créée (utf8mb4 / unicode_ci), `paie_app` limité à `paie.*`, révision 0004 ; 12 tables, 7 déclencheurs, 23 index d'unicité conformes |
| 21:01 | C | **L3** | Route activée, `up -d paie` | Sain en 9 s ; contrôles ci-dessous |
| 21:0x | C | **L3** | Premier superadmin (CLI, mot de passe saisi par le propriétaire) | `zak` (1re saisie non concordante, rien créé ; 2e OK) |
| 21:11 | D | **L3** | Sauvegarde de la base vide | `paie_20261122_211153_…_base_vide_avant_import.zip` |
| 21:11 | D | **L3** | Copies des sources (SHA-256 identiques aux originaux) | `migration/import-20261122/` |
| 21:11 | D | **L3** | Import paie-bulletins (.db du 27/10) | 1 entreprise, 1 salarié, 1 version de paramètres, 3 paies, journal ; 0 écart |
| 21:12 | D | **L3** | Import trésorerie (data.json reconstitué sur déclaration) | Plan v1, 20 échéances (19 payées), 0 correction, 0 rejet |
| 21:12 | D | **L3** | Reprise (décision du 22/11) : juillet clôturé ; août et septembre recalculés puis clôturés ; octobre créé et clôturé | 4 paies clôturées, net 7 000 ; texte identique aux PDF d'origine 4/4 |
| 21:13 | E | L2 | Sauvegarde de production, puis restauration sur le MySQL de dev | `…_apres_import_production.zip` : tables identiques, protections recréées, 4 PDF intacts |

**Détails des contrôles de l'étape C.**
- `http://` renvoie 301 et `https://` renvoie 200.
- Certificat Let's Encrypt de production pour `paie.hbnfactory.cloud`, valable jusqu'au 20/02/2027.
- En-têtes HSTS, `nosniff`, `DENY` et `Referrer-Policy` présents.
- API protégée (401) et SPA servie.
- Ports de l'hôte inchangés ; Tangerine et portfolio en 200 avant et après ; `portfolio-internal` inchangé.

**Rapports de migration** (hors dépôt, matricule masqué, 0600) : `/opt/hbnfactory/platforms/paie/migration/rapports/S5_MIGRATION_DRYRUN_REEL.md` et `S6_MIGRATION_PRODUCTION.md`. Leurs résultats sont identiques : 4 paies, 4 bulletins, 20 échéances, 0 correction, R0.3 0 écart.

## Mesures
| Mesure | Valeur |
|---|---|
| Mémoire au repos | `paie` 107 Mio / 512 ; `paie-db` 216 Mio / 384 (aucun OOM, 0 redémarrage) |
| Génération d'un bulletin PDF | 12 ms (moyenne sur 5) |
| Temps de réponse | `/` 83 ms ; `/api/health` 17 ms |
| Disque | base 208 Mo ; sauvegarde complète 33 Ko ; 15 Go libres sur `/` |
| Mémoire du VPS | 1,6 Go disponibles après mise en service |

## Mise en service
**v1.0.0 — recette validée par le propriétaire le 22/11/2026.** Definition of Done atteinte : service en HTTPS, données réelles importées avec R0.3 à 0 écart, recette signée, sauvegarde de production testée, aucun impact sur Tangerine ni le portfolio.

## (Historique) Restant à faire avant la recette
1. **Recette par le propriétaire :** checklist R2 dans `docs/sprints/S6_RECETTE.md`, à signer. Le tag `v1.0.0` sera posé ensuite.
2. **Bascule (US-64) :**
   - fait : applications Streamlit gelées par le propriétaire ;
   - à faire : `HBN_PAIE_PROJECT_STATE.md` (état HBNFACTORY), en place.

## Écarts et points d'attention
1. **Journal binaire MySQL désactivé** (`--disable-log-bin`). Il n'y a ni réplication ni restauration à un instant donné : les sauvegardes sont applicatives. Cela permet à `paie_app` de créer les déclencheurs sans privilège SUPER. **À valider.**
2. **`root@%` présent dans `paie-db`** (comportement de l'image officielle). Il n'est joignable que depuis `paie-internal`, où se trouve le seul conteneur `paie`. Une restriction à `localhost` est possible (L3). **À décider.**
3. **Reprise de la paie (décision du 22/11) :**
   - les clôtures sont datées du 22/11/2026 et tracées sous l'acteur « reprise » ;
   - les PDF d'origine du 06/11 sont archivés dans `migration/sources/reference/` (SHA256SUMS).
4. **Trésorerie reconstituée sur déclaration :** dates de paiement = dates d'échéance (« Payé – à temps »), avec la mention « reconstitué… » dans les observations.
5. **Requêtes `HEAD` :** une requête `HEAD` sur `/` renvoie une réponse JSON, car la SPA ne répond qu'au `GET`. Sans effet sur les navigateurs ; à corriger si une sonde l'utilise.
6. **Cron Hostinger** `image prune -af --filter until=24h` : l'image en service est protégée, mais les images de dev pourront être supprimées (sans conséquence, elles se reconstruisent).
