# HBN Paie — image de mesure de la référence (Q3) : suites d'origine sous Python 3.12,
# dépendances contraintes aux versions de la mesure S0 (docs/sprints/S0_reference_env.txt).
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
COPY --from=upstream paie-bulletins@df7ff126fdbb3d3c0a509480507361eec6b2b842/requirements.txt paie-bulletins@df7ff126fdbb3d3c0a509480507361eec6b2b842/requirements-dev.txt /req/paie/
COPY --from=upstream ezzinecdi@85354c9c1f1d79d71d215f75dc8131186bafc054/requirements.txt /req/ezz/requirements.txt
COPY ref-constraints-py314.txt /req/constraints.txt
RUN cd /req/paie && pip install -c /req/constraints.txt -r requirements-dev.txt \
 && pip install -c /req/constraints.txt -r /req/ezz/requirements.txt \
 && pip freeze > /req/freeze-py312.txt
