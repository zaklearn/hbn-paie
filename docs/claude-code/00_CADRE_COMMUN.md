# HBN Paie — Cadre commun Claude Code (à lire au début de CHAQUE sprint)

Version 1.0 · 21/11/2026 · Propriétaire : Zak · Rédaction : Claude Chat
Références (projet Claude « hbn factory vps 2026 ») : `PAIE_FUSION_CONCEPTION.md` (v2, validée le 21/11/2026), `PAIE_DIAG_1/2/3_*.md`, maquettes « HBN Paie — maquettes de l'application ».

---

## R0 — RÈGLE CRUCIALE : LES FORMULES DE PAIE SONT INTOUCHABLES

Les bulletins doivent rester identiques au centime aux calculs de la comptabilité. C'est elle qui sert aux déclarations et aux paiements CNSS / AMO / IR. Le moindre écart de formule, d'arrondi ou d'ordre de calcul crée un écart entre les déclarations et les bulletins. **Ce point n'est jamais négociable, même pour « simplifier », « corriger » ou « harmoniser ».**

### R0.1 — Noyau gelé
Les fichiers suivants de `zaklearn/paie-bulletins` au commit **`df7ff126fdbb3d3c0a509480507361eec6b2b842`** sont copiés tels quels dans `backend/app/paie/core/` :

```
src/calculations/money.py      src/calculations/engine.py     src/calculations/cumuls.py
src/calculations/defaults.py   src/models/parameters.py       src/models/payroll.py
src/models/entities.py         src/validation/validators.py   src/pdf/bulletin.py
src/formatting.py
```

- **Seule modification autorisée** : le préfixe d'import `from src.` → `from app.paie.core.`. Rien d'autre : pas de reformatage, pas de renommage, pas de typage ajouté, pas de « nettoyage ».
- `scripts/check_core_integrity.py` normalise ce préfixe, calcule le SHA-256 de chaque fichier et le compare à `backend/app/paie/core/UPSTREAM.sha256`, généré depuis le commit gelé. Ce contrôle est un test pytest **bloquant**, et il tourne à chaque commit.
- Un fichier du noyau doit évoluer ? **STOP** : demander au propriétaire, qui décide. Ne jamais contourner, par exemple en dupliquant une fonction ailleurs.

