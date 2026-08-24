from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.investigations import router as investigations_router
from app.api.routes.runs import router as runs_router


def create_app() -> FastAPI:
    """Factory function for FastAPI application."""
    app = FastAPI(
        title="Project Sentinel API",
        description="AI financial reconciliation and investigation engine API",
        version="0.1.0",
    )

    # Register routers
    app.include_router(health_router)
    app.include_router(investigations_router)
    app.include_router(runs_router)

    return app


app = create_app()
