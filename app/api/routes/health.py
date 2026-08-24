from fastapi import APIRouter

from app.api.schemas.health import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Liveness probe returning server health status."""
    return HealthResponse(status="ok")
