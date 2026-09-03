import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session, verify_api_key
from app.api.schemas.finance_action import (
    ActionDecisionRequest,
    ActionExecuteRequest,
    ActionRecommendRequest,
    FinanceActionResponse,
)
from app.services.finance_action_service import FinanceActionService, PolicyViolationError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/actions", tags=["Finance Actions"])


@router.post(
    "/recommend",
    response_model=FinanceActionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Recommend a policy-gated finance action",
    dependencies=[Depends(verify_api_key)],
)
async def recommend_finance_action(
    req: ActionRecommendRequest,
    session: AsyncSession = Depends(get_db_session),
) -> FinanceActionResponse:
    """Recommend a bounded financial action.
    
    Transitions: DETECTED -> INVESTIGATING -> RECOMMENDED -> PENDING_APPROVAL.
    AI can recommend, but cannot independently execute a financial action.
    """
    service = FinanceActionService(session)
    try:
        action = await service.recommend_action(
            entity_type=req.entity_type,
            entity_id=req.entity_id,
            action_type=req.action_type,
            amount=req.amount,
            currency=req.currency,
            recommended_by=req.recommended_by,
            recommendation_reason=req.recommendation_reason,
            evidence=req.evidence,
            run_id=req.run_id,
        )
        return FinanceActionResponse.model_validate(action)
    except PolicyViolationError as pve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(pve))
    except Exception as e:
        logger.error("Failed to recommend finance action: %s", e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/{id}/approve",
    response_model=FinanceActionResponse,
    summary="Approve a pending finance action (explicit human approval required)",
    dependencies=[Depends(verify_api_key)],
)
async def approve_finance_action(
    id: str,
    req: ActionDecisionRequest,
    session: AsyncSession = Depends(get_db_session),
) -> FinanceActionResponse:
    """Explicit human approval for a pending finance action."""
    service = FinanceActionService(session)
    try:
        action = await service.approve_action(
            action_id=id,
            actor=req.actor,
            reason=req.reason,
        )
        return FinanceActionResponse.model_validate(action)
    except PolicyViolationError as pve:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pve))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error("Failed to approve finance action %s: %s", id, e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/{id}/reject",
    response_model=FinanceActionResponse,
    summary="Reject a pending finance action",
    dependencies=[Depends(verify_api_key)],
)
async def reject_finance_action(
    id: str,
    req: ActionDecisionRequest,
    session: AsyncSession = Depends(get_db_session),
) -> FinanceActionResponse:
    """Explicit human rejection for a pending finance action."""
    service = FinanceActionService(session)
    try:
        action = await service.reject_action(
            action_id=id,
            actor=req.actor,
            reason=req.reason,
        )
        return FinanceActionResponse.model_validate(action)
    except PolicyViolationError as pve:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pve))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error("Failed to reject finance action %s: %s", id, e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/{id}/execute",
    response_model=FinanceActionResponse,
    summary="Execute an approved bounded finance action",
    dependencies=[Depends(verify_api_key)],
)
async def execute_finance_action(
    id: str,
    req: ActionExecuteRequest,
    session: AsyncSession = Depends(get_db_session),
) -> FinanceActionResponse:
    """Execute an approved bounded finance action.
    
    Actions must be bounded and must NOT perform unrestricted money movement.
    AI can recommend, but cannot independently execute a financial action.
    Approval must be explicit.
    """
    service = FinanceActionService(session)
    try:
        action = await service.execute_action(
            action_id=id,
            actor=req.actor,
        )
        return FinanceActionResponse.model_validate(action)
    except PolicyViolationError as pve:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(pve))
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(ve))
    except Exception as e:
        logger.error("Failed to execute finance action %s: %s", id, e, exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/{id}",
    response_model=FinanceActionResponse,
    summary="Get status and details of a finance action",
    dependencies=[Depends(verify_api_key)],
)
async def get_finance_action(
    id: str,
    session: AsyncSession = Depends(get_db_session),
) -> FinanceActionResponse:
    """Fetch status, details, and execution outcome of a finance action."""
    service = FinanceActionService(session)
    action = await service.get_action(id)
    if not action:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Finance action '{id}' not found.")
    return FinanceActionResponse.model_validate(action)


@router.get(
    "",
    response_model=list[FinanceActionResponse],
    summary="List finance actions history",
    dependencies=[Depends(verify_api_key)],
)
async def list_finance_actions(
    state: Optional[str] = Query(None, description="Filter by state (PENDING_APPROVAL, APPROVED, etc.)"),
    entity_id: Optional[str] = Query(None, description="Filter by target entity ID"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
) -> list[FinanceActionResponse]:
    """List finance actions history with optional state and entity filters."""
    service = FinanceActionService(session)
    actions = await service.list_actions(state=state, entity_id=entity_id, entity_type=entity_type, limit=limit)
    return [FinanceActionResponse.model_validate(a) for a in actions]
