from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_investigation_service
from app.api.schemas.investigation import InvestigationResponse
from app.investigation.service import InvestigationService

router = APIRouter(prefix="/investigations", tags=["Investigations"])


@router.get("/{exception_id}", response_model=InvestigationResponse)
async def get_investigation_by_exception(
    exception_id: str,
    service: InvestigationService = Depends(get_investigation_service),
) -> InvestigationResponse:
    """Retrieve persisted investigation conclusion for a given exception ID."""
    investigations = await service.get_by_exception(exception_id)
    if not investigations:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation not found for exception_id '{exception_id}'",
        )
    # Return the latest / primary investigation for the exception
    conclusion = investigations[0]
    return InvestigationResponse(**conclusion.model_dump())
