import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.dependencies import verify_api_key
from app.api.routes.controller import router as controller_router
from app.api.routes.finance_actions import router as finance_actions_router
from app.api.routes.health import router as health_router
from app.api.routes.integrations import router as integrations_router
from app.api.routes.investigations import router as investigations_router
from app.api.routes.reconciliation import router as reconciliation_router
from app.api.routes.runs import router as runs_router
from app.api.routes.settlement_intelligence import router as settlement_intelligence_router
from app.api.routes.webhooks import router as webhooks_router

logger = logging.getLogger(__name__)


def _run_alembic_upgrade() -> None:
    """Blocking call — runs in a worker thread via asyncio.to_thread so its
    internal asyncio.run() (in alembic/env.py) doesn't collide with the
    event loop already running the FastAPI lifespan."""
    from alembic import command
    from alembic.config import Config

    repo_root = Path(__file__).resolve().parents[2]
    cfg = Config(str(repo_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(repo_root / "alembic"))
    command.upgrade(cfg, "head")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Auto-apply any pending Alembic migrations on boot. This exists because
    # the webhook_events table shipped as an ORM model with no migration ever
    # authored for it — it only existed in environments where someone had
    # manually run Base.metadata.create_all(), which silently masked the gap
    # in local development while a freshly-migrated production database
    # (Neon, provisioned purely via `alembic upgrade head`) was missing it
    # entirely, crashing every real webhook. Running the upgrade here too
    # means a schema change can never again ship to migrations/ without also
    # reaching every deployed environment on its next restart, regardless of
    # whether the hosting platform's start command happens to run migrations.
    try:
        await asyncio.to_thread(_run_alembic_upgrade)
        logger.info("Database schema is up to date (alembic upgrade head).")
    except Exception as e:
        logger.error("Startup migration check failed: %s", e, exc_info=True)
    yield


def create_app() -> FastAPI:
    """Factory function for FastAPI application."""
    app = FastAPI(
        title="Veridex API",
        description="Veridex — AI Financial Control & Reconciliation Engine API. Find the discrepancy. Prove the cause. Control the action.",
        version="0.2.0",
        lifespan=lifespan,
    )

    # 1. Configure CORS middleware (AUD-059)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Add Security Headers Middleware (AUD-058)
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    # 3. Register routers with global API Key auth dependency (AUD-063)
    @app.get("/", tags=["System"])
    async def root():
        return {
            "name": "Veridex API",
            "status": "online",
            "version": "0.2.0",
            "documentation": "/docs",
            "health": "/health",
        }

    app.include_router(health_router)
    app.include_router(webhooks_router)
    app.include_router(controller_router, dependencies=[Depends(verify_api_key)])
    app.include_router(finance_actions_router, dependencies=[Depends(verify_api_key)])
    app.include_router(integrations_router, dependencies=[Depends(verify_api_key)])
    app.include_router(investigations_router, dependencies=[Depends(verify_api_key)])
    app.include_router(runs_router, dependencies=[Depends(verify_api_key)])
    app.include_router(runs_router, prefix="/api/v1", dependencies=[Depends(verify_api_key)])
    app.include_router(reconciliation_router, dependencies=[Depends(verify_api_key)])
    app.include_router(settlement_intelligence_router, dependencies=[Depends(verify_api_key)])


    # 4. Structured error handlers (AUD-004, AUD-049, AUD-060, AUD-064)
    from fastapi.encoders import jsonable_encoder

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=jsonable_encoder({"detail": exc.detail, "status_code": exc.status_code}),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=jsonable_encoder({"detail": exc.errors(), "status_code": 422}),
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled server exception: %s", exc, exc_info=True)
        # Starlette moves the bare-`Exception` handler to its outermost
        # ServerErrorMiddleware, which sits OUTSIDE CORSMiddleware — so its
        # response never gets CORS headers added automatically. Without this,
        # every unhandled backend exception surfaces to the browser as a
        # misleading "blocked by CORS policy" error instead of the real 500.
        origin = request.headers.get("origin")
        headers = {"Vary": "Origin"}
        if origin:
            headers["Access-Control-Allow-Origin"] = origin
            headers["Access-Control-Allow-Credentials"] = "true"
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error occurred.", "status_code": 500},
            headers=headers,
        )

    return app


app = create_app()
