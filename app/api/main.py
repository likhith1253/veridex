import logging
import os
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.dependencies import verify_api_key
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

    # 1. CORS Configuration (AUD-061)
    allowed_origins_raw = os.environ.get(
        "ALLOWED_ORIGINS",
        "http://localhost:8501,http://127.0.0.1:8501,http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000,http://127.0.0.1:8000",
    )
    allowed_origins = [o.strip() for o in allowed_origins_raw.split(",") if o.strip()]
    if not allowed_origins or allowed_origins == ["*"]:
        allowed_origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True if allowed_origins != ["*"] else False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # 2. Security Headers Middleware (AUD-063)
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    # 3. Register routers with global API Key auth dependency (AUD-063)
    app.include_router(health_router)
    app.include_router(controller_router, dependencies=[Depends(verify_api_key)])
    app.include_router(integrations_router, dependencies=[Depends(verify_api_key)])
    app.include_router(investigations_router, dependencies=[Depends(verify_api_key)])
    app.include_router(runs_router, dependencies=[Depends(verify_api_key)])
    app.include_router(reconciliation_router, dependencies=[Depends(verify_api_key)])

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
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error occurred.", "status_code": 500},
        )

    return app


app = create_app()
