import logging
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes.controller import router as controller_router
from app.api.routes.health import router as health_router
from app.api.routes.integrations import router as integrations_router
from app.api.routes.investigations import router as investigations_router
from app.api.routes.reconciliation import router as reconciliation_router
from app.api.routes.runs import router as runs_router

logger = logging.getLogger(__name__)


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

    # Structured error handlers (AUD-049, AUD-060)
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
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error occurred.", "status_code": 500},
        )

    return app


app = create_app()
