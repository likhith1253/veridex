"""
Finance Controller API Routes for Project Sentinel (Razorpay Track 4).

Provides endpoints for:
- Executive Summary & Finance KPIs
- Reconciliation Funnel Analytics
- Honest Exception Drill-Down
- Live Cash Position Overview
- Grounded Natural Language Finance Q&A
- Real-Time Transaction Ingestion
- Real-Time Multi-Source Streaming Simulation
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session, get_investigation_service
from app.investigation.service import InvestigationService
from app.matching.ml_scorer import MLScorer
from app.models.transaction import Transaction, TransactionSource, TransactionStatus
from app.services.finance_controller import FinanceController
from simulator.stream_simulator import RealTimeStreamSimulator, StreamConfig

router = APIRouter(prefix="/api/v1/controller", tags=["Finance Controller"])


class QAQueryRequest(BaseModel):
    question: str = Field(..., description="Finance Controller question")
    run_id: Optional[str] = Field(None, description="Optional reconciliation run scope")


class SingleTransactionIngestRequest(BaseModel):
    txn_id: str
    source: str  # "gateway", "ledger", "bank"
    amount: float
    currency: str = "INR"
    order_id: Optional[str] = None
    reference_number: Optional[str] = None
    narration: Optional[str] = None


class StreamSimulateRequest(BaseModel):
    batch_size: int = Field(50, ge=1, le=1000)
    delay_between_events_sec: float = Field(0.01, ge=0.0)


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


@router.get("/funnel")
async def get_reconciliation_funnel(
    run_id: Optional[str] = Query(None, description="Reconciliation Run ID filter"),
    session: AsyncSession = Depends(get_db_session),
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> dict[str, Any]:
    """Retrieve the multi-stage reconciliation funnel."""
    controller = FinanceController(session, investigation_service=investigation_service)
    return await controller.get_reconciliation_funnel(run_id)


@router.get("/exceptions")
async def get_honest_exceptions(
    limit: int = Query(50, ge=1, le=200),
    run_id: Optional[str] = Query(None, description="Reconciliation Run ID filter"),
    session: AsyncSession = Depends(get_db_session),
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> list[dict[str, Any]]:
    """Retrieve honest transparent exception list with evidence and recommended actions."""
    controller = FinanceController(session, investigation_service=investigation_service)
    return await controller.get_honest_exception_list(limit, run_id)


@router.get("/cash-position")
async def get_cash_position(
    run_id: Optional[str] = Query(None, description="Reconciliation Run ID filter"),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Retrieve grounded multi-source cash position summary."""
    from app.services.cash_position import CashPositionService
    service = CashPositionService(session)
    summary = await service.get_cash_position(run_id)
    return summary.to_dict()


@router.post("/qa")
async def answer_finance_query(
    request: QAQueryRequest,
    session: AsyncSession = Depends(get_db_session),
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> dict[str, Any]:
    """Answer finance controller questions grounded strictly in PostgreSQL state."""
    controller = FinanceController(session, investigation_service=investigation_service)
    qa_resp = await controller.answer_finance_query(request.question, request.run_id)
    return {
        "question": qa_resp.question,
        "direct_answer": qa_resp.direct_answer,
        "key_metrics": qa_resp.key_metrics,
        "evidence_records": qa_resp.evidence_records,
        "sql_facts_used": qa_resp.sql_facts_used,
        "confidence": qa_resp.confidence,
    }


@router.post("/ingest")
async def ingest_single_transaction(
    request: SingleTransactionIngestRequest,
    session: AsyncSession = Depends(get_db_session),
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> dict[str, Any]:
    """Ingest a single transaction and reconcile it in real time."""
    from datetime import datetime, timezone
    from decimal import Decimal

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
    result = await controller.ingest_single_transaction(txn)
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


@router.post("/simulate-stream")
async def simulate_transaction_stream(
    request: StreamSimulateRequest,
    session: AsyncSession = Depends(get_db_session),
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> dict[str, Any]:
    """Stream synthetic multi-source events through the real-time reconciliation engine."""
    controller = FinanceController(session, investigation_service=investigation_service)
    streamer = RealTimeStreamSimulator(StreamConfig(
        batch_size=request.batch_size,
        delay_between_events_sec=request.delay_between_events_sec,
    ))

    ingested = 0
    matched_det = 0
    matched_ml = 0
    exceptions = 0

    async for txn in streamer.stream_events(request.batch_size):
        res = await controller.ingest_single_transaction(txn)
        ingested += 1
        if res.status == "MATCHED_DETERMINISTIC":
            matched_det += 1
        elif res.status == "MATCHED_ML":
            matched_ml += 1
        elif res.status == "EXCEPTION_CREATED":
            exceptions += 1

    await session.commit()

    return {
        "events_streamed": ingested,
        "matched_deterministic": matched_det,
        "matched_ml": matched_ml,
        "exceptions_created": exceptions,
        "status": "STREAM_COMPLETE",
    }
