"""Point d'entrée FastAPI de HBN Paie."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app import __version__
from app.api.serialize import issues_out
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.logging import setup_logging
from app.paie.repositories.db import Database, IntegrityError
from app.paie.services import demo, master_data
from app.paie.services.errors import PayrollError, ValidationFailed

log = logging.getLogger("hbn_paie")


def bootstrap(db: Database, *, migrate: bool, seed_demo: bool) -> None:
    """Démarrage, comme l'original (src/ui/common.py) : migrations, paramètres initiaux, démo facultative."""
    if migrate:
        db.migrate()
    master_data.ensure_initial_parameters(db)
    if seed_demo:
        demo.seed_demo(db)


def create_app(database: Database | None = None) -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)
    if database is None and settings.db_url is not None:
        database = Database(settings.db_url.get_secret_value())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if app.state.db is not None:
            bootstrap(app.state.db, migrate=settings.auto_migrate, seed_demo=settings.seed_demo)
        yield

    app = FastAPI(title="HBN Paie", version=__version__, docs_url=None, redoc_url=None, lifespan=lifespan)
    app.state.db = database
    install_error_handlers(app)

    @app.exception_handler(ValidationFailed)
    async def _validation_failed(_: Request, exc: ValidationFailed) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc), "issues": issues_out(exc.issues)})

    @app.exception_handler(PayrollError)
    async def _payroll_error(_: Request, exc: PayrollError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(IntegrityError)
    async def _integrity_error(_: Request, exc: IntegrityError) -> JSONResponse:
        log.warning("violation d'intégrité refusée par la base")
        return JSONResponse(status_code=409, content={"detail": "Opération refusée par une règle d'intégrité de la base."})

    @app.get("/health", include_in_schema=False)
    def health() -> dict:
        """Vivacité du processus (healthcheck Docker) : ne dépend pas de la base."""
        return {"status": "ok"}

    @app.get("/api/health")
    def api_health() -> dict:
        """État de l'application et de la base (si configurée)."""
        db_state = "non_configuree"
        if app.state.db is not None:
            try:
                with app.state.db.read() as conn:
                    db_state = "ok" if conn.execute("SELECT 1 AS ok").fetchone()["ok"] == 1 else "erreur"
            except Exception:  # noqa: BLE001 — l'état est rapporté, jamais le détail (secrets)
                log.warning("base injoignable")
                db_state = "injoignable"
        return {"status": "ok", "version": __version__, "db": db_state}

    from app.api import routes_paie, routes_socle, routes_tresorerie
    from app.tresorerie.services import rapprochement

    rapprochement.register()          # avertissement de clôture « versements incomplets / écart » (S3)
    app.include_router(routes_socle.router)
    app.include_router(routes_paie.router)
    app.include_router(routes_tresorerie.router)
    return app


app = create_app()
