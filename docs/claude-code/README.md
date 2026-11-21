# Pack Claude Code — HBN Paie (v1.0, 21/11/2026)

## Mode d'emploi
1. Donne à Claude Code le dossier complet et le prompt `S0_CADRAGE.md`. En S0, il copie ce pack dans `docs/claude-code/` du dépôt.
2. À la fin de chaque sprint, Claude Code s'arrête et rédige `docs/sprints/S<n>_RAPPORT.md`.
3. Relis le rapport (vérifie la ligne **R0** en premier), réponds à ses questions, puis donne le prompt du sprint suivant.
4. Les étapes **L3** de S6 (base de production, conteneur, données réelles) demandent ton accord explicite au moment de les exécuter.

| Fichier | Rôle |
|---|---|
| `00_CADRE_COMMUN.md` | Règles invariantes, **R0 : formules de paie intouchables**, niveaux d'autorisation, suivi |
| `01_BACKLOG.md` | Epics et user stories (US-01 à US-64) |
| `S0_CADRAGE.md` | Vérifications DNS / MySQL, dépôt, sources gelées, référence de tests, inventaire des données |
| `S1_SOCLE_NOYAU.md` | Socle FastAPI, noyau paie gelé + contrôle d'intégrité |
| `S2_PAIE_MYSQL.md` | Module Paie sur MySQL, procédure, comptes, API |
| `S3_TRESORERIE.md` | Trésorerie multi-salariés, plans de versement, rapprochement en lecture seule |
| `S4_INTERFACE.md` | Interface Vue 3 conforme aux maquettes |
| `S5_EXPLOITATION_MIGRATION.md` | Sauvegarde / restauration, outils de migration, dry-run |
| `S6_DEPLOIEMENT.md` | Docker + Traefik, base de production, import réel, recette, mise en service |

## À préparer de ton côté
- La sauvegarde `.db` de paie-bulletins, **dès maintenant** (le disque de Streamlit Cloud est éphémère).
- Le `data.json` d'ezzinecdi (Google Drive) et le matricule du salarié concerné.
- Le classeur `paie_exemple_EXEMPLE_SARL.xlsx` : il permet le test de conformité cellule par cellule.
- L'emplacement du serveur MySQL et un compte d'administration, à déposer dans un fichier 0600 (S0).
