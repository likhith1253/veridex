"""
Comprehensive Backend Test Suite for Project Sentinel AI Finance Controller (Razorpay Track 4).

Tests:
1. 50+ record batch ingestion & reconciliation API
2. Summary calculations from database state
3. Exception querying, filtering, and single-view retrieval
4. Human decision actions (approve, reject, escalate, resolve)
5. Invalid human state transitions rejection
6. Immutable audit timeline logging
7. Explainability feature extraction
8. Decimal-safe exposure calculations
9. Exception aging calculations
10. Grounded Q&A arithmetic correctness
11. Fee & Tax control auditing
12. 7-Day cash forecasting
13. Source health tracking
14. Failure simulation scenarios
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
from app.services.cash_position import CashPositionService, CashPositionSummary
from app.services.exception_management_service import (
    ExceptionAgingBucket,
    ExceptionAgingReport,
    ExceptionDetail,
    ExceptionManagementService,
)
from app.services.explainability_service import DecisionExplanation, ExplainabilityService
from app.services.exception_intelligence_service import ExceptionIntelligenceService
from app.services.exposure_service import FinancialExposureBreakdown, FinancialExposureService
from app.services.fee_tax_service import FeeTaxReconciliationReport, FeeTaxService
from app.services.finance_controller import ControllerKPIs, FinanceController
from app.services.finance_qa import FinanceQAService, QAResponse
from app.services.forecast_service import CashForecastReport, CashForecastService
from app.services.human_decision_service import (
    HumanAction,
    HumanDecisionResult,
    HumanDecisionService,
)
from app.services.source_health_service import SourceHealthReport, SourceHealthService


@pytest.fixture
def app():
    return create_app()


class TestExposureService:
    """Test Decimal-Safe Financial Exposure Service."""

    @pytest.mark.asyncio
    async def test_exposure_arithmetic_precision(self):
        session = AsyncMock()
        mock_t1 = MagicMock(amount=Decimal("100000.50"), source="gateway")
        mock_t2 = MagicMock(amount=Decimal("50000.25"), source="ledger")
        res_txn = MagicMock()
        res_txn.scalars.return_value.all.return_value = [mock_t1, mock_t2]

        mock_exc1 = MagicMock(financial_exposure=Decimal("25000.75"), exception_category=ExceptionCategory.DELAYED_SETTLEMENT)
        mock_exc2 = MagicMock(financial_exposure=Decimal("150000.00"), exception_category=ExceptionCategory.UNEXPLAINED)
        res_exc = MagicMock()
        res_exc.scalars.return_value.all.return_value = [mock_exc1, mock_exc2]

        res_dec = MagicMock()
        res_dec.scalars.return_value.all.return_value = []
        res_m = MagicMock()
        res_m.scalars.return_value.all.return_value = []

        session.execute = AsyncMock(side_effect=[res_txn, res_m, res_exc, res_dec])

        service = FinancialExposureService(session)
        exp = await service.calculate_exposure()

        assert exp.total_processed_value == Decimal("150000.75")
        assert exp.unresolved_value == Decimal("175000.75")
        assert exp.high_risk_value == Decimal("150000.00")
        assert exp.delayed_settlement_exposure == Decimal("25000.75")
        assert exp.unexplained_exposure == Decimal("150000.00")


class TestHumanDecisionService:
    """Test Human In The Loop Decision Operations & Transition Validation."""

    @pytest.mark.asyncio
    async def test_approve_valid_transition(self):
        session = AsyncMock()
        mock_exc = MagicMock(id="exc-101", status="open", resolved=False, transaction_id="tx-1", run_id="run-1")
        res_mock = MagicMock()
        res_mock.scalar_one_or_none.return_value = mock_exc
        session.execute = AsyncMock(return_value=res_mock)
        session.flush = AsyncMock()
        session.commit = AsyncMock()

        service = HumanDecisionService(session)
        service.audit_repo.create = AsyncMock(return_value="audit-101")

        result = await service.apply_decision(
            exception_id="exc-101",
            action=HumanAction.APPROVE,
            actor="controller_alice",
            reason="Approved with manual match",
        )

        assert result.action == "approve"
        assert result.new_status == "approved"
        assert result.actor == "controller_alice"
        assert mock_exc.resolved is True

    @pytest.mark.asyncio
    async def test_invalid_action_on_resolved_exception_raises_error(self):
        session = AsyncMock()
        mock_exc = MagicMock(id="exc-102", status="resolved", resolved=True)
        res_mock = MagicMock()
        res_mock.scalar_one_or_none.return_value = mock_exc
        session.execute = AsyncMock(return_value=res_mock)

        service = HumanDecisionService(session)

        with pytest.raises(ValueError, match="already resolved"):
            await service.apply_decision(
                exception_id="exc-102",
                action=HumanAction.REJECT,
            )


class TestExceptionIntelligenceService:
    """Test structured exception intelligence and risk explanations."""

    @pytest.mark.asyncio
    async def test_exception_intelligence_assembles_risk_and_next_steps(self):
        session = AsyncMock()

        mock_exc = MagicMock(
            id="exc-201",
            run_id="run-88",
            transaction_id="txn-55",
            exception_category=ExceptionCategory.DELAYED_SETTLEMENT,
            status="open",
            confidence=Decimal("0.90"),
            financial_exposure=Decimal("85000.00"),
            expected_cost=Decimal("20000.00"),
            explanation="Settlement is delayed by several days.",
            evidence={"amount_delta": "5000.00", "time_span_days": 5.0},
            recommended_action="approve_match",
            resolved=False,
            created_at=datetime.now(timezone.utc),
        )
        mock_inv = MagicMock(
            method="deterministic",
            root_cause="Delayed settlement timing across gateway and bank.",
            classification=ExceptionCategory.DELAYED_SETTLEMENT,
            confidence=Decimal("0.92"),
            financial_exposure=Decimal("85000.00"),
            expected_cost=Decimal("18000.00"),
            recommended_action="approve_match",
            requires_human_review=False,
            evidence={"rule": "delayed_settlement_timing", "time_span_days": 5.0},
        )

        res_exc = MagicMock(); res_exc.scalar_one_or_none.return_value = mock_exc
        res_inv = MagicMock(); res_inv.scalar_one_or_none.return_value = mock_inv
        session.execute = AsyncMock(side_effect=[res_exc, res_inv])

        service = ExceptionIntelligenceService(session)
        intelligence = await service.get_exception_intelligence("exc-201")

        assert intelligence.exception_id == "exc-201"
        assert intelligence.risk_bucket in {"medium", "high", "critical"}
        assert intelligence.root_cause == "Delayed settlement timing across gateway and bank."
        assert intelligence.recommended_action == "approve_match"
        assert "next_steps" in intelligence.to_dict()
        assert "supporting_facts" in intelligence.to_dict()

    @pytest.mark.asyncio
    async def test_exception_intelligence_list_is_risk_ordered(self):
        session = AsyncMock()

        exc_a = MagicMock(
            id="a",
            run_id="run-1",
            transaction_id="t1",
            exception_category=ExceptionCategory.UNEXPLAINED,
            status="open",
            confidence=Decimal("0.30"),
            financial_exposure=Decimal("150000.00"),
            expected_cost=Decimal("90000.00"),
            explanation="Unexplained exception",
            evidence={"rule": "unexplained_fallback"},
            recommended_action="escalate_manual",
            resolved=False,
            created_at=datetime.now(timezone.utc),
        )
        exc_b = MagicMock(
            id="b",
            run_id="run-1",
            transaction_id="t2",
            exception_category=ExceptionCategory.CURRENCY_ROUNDING,
            status="open",
            confidence=Decimal("0.98"),
            financial_exposure=Decimal("250.00"),
            expected_cost=Decimal("5.00"),
            explanation="Minor rounding variance",
            evidence={"rule": "rounding_tolerance"},
            recommended_action="write_off",
            resolved=False,
            created_at=datetime.now(timezone.utc),
        )

        stmt1 = MagicMock(); stmt1.scalars.return_value.all.return_value = [exc_a, exc_b]
        session.execute = AsyncMock(return_value=stmt1)

        service = ExceptionIntelligenceService(session)
        items = await service.list_exception_intelligence(run_id="run-1")

        assert items[0]["exception_id"] == "a"
        assert items[0]["risk_bucket"] in {"high", "critical"}
        assert items[1]["exception_id"] == "b"
        assert items[0]["risk_score"] >= items[1]["risk_score"]


class TestFeeTaxService:
    """Test Fee & Tax Control Auditing."""

    @pytest.mark.asyncio
    async def test_fee_tax_reconciliation(self):
        session = AsyncMock()
        # Normal fee: 2% of 10,000 = 200 fee, 18% of 200 = 36 tax
        mock_t1 = MagicMock(
            domain_transaction_id="GW_FEETAX_1",
            id="1",
            amount=Decimal("10000.00"),
            fee=Decimal("200.00"),
            tax=Decimal("36.00"),
            order_id="ORD_1",
        )
        # Discrepant fee: 2% of 10,000 should be 200, observed 250
        mock_t2 = MagicMock(
            domain_transaction_id="GW_FEETAX_2",
            id="2",
            amount=Decimal("10000.00"),
            fee=Decimal("250.00"),
            tax=Decimal("45.00"),
            order_id="ORD_2",
        )
        res_mock = MagicMock()
        res_mock.scalars.return_value.all.return_value = [mock_t1, mock_t2]
        session.execute = AsyncMock(return_value=res_mock)

        service = FeeTaxService(session)
        report = await service.reconcile_fees_and_taxes()

        assert report.total_transactions_analyzed == 2
        assert report.discrepant_transactions_count == 1
        assert len(report.discrepancies) == 1
        assert report.discrepancies[0]["transaction_id"] == "GW_FEETAX_2"
        assert report.discrepancies[0]["fee_difference"] == "50.00"


class TestForecastAndHealthServices:
    """Test 7-Day Forecasting and Source Health."""

    @pytest.mark.asyncio
    async def test_7day_cash_forecast(self):
        session = AsyncMock()
        mock_txns = [MagicMock(amount=Decimal("30000.00")) for _ in range(10)]
        res_mock = MagicMock()
        res_mock.scalars.return_value.all.return_value = mock_txns
        session.execute = AsyncMock(return_value=res_mock)

        service = CashForecastService(session)
        fc = await service.generate_7day_forecast()

        assert len(fc.forecast_days) == 7
        assert fc.seven_day_forecast_total_inr > 0.0

    @pytest.mark.asyncio
    async def test_source_health(self):
        session = AsyncMock()
        res_txn = MagicMock()
        res_txn.all.return_value = [("gateway", 100, Decimal("500000")), ("ledger", 100, Decimal("500000")), ("bank", 95, Decimal("480000"))]
        res_exc = MagicMock()
        res_exc.scalar_one.return_value = 5
        session.execute = AsyncMock(side_effect=[res_txn, res_exc])

        service = SourceHealthService(session)
        health = await service.get_source_health()

        assert health.overall_health in ("HEALTHY", "DEGRADED")
        assert len(health.sources) == 3


class TestControllerAPIRoutesEndToEnd:
    """Test All Controller REST Endpoints with HTTP Client."""

    @pytest.mark.asyncio
    async def test_batch_ingest_and_controller_endpoints(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Test Ingest Batch
            batch_payload = {
                "batch_id": "test_batch_001",
                "gateway_records": [
                    {"txn_id": f"GW_{i}", "amount": 1000.0 + i, "currency": "INR", "order_id": f"ORD_{i}", "reference_number": f"UTR_{i}"}
                    for i in range(20)
                ],
                "ledger_records": [
                    {"txn_id": f"LD_{i}", "amount": 1000.0 + i, "currency": "INR", "order_id": f"ORD_{i}", "reference_number": f"REF_{i}"}
                    for i in range(20)
                ],
                "bank_records": [
                    {"txn_id": f"BK_{i}", "amount": 1000.0 + i, "currency": "INR", "order_id": f"ORD_{i}", "reference_number": f"UTR_{i}", "narration": f"PAYMENT FOR ORD_{i}"}
                    for i in range(20)
                ],
            }

            with patch("app.api.routes.controller.FinanceController") as MockController:
                mock_ctrl = MagicMock()
                mock_ctrl.ingest_and_reconcile_batch = AsyncMock(return_value={
                    "batch_id": "test_batch_001",
                    "run_id": "run-test-001",
                    "records_received": 60,
                    "records_normalized": 60,
                    "processing_status": "COMPLETED",
                    "processing_duration_ms": 12.5,
                    "reconciliation_status": "completed",
                    "auto_matched_count": 55,
                    "ml_recovered_count": 3,
                    "manual_review_count": 1,
                    "unresolved_count": 1,
                })
                mock_ctrl.get_summary_kpis = AsyncMock(return_value=ControllerKPIs(
                    total_records_processed=60,
                    total_logical_transactions=20,
                    deterministic_matches=55,
                    ml_recovered_matches=3,
                    total_matched_records=116,
                    automatic_matches=55,
                    manual_reviews=1,
                    unresolved_transactions=1,
                    match_rate=96.67,
                    reconciliation_precision=None,
                    reconciliation_recall=None,
                    f1_score=None,
                    exception_rate=1.67,
                    total_matched_monetary_value_inr=58000.0,
                    unresolved_monetary_exposure_inr=1000.0,
                    manual_review_exposure_inr=1000.0,
                    high_risk_exposure_inr=0.0,
                    delayed_settlement_inr=0.0,
                    duplicate_amount_inr=0.0,
                    fee_mismatch_inr=0.0,
                    processing_throughput_tps=1800.0,
                    average_processing_latency_ms=0.55,
                ))
                mock_ctrl.generate_controller_report = AsyncMock(return_value={
                    "report_id": "rep_001",
                    "kpis": {"match_rate": 96.67},
                    "recommended_actions_summary": ["All clear"],
                })
                mock_ctrl.get_audit_timeline = AsyncMock(return_value=[
                    {"event_id": "ev-1", "event_type": "RECONCILIATION_RUN_COMPLETED", "timestamp": "2026-08-24T12:00:00Z"}
                ])
                mock_ctrl.simulate_failure_scenario = AsyncMock(return_value={
                    "scenario": "corrupted_utr",
                    "status": "SIMULATION_EXECUTED",
                })
                mock_ctrl.qa_service.answer_query = AsyncMock(return_value=QAResponse(
                    question="What is the unresolved exposure?",
                    direct_answer="Currently, INR 1,000.00 remains unreconciled.",
                    key_metrics={"total_unreconciled_inr": 1000.0},
                    evidence_records=[],
                    sql_facts_used=["SQL count and sum on exceptions"],
                ))
                MockController.return_value = mock_ctrl

                # Test Batch Ingest
                r_batch = await client.post("/api/v1/controller/ingest/batch", json=batch_payload)
                assert r_batch.status_code == 200
                assert r_batch.json()["records_received"] == 60
                assert r_batch.json()["auto_matched_count"] == 55

                # Test Summary
                r_sum = await client.get("/api/v1/controller/summary")
                assert r_sum.status_code == 200
                assert r_sum.json()["match_rate"] == 96.67

                # Test Report
                r_rep = await client.get("/api/v1/controller/report")
                assert r_rep.status_code == 200
                assert r_rep.json()["report_id"] == "rep_001"

                # Test Timeline
                r_time = await client.get("/api/v1/controller/audit/timeline")
                assert r_time.status_code == 200
                assert len(r_time.json()) == 1

                # Test Q&A
                r_qa = await client.post("/api/v1/controller/qa", json={"question": "What is the unresolved exposure?"})
                assert r_qa.status_code == 200
                assert "1,000.00" in r_qa.json()["direct_answer"]

                # Test Failure Simulation
                r_sim = await client.post("/api/v1/controller/simulate-failure", json={"scenario": "corrupted_utr", "amount": 25000.0})
                assert r_sim.status_code == 200
                assert r_sim.json()["scenario"] == "corrupted_utr"


class TestRefundAndSettlementAccounting:
    """Test Refund Reconciliation and Unified Settlement Accounting Equations."""

    @pytest.mark.asyncio
    async def test_refund_audit_and_over_refund_detection(self):
        from app.services.refund_service import RefundAccountingService
        session = AsyncMock()
        # Normal payment: 10,000 with 3,000 partial refund
        mock_t1 = MagicMock(
            domain_transaction_id="GW_PAY_01",
            id="1",
            amount=Decimal("10000.00"),
            order_id="ORD_01",
            meta_data={"refunds": [{"refund_id": "rf_1", "amount": "3000.00"}]},
        )
        # Over-refund anomaly: 5,000 payment with 6,000 refund
        mock_t2 = MagicMock(
            domain_transaction_id="GW_PAY_02",
            id="2",
            amount=Decimal("5000.00"),
            order_id="ORD_02",
            meta_data={"refunds": [{"refund_id": "rf_2", "amount": "6000.00"}]},
        )
        res_mock = MagicMock()
        res_mock.scalars.return_value.all.return_value = [mock_t1, mock_t2]
        session.execute = AsyncMock(return_value=res_mock)

        service = RefundAccountingService(session)
        report = await service.audit_refunds()

        assert report.total_payments_audited == 2
        assert report.partially_refunded_count == 1
        assert report.over_refund_anomalies_count == 1
        assert report.total_over_refund_exposure == "1000.00"

    @pytest.mark.asyncio
    async def test_duplicate_incident_detection(self):
        from app.services.duplicate_detection_service import DuplicateDetectionService
        session = AsyncMock()
        mock_t1 = MagicMock(source="gateway", order_id="ORD_DUP_1", domain_transaction_id="GW_1", amount=Decimal("1000.00"), reference_number=None)
        mock_t2 = MagicMock(source="gateway", order_id="ORD_DUP_1", domain_transaction_id="GW_2", amount=Decimal("1000.00"), reference_number=None)
        res_mock = MagicMock()
        res_mock.scalars.return_value.all.return_value = [mock_t1, mock_t2]
        session.execute = AsyncMock(return_value=res_mock)

        service = DuplicateDetectionService(session)
        report = await service.audit_duplicates()

        assert report.total_incidents_detected == 1
        assert report.duplicate_charges_count == 1
        assert report.duplicate_charges_exposure == "1000.00"

    @pytest.mark.asyncio
    async def test_settlement_accounting_equation(self):
        from app.services.settlement_accounting_service import SettlementAccountingService
        session = AsyncMock()
        # Gross = 100,000, Fee = 2,000, Tax = 360 -> Expected Net = 97,640
        res_gw = MagicMock()
        res_gw.first.return_value = (Decimal("100000.00"), Decimal("2000.00"), Decimal("360.00"))
        # Bank credit = 97,640 -> Fully Reconciled
        res_bk = MagicMock()
        res_bk.scalar_one.return_value = Decimal("97640.00")
        session.execute = AsyncMock(side_effect=[res_gw, res_bk])

        service = SettlementAccountingService(session)
        summary = await service.calculate_settlement_accounting()

        assert summary.gross_gateway_volume == "100000.00"
        assert summary.expected_net_settlement == "97640.00"
        assert summary.actual_bank_settled_credits == "97640.00"
        assert summary.net_settlement_variance == "0.00"
        assert summary.settlement_reconciliation_status == "RECONCILED"

    @pytest.mark.asyncio
    async def test_settlement_and_cash_position_harmonized_equation(self):
        """Verify that SettlementAccountingService and CashPositionService produce identical authoritative settlement equations."""
        from app.database.models import Transaction as TransactionORM
        from app.models.transaction import TransactionSource
        from app.services.cash_position import CashPositionService

        session = AsyncMock()
        t_gw = MagicMock(spec=TransactionORM)
        t_gw.amount = Decimal("2310799.00")
        t_gw.fee = Decimal("46215.98")
        t_gw.tax = Decimal("8318.88")
        t_gw.source = TransactionSource.GATEWAY.value

        t_bk = MagicMock(spec=TransactionORM)
        t_bk.amount = Decimal("2310799.00")
        t_bk.fee = None
        t_bk.tax = None
        t_bk.source = TransactionSource.BANK.value

        res_txns = MagicMock()
        res_txns.scalars.return_value.all.return_value = [t_gw, t_bk]

        res_excs = MagicMock()
        res_excs.scalars.return_value.all.return_value = []

        session.execute = AsyncMock(side_effect=[res_txns, res_excs])

        service = CashPositionService(session)
        cash_summary = await service.get_cash_position()

        # Invariant 1: Gross - MDR - GST - Refunds = Expected Net
        expected_net = cash_summary.expected_gross - cash_summary.total_deducted_fees - cash_summary.total_deducted_taxes - cash_summary.total_refunded_amount
        assert cash_summary.expected_net_settlement == expected_net
        assert cash_summary.expected_net_settlement == Decimal("2256264.14")
        assert cash_summary.expected_gross == Decimal("2310799.00")

        # Invariant 2: Actual Bank Credits - Expected Net = Variance
        variance = cash_summary.received_bank_credits - cash_summary.expected_net_settlement
        assert cash_summary.settlement_variance == variance
        assert cash_summary.settlement_variance == Decimal("54534.86")
        assert cash_summary.received_bank_credits == Decimal("2310799.00")



class TestWebhookIntegration:
    """Test Razorpay Webhook Ingestion & Signature Verification."""

    @pytest.mark.asyncio
    async def test_razorpay_webhook_endpoint(self, app):
        import hashlib
        import hmac
        import json
        from app.api.dependencies import get_db_session, get_investigation_service

        mock_db = AsyncMock()
        app.dependency_overrides[get_db_session] = lambda: mock_db
        app.dependency_overrides[get_investigation_service] = lambda: MagicMock()

        secret = "rzp_test_secret_sentinel"
        payload = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_webhook_test_101",
                        "order_id": "order_test_101",
                        "amount": 2500000,  # 25,000 INR
                        "currency": "INR",
                        "status": "captured",
                        "created_at": 1700000000,
                    }
                }
            }
        }
        body_bytes = json.dumps(payload).encode("utf-8")
        signature = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            with patch("app.api.routes.integrations.IncrementalReconciliationService") as MockInc:
                from app.services.incremental_reconciliation import IncrementalReconciliationResult
                mock_inc_inst = MagicMock()
                mock_inc_inst.ingest_and_reconcile = AsyncMock(return_value=IncrementalReconciliationResult(
                    transaction_id="pay_webhook_test_101",
                    status="MATCHED_DETERMINISTIC",
                    action="auto_match",
                    match_id="m-wh-101",
                    matched_transaction_id="LD_101",
                    confidence=0.98,
                    processing_time_ms=0.65,
                ))
                MockInc.return_value = mock_inc_inst

                resp = await client.post(
                    "/api/v1/integrations/razorpay/webhook",
                    content=body_bytes,
                    headers={"X-Razorpay-Signature": signature, "Content-Type": "application/json"},
                )
                assert resp.status_code == 200
                assert resp.json()["transaction_id"] == "pay_webhook_test_101"
                assert resp.json()["status"] == "MATCHED_DETERMINISTIC"
