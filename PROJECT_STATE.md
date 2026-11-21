# HBN Paie — état du projet

| Champ | Valeur |
|---|---|
| Sprint courant | S0 — cadrage **terminé** (US-02, US-05 bloquées en attente du propriétaire) — tag `sprint-S0` |
| Prochaine action autorisée | Aucune avant les réponses Q1–Q5 de `docs/sprints/S0_RAPPORT.md` et le « go S1 » |

## Décisions validées
- Conception v2.1 (D1–D9), `docs/reference/PAIE_FUSION_CONCEPTION.md` ; cadre R0–R9, `docs/claude-code/00_CADRE_COMMUN.md`.

## Faits vérifiés (21/11/2026)
- DNS `paie.hbnfactory.cloud` → 2.25.6.153 = IP du VPS (local, 1.1.1.1, 8.8.8.8).
- VPS : 3,8 Gio RAM (2,0 disponibles), 1 vCPU, 23 Go libres. Traefik v3.7.19 : résolveur `le`, middleware `hbn-secure-headers@file`, réseau `hbn-proxy`.
- MySQL WordPress = conteneur `hbn-portfolio-db-1` (mysql 8.4.13), réseau `portfolio-internal` seul, aucun port publié.
- Sources gelées : paie-bulletins `df7ff126…` (78 fichiers), ezzinecdi `85354c9c…` (11 fichiers) ; `upstream/MANIFEST.sha256` = `dabd124c…148d`.
- Référence R0.3 (Python 3.14.4) : paie-bulletins 238 passés + 1 ignoré (Excel absent) ; ezzinecdi 9 passés ; golden 6 scénarios.
- Dossiers VPS : `/opt/hbnfactory/platforms/paie/` (0750), `migration/sources/` (0700).

## À confirmer
- Q1 MySQL (A : conteneur portfolio / B : MySQL dédié) et dépôt du compte admin.
- Q2 accès GitHub pour créer/pousser `zaklearn/hbn-paie`.
- Q3 Python 3.12 via `hbn-paie-dev` en S1.
- Q4 fichiers sources + matricule (US-05).
- Q5 documents PAIE_DIAG_1/2/3.
- Alerte : secrets et données publics dans `zaklearn/ezzinecdi` (rotation recommandée).
