import logging
import uuid
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.dependencies import get_reconciliation_service
from app.api.schemas.reconciliation import ReconciliationRunRequest
from app.models.reconciliation_summary import ReconciliationSummary
from app.services.reconciliation import ReconciliationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reconciliation", tags=["Reconciliation"])


@router.post("/runs", response_model=ReconciliationSummary, status_code=status.HTTP_200_OK)
async def trigger_reconciliation_run(
    request: ReconciliationRunRequest,
    service: ReconciliationService = Depends(get_reconciliation_service),
) -> ReconciliationSummary:
    """Execute a reconciliation run across gateway, ledger, and bank feeds."""
    run_id = request.run_id or f"run_{uuid.uuid4().hex[:12]}"
    transactions_by_source = request.to_transactions_by_source()

    try:
        summary = await service.run_reconciliation(
            transactions_by_source=transactions_by_source,
            run_id=run_id,
        )
        return summary
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Reconciliation run failed for run_id %s: %s", run_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reconciliation run failed: {str(e)}",
        )
