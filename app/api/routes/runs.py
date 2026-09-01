from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select

from app.api.dependencies import get_reconciliation_repository
from app.database.models import ReconciliationRun as ReconciliationRunORM
from app.api.schemas.run import RunSummaryResponse
from app.database.repositories.reconciliation_repository import ReconciliationRepository

router = APIRouter(prefix="/runs", tags=["Runs"])


@router.get("")
async def list_runs(
    limit: int = Query(20, ge=1, le=100),
    repo: ReconciliationRepository = Depends(get_reconciliation_repository),
) -> dict[str, object]:
    """List the most recent reconciliation runs for UI scoping."""
    result = await repo.session.execute(
        select(ReconciliationRunORM).order_by(ReconciliationRunORM.created_at.desc()).limit(limit)
    )
    runs = result.scalars().all()
    return {
        "total_count": len(runs),
        "runs": [
            {
                "id": r.id,
                "run_id": r.run_id,
                "status": r.status.value if hasattr(r.status, "value") else str(r.status),
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "gateway_count": r.gateway_count,
                "ledger_count": r.ledger_count,
                "bank_count": r.bank_count,
                "match_count": r.match_count,
                "exception_count": r.exception_count,
            }
            for r in runs
        ],
    }


@router.get("/{run_id}/summary", response_model=RunSummaryResponse)
async def get_run_summary(
    run_id: str,
    repo: ReconciliationRepository = Depends(get_reconciliation_repository),
) -> RunSummaryResponse:
    """Retrieve execution summary for a reconciliation run."""
    run = await repo.get_run_by_run_id(run_id)
    if not run:
        # Fallback check by internal ORM ID
        run = await repo.get_run_by_id(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reconciliation run not found for run_id '{run_id}'",
        )

    total_transactions = run.gateway_count + run.ledger_count + run.bank_count
    return RunSummaryResponse(
        run_id=run.run_id,
        status=run.status,
        started_at=run.started_at,
        completed_at=run.ended_at,
        total_transactions=total_transactions,
        gateway_count=run.gateway_count,
        ledger_count=run.ledger_count,
        bank_count=run.bank_count,
        match_count=run.match_count,
        exception_count=run.exception_count,
        summary=run.summary,
    )
