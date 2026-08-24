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

    from fastapi import Request
    from fastapi.responses import JSONResponse
    import traceback

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={"detail": f"Internal Server Error: {str(exc)}", "traceback": traceback.format_exc()}
        )

    return app


app = create_app()
