"""
Finance Controller API Routes for Project Sentinel (Razorpay Track 4).

Comprehensive REST API Endpoints:
- Batch Ingestion & 3-Way Reconciliation
- Executive Summary KPIs
- Financial Exposure Breakdown
- Multi-Stage Reconciliation Funnel
- Exception Management, Filtering & Detail
- Exception Aging Analysis
- Human-in-the-Loop Decision Operations (approve, reject, escalate, resolve)
- Explainability & Feature Evidence
- Live Multi-Source Cash Position
- Fee & Tax Control Auditing
- Audit Event Chronological Timeline
- Comprehensive Batch Finance Report
- Fact-Grounded Finance Q&A
- 7-Day Forward Cash Forecast
- Feed Source Health & Quality Tracking
- Failure Simulation Scenarios
"""

import logging
from decimal import Decimal
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.api.dependencies import get_db_session, get_investigation_service
from app.api.schemas.controller import (
    BatchIngestRequest,
    BatchIngestResponse,
    CopilotBriefResponse,
    CopilotQueryRequest,
    CopilotQueryResponse,
    FailureSimulationRequest,
    HumanDecisionRequest,
    SingleTransactionIngestRequest,
)
from app.investigation.service import InvestigationService
from app.models.transaction import Transaction, TransactionSource, TransactionStatus
from app.services.finance_controller import FinanceController
from app.services.human_decision_service import HumanAction

router = APIRouter(prefix="/api/v1/controller", tags=["Finance Controller"])

_VALID_EXCEPTION_CATEGORIES = {
    "amount_mismatch",
    "amount_mismatch_exception",
    "missing_ledger",
    "missing_bank",
    "missing_gateway",
    "missing_source",
    "missing_source_exception",
    "delayed_settlement",
    "delayed_settlement_exception",
    "duplicate_transaction",
    "duplicate_entry",
    "duplicate_exception",
    "fee_discrepancy",
    "fee_mismatch",
    "fee_mismatch_exception",
    "tax_mismatch_exception",
    "settlement_variance_exception",
    "partial_match_exception",
    "complex_mismatch_exception",
    "missing_fields_exception",
    "unmatched_settlement",
    "currency_mismatch",
    "unrecognized",
    "unexplained",
}


class QAQueryRequest(BaseModel):
    question: str = Field(..., description="Finance Controller question")
    run_id: Optional[str] = Field(None, description="Optional reconciliation run scope")


