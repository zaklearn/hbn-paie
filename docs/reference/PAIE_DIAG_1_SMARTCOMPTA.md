# Diagnostic 1/3 — SmartCompta v6.6 (archive `smartcompta-v4.zip`)

Date : 21/11/2026 · Source : archive fournie (686 fichiers, 17 Mo). Rôle dans la fusion : **stack et conventions de référence** (pas la source fonctionnelle de la paie).

## 1. Organisation

```
smartcompta-v4/
├── Dockerfile                  multi-stage : build Vue (node:20) → FastAPI + SPA statique (python:3.12-slim)
├── smartcompta-v6-backend/     FastAPI
│   ├── main.py                 montage des routers, /health, SPA statique
│   ├── app/api/                routers (auth, clients, extract, compliance, demarches, whatsapp, finops…)
│   │   └── endpoints/payroll.py   routes paie, préfixe /api/payroll
│   ├── app/payroll_module/     moteur paie « Maroc-Pay-2026 » autonome (engine, schemas, params.json)
│   ├── app/services/payroll_export/  PDF (Jinja2 + xhtml2pdf), Excel, Word, nommage bulletins
│   ├── app/db/                 SQLAlchemy 2 (engine, models, *_schema_sync.py), auth MySQL
│   ├── sql_migrations/         001…006 (SQL manuel ; alembic listé mais non utilisé)
│   └── tests/                  pytest (dont tests/payroll/)
└── smartcompta-v6-frontend/    Vue 3 + Vite 6 + TS + Pinia + Tailwind 3 + axios + lucide
    ├── src/views/payroll/      composants paie (SalaryInput, ExemptionAccordion, ResultsDashboard, PayrollTable,
    │                           BulletinIdentityBlock, ExportActions, SettingsModal, HistoryModal, EmployerListTable…)
    ├── src/views/simulator/Payroll.vue   page simulateur (739 l.)
    └── src/stores/*.ts, src/shared/services/http.ts, src/router/
```

## 2. Stack (fait vérifié)

| Couche | Technologie |
|---|---|
| Backend | Python 3.12, FastAPI 0.115, Pydantic 2.9, Uvicorn (2 workers) |
| ORM / DB | SQLAlchemy ≥ 2.0.25 + PyMySQL, MySQL/MariaDB, `pool_pre_ping`, `pool_recycle=3600` |
| Docs générés | ReportLab 4.1, xhtml2pdf + Jinja2, openpyxl, python-docx, pandas |
| Frontend | Vue 3.5, Vite 6, TypeScript 5.3, Pinia 2, vue-router 4, Tailwind 3.4, axios |
| Déploiement | Image unique multi-stage, SPA servie par FastAPI, HEALTHCHECK `curl /health`, port 8000 |

## 3. Module paie existant (fonctionnalités)

- `POST /api/payroll/calculate` : calcul d'un bulletin (Decimal, arrondi 2 déc.) — brut → exonérations BO 3744 (transport ≤ 500, panier 30/j si ≥ 6 h, représentation ≤ 10 %, déplacement intégral) → SBI → CNSS/AMO/IPE plafonnés → SNI → frais pro 25 % plafond 2 500 → RNI → IGR barème **mensuel** LF 2026 → réduction charges de famille 30/pers. plafond 180 → net.
- `GET/PATCH/PUT /api/payroll/settings` : paramètres dans `params.json` (fichier, pas en base).
- `POST /export/pdf|excel`, modèle de formulaire de déplacement.
- Archives : table `payroll_archives` (employeur = `clients.id`, salarié = **nom en texte**, résultat JSON), historique, analytics, ZIP mensuel, suppression.

## 4. Points d'attention pour la fusion

1. **Deux moteurs de paie différents.** Celui de SmartCompta (barème IGR mensuel, plafond 37 %, frais pro 25 %/2 500) **n'est pas** celui de paie-bulletins (barème IR annuel, plafond 38 %, frais pro 35 %/25 % selon seuil 78 000, net arrondi au dirham). Ils donnent des résultats différents : on ne les mélange pas. La fusion reprend le moteur paie-bulletins (spécification exacte demandée).
2. **Conventions à reprendre** : structure `app/api | services | db | core`, config Pydantic Settings, logs, HEALTHCHECK, image multi-stage, stores Pinia, client HTTP unique.
3. **Conventions à ne pas reprendre** : mots de passe en SHA-256 salé et comptes par défaut `admin/admin123` créés au démarrage ; `BASE_PATH=/smartcompta/` et origine `datavizir.site` en dur ; schéma synchronisé par scripts maison au lieu de migrations versionnées.
4. **Hygiène de l'archive** : elle contient des `.env`, des clés de compte de service Google, `users.json`/`tokens.json`, des logs, `dist/` et `.pytest_cache`. Ces fichiers ne doivent pas être copiés dans le nouveau dépôt. Il faudra faire tourner les clés Google si l'archive a circulé.

## 5. Déploiement constaté

Image unique, Uvicorn sur :8000, `/smartcompta/` derrière l'ancien Nginx (VPS perdu). Pas de compose dans l'archive. À adapter à Traefik (`hbn-proxy`, `le`, `hbn-secure-headers@file`).