### R0.2 — Interdits
- Utiliser, importer ou s'inspirer du moteur paie de SmartCompta (`app/payroll_module/`, `params.json`, barème IGR mensuel). Il calcule **différemment**.
- Recalculer une rubrique ailleurs que dans le noyau, et notamment en JavaScript dans le frontend. L'aperçu instantané appelle l'API, qui appelle le noyau.
- Remplacer `Decimal` par `float`, ou modifier `excel_round` (demi vers l'extérieur), l'ordre des arrondis, la méthode des totaux par défaut (`somme_lignes`) ou les valeurs de `defaults.py`.
- Mettre à jour d'initiative des taux ou un barème (« LF 2026 » ou autre). Les paramètres ne changent que par une **nouvelle version datée saisie par le propriétaire**, jamais rétroactive.
- Stocker un montant ou un taux de calcul dans une colonne qui arrondit (`DECIMAL(14,2)`, `FLOAT`, `DOUBLE`). Certaines valeurs intermédiaires ne sont pas arrondies (RBI, IR annuel). Saisies, résultats, cumuls et paramètres sont stockés comme dans l'original : **texte décimal exact** (chaînes JSON) via les `to_dict` / `from_dict` du noyau.
- Faire influencer un calcul par la trésorerie. Le rapprochement « versé / net » et « CNSS versée / cotisations » est un **affichage en lecture seule** plus un avertissement confirmable à la clôture. Il ne modifie jamais une saisie, un résultat, un paramètre ni un statut de paie.

### R0.3 — Preuves exigées
- Les tests d'origine du moteur, des écarts PDF, du PDF et de non-régression (`tests/golden/results.json`) passent **sans modifier une seule valeur attendue**.
- Si le propriétaire fournit le classeur `paie_exemple_EXEMPLE_SARL.xlsx`, `test_reference_excel.py` doit passer (`PAIE_REFERENCE_XLSX`).
- Migration : chaque paie clôturée importée est recalculée en lecture seule par le noyau, et le résultat doit être **identique chaîne par chaîne** au résultat stocké. Tout écart est signalé, jamais corrigé.
- Chaque rapport de sprint contient une ligne « R0 : intégrité du noyau OK (n fichiers), golden OK (n cas) ».

---

## R1 à R9 — Autres règles

| # | Règle |
|---|---|
| R1 | Les logiques ezzinecdi (commit `85354c9c1f1d79d71d215f75dc8131186bafc054`) sont reprises à l'identique : génération des échéances, régularité au jour, statuts, réconciliation, Excel 8 colonnes, ICS. Seule extension validée : le passage à plusieurs salariés (`employee_id` + plan de versement par salarié, cf. conception §2) |
| R2 | Aucune fonctionnalité perdue : chaque ligne des tableaux « Fonctionnalités » de PAIE_DIAG_2 et PAIE_DIAG_3 a son équivalent, vérifié en recette (S6) |
| R3 | Base `paie` dédiée, utilisateur MySQL dédié, aucune requête vers les tables WordPress |
| R4 | Secrets uniquement dans `.env` (0600, hors Git), jamais affichés dans un log, un rapport ou la conversation |
| R5 | Aucune commande destructive (`DROP`, `down -v`, `rm -rf`, `TRUNCATE`, restauration) sans autorisation explicite du sprint ou du propriétaire |
| R6 | Ne rien toucher sur le VPS hors de `/opt/hbnfactory/platforms/paie/`. Traefik, Tangerine et le portfolio ne sont pas modifiés. Pas de second reverse proxy |
| R7 | Ne rien copier de l'archive SmartCompta qui contienne des secrets (`.env`, `config/*.json`, `data/*.json`, logs, `dist/`) ; reprendre uniquement des conventions de code |
| R8 | Interface conforme aux maquettes : 6 entrées de menu, barre de contexte période + salarié, une action principale par écran, code couleur commun, données sensibles masquées |
| R9 | Doute, contradiction ou information manquante → STOP et question au propriétaire. Ne jamais inventer |

## Niveaux d'autorisation

| Niveau | Contenu | Dans ce projet |
|---|---|---|
| L0 | Lecture, diagnostic | Toujours autorisé |
| L1 | Écriture dans le dépôt `hbn-paie` et dans un environnement de dev local (MySQL de test en conteneur) | Autorisé dans le périmètre du sprint |
| L2 | Création de fichiers sous `/opt/hbnfactory/platforms/paie/` sur le VPS | Seulement si le sprint le dit |
| L3 | Création de la base de production, conteneur en production, import des données réelles, mise en service | **Validation explicite du propriétaire au moment de l'exécuter** |

## Suivi Scrum (fichiers à la racine du dépôt)

- `PROJECT_STATE.md` : état courant (sprint, décisions, faits vérifiés, points à confirmer, prochaine action autorisée). Mis à jour en fin de sprint, sans réécrire l'historique.
- `BACKLOG.md` : copie de `01_BACKLOG.md`. Statut des stories : `À faire` / `En cours` / `Fait` / `Bloqué (raison)`.
- `CHANGELOG.md` : une entrée par sprint.
- `docs/sprints/S<n>_RAPPORT.md` : rapport court (1 page). Ce qui est fait, preuves (tests, commandes), ligne R0, écarts, questions.
- Un commit par story (`S2/US-21: …`). La fin de sprint est taguée `sprint-S<n>`.
- Catégories d'information : FAIT VÉRIFIÉ, DÉCISION VALIDÉE, HYPOTHÈSE, À CONFIRMER, ACTION EXÉCUTÉE, ACTION REPORTÉE.

## Fin de sprint = point d'arrêt
Arrêter après le rapport. Ne jamais enchaîner sur le sprint suivant sans le « go » du propriétaire.

## Stack cible (rappel)
Backend Python 3.12, FastAPI, Pydantic 2, SQLAlchemy 2 + PyMySQL, Alembic, ReportLab, openpyxl, pandas. Frontend Vue 3 + Vite + TypeScript + Pinia + vue-router + Tailwind + axios. Image Docker unique multi-stage, 1 worker Uvicorn, servie à la racine de `paie.hbnfactory.cloud` derrière Traefik.
