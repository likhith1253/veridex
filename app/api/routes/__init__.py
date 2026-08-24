from app.api.routes.health import router as health_router
from app.api.routes.investigations import router as investigations_router
from app.api.routes.runs import router as runs_router

__all__ = ["health_router", "investigations_router", "runs_router"]
