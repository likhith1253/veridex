from fastapi import FastAPI

from app.api.routes.controller import router as controller_router
from app.api.routes.health import router as health_router
from app.api.routes.integrations import router as integrations_router
from app.api.routes.investigations import router as investigations_router
from app.api.routes.reconciliation import router as reconciliation_router
from app.api.routes.runs import router as runs_router


def create_app() -> FastAPI:
    """Factory function for FastAPI application."""
    app = FastAPI(
        title="Project Sentinel API",
        description="AI Financial Controller and Reconciliation Engine API",
        version="0.2.0",
    )

    # Register routers
    app.include_router(health_router)
    app.include_router(controller_router)
    app.include_router(integrations_router)
    app.include_router(investigations_router)
    app.include_router(runs_router)
    app.include_router(reconciliation_router)

    return app


app = create_app()
