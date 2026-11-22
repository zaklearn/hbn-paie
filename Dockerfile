# syntax=docker/dockerfile:1
# =============================================================================
# HBN Paie — image unique multi-stage (S6 / US-60), modèle SmartCompta :
#   1. front   : build de la SPA Vue (node:20-alpine)
#   2. verify  : test BLOQUANT d'intégrité du noyau paie gelé (R0) — échec = image refusée
#   3. runtime : FastAPI + SPA statique (python:3.12-slim), utilisateur non root, 1 worker Uvicorn
# upstream/, docs/, données et secrets exclus du contexte (.dockerignore).
# =============================================================================
ARG NODE_IMAGE=node:20-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293
ARG PYTHON_IMAGE=python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b

FROM ${NODE_IMAGE} AS front
WORKDIR /front
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund --loglevel=error
COPY frontend/ ./
RUN npx vue-tsc --noEmit && npx vite build

FROM ${PYTHON_IMAGE} AS verify
ENV PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 PIP_ROOT_USER_ACTION=ignore
COPY backend/requirements.txt backend/requirements-dev.txt /req/
RUN pip install -r /req/requirements-dev.txt
COPY backend/ /app/backend/
COPY scripts/check_core_integrity.py /app/scripts/
WORKDIR /app/backend
# R0.1 : le noyau embarqué est identique au commit gelé paie-bulletins@df7ff12.
RUN python -m pytest -q -p no:cacheprovider tests/test_core_integrity.py && touch /tmp/r0-integrite-ok

FROM ${PYTHON_IMAGE} AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore PAIE_STATIC_DIR=/app/static PAIE_BACKUP_DIR=/app/data/backups
RUN groupadd --system --gid 10001 paie && useradd --system --uid 10001 --gid paie --home-dir /app paie
COPY backend/requirements.txt /req/requirements.txt
RUN pip install -r /req/requirements.txt
COPY --from=verify /tmp/r0-integrite-ok /app/R0-INTEGRITE-OK
COPY backend/app /app/backend/app
COPY backend/alembic /app/backend/alembic
COPY backend/alembic.ini /app/backend/alembic.ini
COPY scripts/check_core_integrity.py scripts/migrate_paie_bulletins.py scripts/migrate_ezzinecdi.py scripts/paie-backup scripts/paie-restore /app/scripts/
COPY --from=front /front/dist /app/static
RUN mkdir -p /app/data/backups /app/data/logs && chown -R paie:paie /app/data
USER paie
WORKDIR /app/backend
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"]
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
