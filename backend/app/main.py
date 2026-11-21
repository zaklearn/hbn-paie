"""Point d'entrée FastAPI de HBN Paie."""

from __future__ import annotations

import logging

from fastapi import FastAPI

from app import __version__
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.logging import setup_logging

log = logging.getLogger("hbn_paie")


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)
    app = FastAPI(title="HBN Paie", version=__version__, docs_url=None, redoc_url=None)
    install_error_handlers(app)

    @app.get("/health", include_in_schema=False)
    def health() -> dict:
        """Vivacité du processus (healthcheck Docker) : ne dépend pas de la base."""
        return {"status": "ok"}

    @app.get("/api/health")
    def api_health() -> dict:
        """État de l'application et de la base (si configurée)."""
        db = "non_configuree"
        if settings.db_url is not None:
            from app.db.engine import ping

            try:
                db = "ok" if ping() else "erreur"
            except Exception:  # noqa: BLE001 — l'état est rapporté, jamais le détail (secrets)
                log.warning("base injoignable")
                db = "injoignable"
        return {"status": "ok", "version": __version__, "db": db}

    return app


app = create_app()
