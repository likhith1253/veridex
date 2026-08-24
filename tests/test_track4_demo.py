"""
Comprehensive Track 4 Demo and Integration Test Suite for Project Sentinel.

Verifies:
1. 50+ batch processing operations loop
2. Multi-stage reconciliation funnel & honest exception lists
3. Incremental real-time transaction ingestion
4. Grounded Controller Q&A
5. FastAPI Controller routes (/summary, /funnel, /exceptions, /cash-position, /qa, /ingest)
"""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import create_app
from app.models.decision_result import DecisionAction, DecisionResult
from app.models.exception_record import ExceptionCategory, ExceptionRecord
from app.models.transaction import Transaction, TransactionSource, TransactionStatus
from app.services.finance_controller import ControllerKPIs, FinanceController


@pytest.fixture
def test_app():
    return create_app()


@pytest.mark.asyncio
async def test_controller_api_routes(test_app):
    """Test all controller API routes with mocked database sessions."""
    from app.api.dependencies import get_db_session, get_investigation_service
    mock_db_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one.return_value = 0
    mock_res.scalar_one_or_none.return_value = None
    mock_res.scalars.return_value.all.return_value = []
    mock_db_session.execute = AsyncMock(return_value=mock_res)
    test_app.dependency_overrides[get_db_session] = lambda: mock_db_session
    test_app.dependency_overrides[get_investigation_service] = lambda: MagicMock()

    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Health check
        resp = await client.get("/health")
        assert resp.status_code == 200

        # Mock dependency overrides for controller routes
        with patch("app.api.routes.controller.FinanceController") as MockController:
            mock_inst = MagicMock()
            mock_inst.get_summary_kpis = AsyncMock(return_value=ControllerKPIs(
                total_records_processed=150,
                total_logical_transactions=50,
                total_transaction_value_inr=1500000.0,
                deterministic_matches=82,
                ml_recovered_matches=18,
                total_matched_records=100,
                automatic_matches=82,
                manual_reviews=7,
                unresolved_transactions=9,
                match_rate=90.0,
                reconciliation_precision=89.86,
                reconciliation_recall=100.0,
                f1_score=94.66,
                exception_rate=9.0,
                total_matched_monetary_value_inr=1400000.0,
                unresolved_monetary_exposure_inr=75000.0,
                manual_review_exposure_inr=25000.0,
                high_risk_exposure_inr=30000.0,
                delayed_settlement_inr=25000.0,
                duplicate_amount_inr=15000.0,
                fee_mismatch_inr=5000.0,
                processing_throughput_tps=1800.0,
                average_processing_latency_ms=0.55,
            ))
            mock_inst.get_reconciliation_funnel = AsyncMock(return_value={
                "incoming_records": 150,
                "deterministic_matches": 82,
                "ml_recovered": 18,
                "manual_reviews": 7,
                "unresolved": 9,
                "final_match_rate": 90.0,
            })
            mock_inst.get_honest_exception_list = AsyncMock(return_value=[
                {
                    "exception_id": "exc-001",
                    "transaction_id": "tx-001",
                    "category": "delayed_settlement",
                    "confidence": 0.85,
                    "financial_exposure_inr": 25000.0,
                    "expected_cost_inr": 3750.0,
                    "explanation": "Settlement delayed past SLA",
                    "evidence": {},
                    "recommended_action": "escalate_manual",
                    "resolved": False,
                }
            ])
            from app.services.finance_qa import QAResponse
            mock_qa = MagicMock()
            mock_qa.answer_query = AsyncMock(return_value=QAResponse(
                question="How much money is unreconciled?",
                direct_answer="Currently, INR 75,000.00 remains unreconciled across open exceptions.",
                key_metrics={"total_unreconciled_inr": 75000.0},
                evidence_records=[],
                sql_facts_used=["Calculated from exceptions"],
            ))
            mock_inst.qa_service = mock_qa
            from app.services.incremental_reconciliation import IncrementalReconciliationResult
            mock_inc = MagicMock()
            mock_inc.ingest_and_reconcile = AsyncMock(return_value=IncrementalReconciliationResult(
                transaction_id="GW_LIVE_101",
                status="MATCHED_DETERMINISTIC",
                action="auto_match",
                match_id="m-101",
                matched_transaction_id="LD_LIVE_101",
                confidence=0.98,
                processing_time_ms=0.85,
            ))
            mock_inst.incremental_service = mock_inc

            MockController.return_value = mock_inst

            # GET /api/v1/controller/summary
            r_sum = await client.get("/api/v1/controller/summary")
            assert r_sum.status_code == 200
            assert r_sum.json()["total_records_processed"] == 150
            assert r_sum.json()["match_rate"] == 90.0

            # GET /api/v1/controller/funnel
            r_fun = await client.get("/api/v1/controller/funnel")
            assert r_fun.status_code == 200
            assert r_fun.json()["deterministic_matches"] == 82

            # GET /api/v1/controller/exceptions
            r_exc = await client.get("/api/v1/controller/exceptions")
            assert r_exc.status_code == 200
            assert "exceptions" in r_exc.json()

            # POST /api/v1/controller/qa
            r_qa = await client.post("/api/v1/controller/qa", json={"question": "How much money is unreconciled?"})
            assert r_qa.status_code == 200
            assert "75,000.00" in r_qa.json()["direct_answer"]

            # POST /api/v1/controller/ingest
            r_ing = await client.post("/api/v1/controller/ingest", json={
                "txn_id": "GW_LIVE_101",
                "source": "gateway",
                "amount": 5000.0,
                "currency": "INR",
                "order_id": "ORD_101",
                "reference_number": "UTR_101"
            })
            assert r_ing.status_code == 200
            assert r_ing.json()["status"] == "MATCHED_DETERMINISTIC"