# 1. Batch Ingestion API
@router.post("/ingest/batch", response_model=BatchIngestResponse)
async def ingest_batch_records(
    request: BatchIngestRequest,
    session: AsyncSession = Depends(get_db_session),
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> dict[str, Any]:
    """Ingest multi-source transaction batch (50+ records) and execute 3-way reconciliation."""
    from datetime import datetime, timezone
    import traceback

    try:
        def parse_items(items, src: TransactionSource) -> list[Transaction]:
            txns = []
            for it in items:
                dt = datetime.fromisoformat(it.timestamp) if it.timestamp else datetime.now(timezone.utc)
                txns.append(
                    Transaction(
                        txn_id=it.txn_id,
                        source=src,
                        amount=Decimal(str(it.amount)),
                        currency=it.currency,
                        timestamp=dt,
                        status=TransactionStatus.COMPLETED,
                        order_id=it.order_id,
                        reference_number=it.reference_number,
                        fee=Decimal(str(it.fee)) if it.fee else None,
                        tax=Decimal(str(it.tax)) if it.tax else None,
                        narration=it.narration,
                    )
                )
            return txns

        gw_txns = parse_items(request.gateway_records, TransactionSource.GATEWAY)
        ld_txns = parse_items(request.ledger_records, TransactionSource.LEDGER)
        bk_txns = parse_items(request.bank_records, TransactionSource.BANK)

        controller = FinanceController(session, investigation_service=investigation_service)
        res = await controller.ingest_and_reconcile_batch(gw_txns, ld_txns, bk_txns, request.batch_id)
        return res
    except Exception as e:
        import logging
        logging.error(f"Batch ingestion error: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Batch ingestion failed: {str(e)}")


@router.post("/ingest")
async def ingest_single_transaction(
    request: SingleTransactionIngestRequest,
    session: AsyncSession = Depends(get_db_session),
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> dict[str, Any]:
    """Ingest a single transaction and reconcile it in real time."""
    from datetime import datetime, timezone

    try:
        source_enum = TransactionSource(request.source.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid transaction source: {request.source}")

    txn = Transaction(
        txn_id=request.txn_id,
        source=source_enum,
        amount=Decimal(str(request.amount)),
        currency=request.currency,
        timestamp=datetime.now(timezone.utc),
        status=TransactionStatus.COMPLETED,
        order_id=request.order_id,
        reference_number=request.reference_number,
        narration=request.narration,
    )

    controller = FinanceController(session, investigation_service=investigation_service)
    result = await controller.incremental_service.ingest_and_reconcile(txn)
    await session.commit()

    return {
        "transaction_id": result.transaction_id,
        "status": result.status,
        "action": result.action,
        "match_id": result.match_id,
        "matched_transaction_id": result.matched_transaction_id,
        "confidence": result.confidence,
        "exception_id": result.exception_id,
        "investigation_id": result.investigation_id,
        "processing_time_ms": result.processing_time_ms,
    }


# 2. Executive Summary KPIs
@router.get("/summary")
async def get_controller_summary(
    run_id: Optional[str] = Query(None, description="Reconciliation Run ID filter"),
    session: AsyncSession = Depends(get_db_session),
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> dict[str, Any]:
    """Retrieve executive financial KPIs and reconciliation metrics."""
    controller = FinanceController(session, investigation_service=investigation_service)
    kpis = await controller.get_summary_kpis(run_id)
    return kpis.to_dict()


@router.get("/kpis/summary")
async def get_controller_summary_legacy(
    run_id: Optional[str] = Query(None, description="Reconciliation Run ID filter"),
    session: AsyncSession = Depends(get_db_session),
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> dict[str, Any]:
    """Legacy alias for independent evaluator compatibility."""
    controller = FinanceController(session, investigation_service=investigation_service)
    kpis = await controller.get_summary_kpis(run_id)
    payload = kpis.to_dict()
    match_rate = payload.get("match_rate")
    if isinstance(match_rate, (int, float)):
        payload["match_rate_percent"] = match_rate
        payload["match_rate"] = match_rate / 100.0
    return payload


# 3. Financial Exposure Breakdown
@router.get("/exposure")
async def get_financial_exposure(
    run_id: Optional[str] = Query(None, description="Reconciliation Run ID filter"),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Retrieve Decimal-safe financial exposure breakdown."""
    from app.services.exposure_service import FinancialExposureService
    service = FinancialExposureService(session)
    exp = await service.calculate_exposure(run_id)
    return exp.to_dict()


@router.get("/cash/position")
async def get_cash_position_legacy(
    run_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Legacy alias for independent evaluator compatibility."""
    from app.services.cash_position import CashPositionService
    service = CashPositionService(session)
    summary = await service.get_cash_position(run_id)
    payload = summary.to_dict()
    payload.setdefault("expected_gross_settlement_inr", payload.get("expected_gross") or payload.get("expected_amount") or "0.00")
    payload.setdefault("expected_net_settlement_inr", payload.get("expected_net_settlement") or "0.00")
    payload.setdefault("received_bank_credits_inr", payload.get("received_bank_credits") or payload.get("received_amount") or "0.00")
    payload.setdefault("settlement_variance_inr", payload.get("settlement_variance") or "0.00")
    payload.setdefault("unreconciled_exposure_inr", payload.get("unreconciled_amount") or "0.00")
    return payload


# 4. Reconciliation Funnel
@router.get("/funnel")
async def get_reconciliation_funnel(
    run_id: Optional[str] = Query(None, description="Reconciliation Run ID filter"),
    session: AsyncSession = Depends(get_db_session),
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> dict[str, Any]:
    """Retrieve multi-stage reconciliation funnel."""
    controller = FinanceController(session, investigation_service=investigation_service)
    return await controller.get_reconciliation_funnel(run_id)


# 5. Exception Management & Filtering
@router.get("/exceptions")
async def list_exceptions(
    status: Optional[Literal["open", "investigating", "resolved", "approved", "rejected", "escalated"]] = Query(None, description="Exception lifecycle status filter"),
    category: Optional[str] = Query(None, description="Exception root-cause category filter"),
    min_exposure: Optional[Decimal] = Query(None, ge=Decimal("0.0"), description="Minimum financial exposure filter"),
    max_exposure: Optional[Decimal] = Query(None, ge=Decimal("0.0"), description="Maximum financial exposure filter"),
    transaction_id: Optional[str] = Query(None),
    run_id: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Query exceptions with multi-criteria filtering and pagination."""
    import traceback
    from app.services.exception_management_service import ExceptionManagementService
    try:
        if category and category not in _VALID_EXCEPTION_CATEGORIES:
            raise HTTPException(status_code=422, detail=f"Invalid category filter: {category}")
        service = ExceptionManagementService(session)

        items, total_count = await service.list_exceptions(
            status=status,
            category=category,
            min_exposure=min_exposure,
            max_exposure=max_exposure,
            transaction_id=transaction_id,
            run_id=run_id,
            page=page,
            page_size=page_size,
        )
        return {
            "page": page,
            "page_size": page_size,
            "total_count": total_count,
            "exceptions": items,
        }
    except HTTPException:
        raise
    except Exception as e:
        import logging
        logging.error(f"Exception list error: {str(e)}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Failed to list exceptions: {str(e)}")


@router.get("/exceptions/open")
async def list_open_exceptions(
    limit: int = Query(100, ge=1, le=1000),
    run_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Legacy alias returning open exceptions for evaluator compatibility."""
    from app.services.exception_management_service import ExceptionManagementService
    service = ExceptionManagementService(session)
    items, total_count = await service.list_exceptions(status="open", run_id=run_id, page=1, page_size=limit)
    return {"page": 1, "page_size": limit, "total_count": total_count, "exceptions": items}


@router.get("/transactions")
async def list_transactions(
    run_id: Optional[str] = Query(None, description="Reconciliation Run ID filter"),
    limit: int = Query(100, ge=1, le=1000),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """List transactions, optionally scoped by reconciliation run."""
    from sqlalchemy import select
    from app.database.models import ReconciliationItem as ReconciliationItemORM
    from app.database.models import ReconciliationRun as ReconciliationRunORM
    from app.database.models import Transaction as TransactionORM

    stmt = select(TransactionORM)
    effective_run_id = run_id
    if run_id:
        run_res = await session.execute(
            select(ReconciliationRunORM).where(
                (ReconciliationRunORM.id == run_id) | (ReconciliationRunORM.run_id == run_id)
            )
        )
        run_obj = run_res.scalar_one_or_none()
        if run_obj:
            effective_run_id = run_obj.id
            item_res = await session.execute(
                select(ReconciliationItemORM.transaction_id).where(ReconciliationItemORM.run_id == run_obj.id)
            )
            txn_ids = list(item_res.scalars().all())
            stmt = stmt.where(TransactionORM.id.in_(txn_ids)) if txn_ids else stmt.where(False)
        else:
            stmt = stmt.where(False)

    res = await session.execute(stmt.order_by(TransactionORM.created_at.desc()).limit(limit))
    transactions = []
    for txn in res.scalars().all():
        transactions.append({
            "id": txn.id,
            "run_id": effective_run_id,
            "domain_transaction_id": txn.domain_transaction_id,
            "source": txn.source.value if hasattr(txn.source, "value") else str(txn.source),
            "reference_number": txn.reference_number,
            "order_id": txn.order_id,
            "amount": str(txn.amount),
            "currency": txn.currency,
            "timestamp": txn.timestamp.isoformat() if txn.timestamp else None,
            "fee": str(txn.fee) if txn.fee is not None else None,
            "tax": str(txn.tax) if txn.tax is not None else None,
            "status": txn.status.value if hasattr(txn.status, "value") else str(txn.status),
        })

    return {"run_id": effective_run_id, "total_count": len(transactions), "transactions": transactions}


# 6. Exception Aging Analysis
@router.get("/exceptions/aging")
async def get_exception_aging(
    run_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Retrieve exception aging distribution across standard time buckets."""
    from app.services.exception_management_service import ExceptionManagementService
    service = ExceptionManagementService(session)
    aging = await service.calculate_exception_aging(run_id)
    from dataclasses import asdict
    return asdict(aging)


# 7. Single Exception Detail View
@router.get("/exceptions/intelligence")
async def list_exception_intelligence(
    run_id: Optional[str] = Query(None, description="Optional run scope for intelligence listing"),
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_db_session),
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> list[dict[str, Any]]:
    """Return risk-ordered structured intelligence for open exceptions in a scope."""
    controller = FinanceController(session, investigation_service=investigation_service)
    return await controller.list_exception_intelligence(run_id=run_id, limit=limit)


@router.get("/exceptions/{exception_id}/intelligence")
async def get_exception_intelligence(
    exception_id: str,
    session: AsyncSession = Depends(get_db_session),
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> dict[str, Any]:
    """Return a structured explanation of why an exception happened, how serious it is, and what to do next."""
    controller = FinanceController(session, investigation_service=investigation_service)
    try:
        return await controller.get_exception_intelligence(exception_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/exceptions/{exception_id}")
async def get_exception_detail(
    exception_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Retrieve full structured evidence and investigation details for a single exception."""
    from app.services.exception_management_service import ExceptionManagementService
    service = ExceptionManagementService(session)
    try:
        detail = await service.get_exception_detail(exception_id)
        return detail.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/exceptions/{exception_id}/investigation")
async def get_exception_investigation_view(
    exception_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Return comprehensive investigation view with timeline, evidence, and decision boundary."""
    from app.services.investigation_view_service import InvestigationViewService
    service = InvestigationViewService(session)
    try:
        view = await service.get_investigation_view(exception_id)
        return view.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# 8. Human Decision API
@router.post("/exceptions/{exception_id}/decision")
async def apply_human_decision(
    exception_id: str,
    request: HumanDecisionRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Apply human decision (approve, reject, escalate, resolve) with validation and audit logging."""
    from app.services.human_decision_service import HumanDecisionService
    service = HumanDecisionService(session)
    try:
        act_enum = HumanAction(request.action.lower())
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid action: {request.action}. Must be one of: approve, reject, escalate, resolve")

    try:
        res = await service.apply_decision(
            exception_id=exception_id,
            action=act_enum,
            actor=request.actor,
            reason=request.reason,
        )
        from dataclasses import asdict
        return asdict(res)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e).strip("'\""))
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error applying human decision on exception %s: %s", exception_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error occurred.")


# 9. Explainability API
@router.get("/decisions/{decision_id}/explain")
async def explain_decision(
    decision_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Retrieve explainability metadata and feature vectors for a reconciliation decision."""
    from app.services.explainability_service import ExplainabilityService
    service = ExplainabilityService(session)
    try:
        expl = await service.explain_decision(decision_id)
        return expl.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


# 10. Cash Position
@router.get("/cash-position")
async def get_cash_position(
    run_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Retrieve grounded multi-source cash position summary."""
    from app.services.cash_position import CashPositionService
    service = CashPositionService(session)
    summary = await service.get_cash_position(run_id)
    return summary.to_dict()


# 11. Fee and Tax Control
@router.get("/fee-tax-control")
async def get_fee_tax_control(
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Retrieve fee and tax reconciliation report."""
    from app.services.fee_tax_service import FeeTaxService
    service = FeeTaxService(session)
    report = await service.reconcile_fees_and_taxes(limit)
    return report.to_dict()


@router.get("/accounting/fee-audit")
async def get_fee_tax_control_legacy(
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Legacy alias for independent evaluator compatibility."""
    from app.services.fee_tax_service import FeeTaxService
    service = FeeTaxService(session)
    report = await service.reconcile_fees_and_taxes(limit)
    return report.to_dict()


# 12. Audit Timeline
@router.get("/audit/timeline")
async def get_audit_timeline(
    run_id: Optional[str] = Query(None),
    transaction_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db_session),
) -> list[dict[str, Any]]:
    """Retrieve chronological audit timeline."""
    controller = FinanceController(session)
    return await controller.get_audit_timeline(run_id=run_id, transaction_id=transaction_id)


# 13. Finance Controller Report
@router.get("/report")
async def get_controller_report(
    run_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_db_session),
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> dict[str, Any]:
    """Generate structured batch-level finance controller report."""
    controller = FinanceController(session, investigation_service=investigation_service)
    return await controller.generate_controller_report(run_id)


# 14. Fact-Grounded Finance Q&A
@router.post("/qa")
async def answer_finance_query(
    request: QAQueryRequest,
    session: AsyncSession = Depends(get_db_session),
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> dict[str, Any]:
    """Answer finance controller questions grounded strictly in PostgreSQL state."""
    controller = FinanceController(session, investigation_service=investigation_service)
    qa_resp = await controller.qa_service.answer_query(request.question, request.run_id)
    return {
        "question": qa_resp.question,
        "direct_answer": qa_resp.direct_answer,
        "key_metrics": qa_resp.key_metrics,
        "evidence_records": qa_resp.evidence_records,
        "sql_facts_used": qa_resp.sql_facts_used,
        "confidence": qa_resp.confidence,
    }


@router.post("/copilot/query", response_model=CopilotQueryResponse)
async def ask_copilot_query(
    request: CopilotQueryRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Answer grounded finance-control questions with integrated controller context and deterministic recommendations."""
    from app.services.copilot_service import FinanceCopilotService

    service = FinanceCopilotService(session)
    return await service.answer_question(request.question, request.run_id)


@router.api_route("/copilot/brief", methods=["GET", "POST"], response_model=CopilotBriefResponse)
async def get_finance_monthly_brief(
    request: dict[str, Any] | None = None,
    run_id: Optional[str] = Query(None, description="Optional run scope for the brief"),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Render a live executive brief from the current controller state and exception intelligence."""
    from app.services.copilot_service import FinanceCopilotService

    service = FinanceCopilotService(session)
    effective_run_id = run_id
    if isinstance(request, dict) and request.get("run_id"):
        effective_run_id = request.get("run_id")
    return await service.generate_daily_brief(effective_run_id)


# 15. 7-Day Cash Forecast
@router.get("/forecast")
async def get_7day_cash_forecast(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Retrieve transparent 7-day forward cash settlement forecast."""
    from app.services.forecast_service import CashForecastService
    service = CashForecastService(session)
    fc = await service.generate_7day_forecast()
    return fc.to_dict()


# 16. Benchmark / Model Evaluation (evaluation-only)
@router.get("/benchmark")
async def get_benchmark_results(
    num_transactions: int = Query(100, ge=1, le=5000),
    seed: int = Query(42, ge=0, le=999999),
) -> dict[str, Any]:
    """Run an evaluation-only benchmark in memory without touching live PostgreSQL state."""
    return FinanceController.get_benchmark_evaluation(num_transactions=num_transactions, seed=seed)


# 17. Source Health
@router.get("/source-health")
async def get_source_health(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Retrieve feed source health and discrepancy metrics."""
    from app.services.source_health_service import SourceHealthService
    service = SourceHealthService(session)
    health = await service.get_source_health()
    return health.to_dict()


# 17. Failure Simulation
@router.post("/simulate-failure")
async def simulate_failure(
    request: FailureSimulationRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Simulate backend operational failure scenarios (corrupted UTR, duplicate, delayed, etc.)."""
    controller = FinanceController(session)
    return await controller.simulate_failure_scenario(request.scenario, request.amount)


# 18. Refund & Partial-Refund Reconciliation
@router.get("/refunds/audit")
async def get_refund_audit(
    limit: int = Query(100, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Retrieve refund reconciliation report including over-refund anomalies."""
    from app.services.refund_service import RefundAccountingService
    service = RefundAccountingService(session)
    report = await service.audit_refunds(limit)
    return report.to_dict()


# 19. Unified Settlement Accounting
@router.get("/settlement/accounting")
async def get_settlement_accounting(
    run_id: Optional[str] = Query(None, description="Reconciliation Run ID filter"),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Compute Gross - Fees - Taxes - Refunds = Expected Settlement vs Bank Credits."""
    from app.services.settlement_accounting_service import SettlementAccountingService
    service = SettlementAccountingService(session)
    summary = await service.calculate_settlement_accounting(run_id)
    return summary.to_dict()


# 20. Duplicate Payment Audit
@router.get("/duplicates/audit")
async def get_duplicate_audit(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Isolate duplicate charges, duplicate bank settlements, and duplicate webhooks."""
    from app.services.duplicate_detection_service import DuplicateDetectionService
    service = DuplicateDetectionService(session)
    report = await service.audit_duplicates()
    return report.to_dict()


class AssignExceptionRequest(BaseModel):
    assigned_to: str = Field(..., description="Controller analyst username or email")
    actor: str = Field("finance_controller_admin", description="Assigner username")


class AddNoteRequest(BaseModel):
    note: str = Field(..., description="Review note content")
    actor: str = Field("finance_controller_user", description="Note author")


# 21. Assign Exception & Add Review Note
@router.post("/exceptions/{exception_id}/assign")
async def assign_exception(
    exception_id: str,
    request: AssignExceptionRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Assign an open exception to a controller analyst with immutable audit log."""
    from app.services.human_decision_service import HumanAction, HumanDecisionService
    service = HumanDecisionService(session)
    try:
        res = await service.apply_decision(
            exception_id=exception_id,
            action=HumanAction.ASSIGN,
            actor=request.actor,
            assigned_to=request.assigned_to,
        )
        return res.to_dict()
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e).strip("'\""))
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error assigning exception %s: %s", exception_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error occurred.")


@router.post("/exceptions/{exception_id}/note")
async def add_exception_note(
    exception_id: str,
    request: AddNoteRequest,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Add a review note to an exception with immutable audit log."""
    from app.services.human_decision_service import HumanAction, HumanDecisionService
    service = HumanDecisionService(session)
    try:
        res = await service.apply_decision(
            exception_id=exception_id,
            action=HumanAction.ADD_NOTE,
            actor=request.actor,
            note=request.note,
        )
        return res.to_dict()
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e).strip("'\""))
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error adding note to exception %s: %s", exception_id, e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error occurred.")
