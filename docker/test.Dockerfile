# HBN Paie — image de tests de DEV (Python 3.12), dépendances figées de backend/.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1 PIP_ROOT_USER_ACTION=ignore
COPY requirements.txt requirements-dev.txt /req/
RUN pip install -r /req/requirements-dev.txt
WORKDIR /work/backend
