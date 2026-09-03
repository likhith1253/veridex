from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_investigation_service
from app.api.schemas.investigation import (
    InvestigationDossierResponse,
    InvestigationResponse,
)
from app.investigation.service import InvestigationService

router = APIRouter(tags=["Investigations"])


@router.get("/investigations/{exception_id}", response_model=InvestigationResponse)
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
    conclusion = investigations[0]
    return InvestigationResponse(**conclusion.model_dump())


@router.get("/api/v1/investigations/{id}", response_model=InvestigationDossierResponse)
@router.get("/investigations/{id}/dossier", response_model=InvestigationDossierResponse)
async def get_investigation_dossier(
    id: str,
    service: InvestigationService = Depends(get_investigation_service),
) -> InvestigationDossierResponse:
    """Retrieve comprehensive AI investigation & evidence dossier for an exception, settlement, or transaction."""
    return await service.build_investigation_dossier(id)

