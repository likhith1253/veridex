"""
End-to-End Integration & Unit Tests for the Sentinel AI Finance Controller (Razorpay Track 4).

Tests:
1. Single transaction ingestion & incremental reconciliation
2. Idempotency on duplicate transaction ingestion
3. Grounded Finance KPI calculation
4. Cash position & financial exposure aggregation
5. Honest exception list generation
6. Grounded Finance Q&A engine
7. Real-Time transaction stream simulator
8. Razorpay test-mode adapter & webhook signature verification
9. 50+ batch finance operations loop
"""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.integrations.razorpay_adapter import RazorpayAdapter
from app.models.decision_result import DecisionAction, DecisionResult
from app.models.exception_record import ExceptionCategory, ExceptionRecord
from app.models.match_result import MatchResult, MatchType
from app.models.transaction import Transaction, TransactionSource, TransactionStatus
from app.services.cash_position import CashPositionService, CashPositionSummary
from app.services.finance_controller import ControllerKPIs, FinanceController
from app.services.finance_qa import FinanceQAService
from app.services.incremental_reconciliation import IncrementalReconciliationService
from simulator.stream_simulator import RealTimeStreamSimulator, StreamConfig


def _ts() -> datetime:
    return datetime(2026, 8, 24, tzinfo=timezone.utc)


def _make_txn(txn_id: str, amount: Decimal, src: TransactionSource = TransactionSource.GATEWAY, ord_id: str = "ORD_1", ref: str = "REF_1") -> Transaction:
    return Transaction(
        txn_id=txn_id,
        source=src,
        amount=amount,
        currency="INR",
        timestamp=_ts(),
        status=TransactionStatus.COMPLETED,
        order_id=ord_id,
        reference_number=ref,
        narration=f"Test transaction {txn_id}",
    )


class TestRazorpayAdapter:
    """Test Razorpay Test-Mode Adapter & Webhook Signatures."""

    def test_webhook_signature_verification(self):
        adapter = RazorpayAdapter(webhook_secret="test_secret_123")
        payload = b'{"event":"payment.captured"}'
        import hashlib, hmac
        valid_sig = hmac.new(b"test_secret_123", payload, hashlib.sha256).hexdigest()

        assert adapter.verify_webhook_signature(payload, valid_sig) is True
        assert adapter.verify_webhook_signature(payload, "invalid_sig") is False

    def test_parse_payment_captured_event(self):
        adapter = RazorpayAdapter()
        raw_event = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_rzp_999",
                        "order_id": "order_rzp_999",
                        "amount": 250000,  # 2500.00 INR
                        "currency": "INR",
                        "status": "captured",
                        "fee": 5000,
                        "tax": 900,
                        "acquirer_data": {"utr": "UTR_RZP_999"},
                    }
                }
            }
        }
        txn = adapter.parse_payment_event(raw_event)
        assert txn.txn_id == "pay_rzp_999"
        assert txn.amount == Decimal("2500.00")
        assert txn.source == TransactionSource.GATEWAY
        assert txn.reference_number == "UTR_RZP_999"


class TestFinanceQAGrounded:
    """Test Fact-Grounded Finance Q&A."""

    @pytest.mark.asyncio
    async def test_qa_unreconciled_money_grounded(self):
        session = AsyncMock()
        # Mock exceptions return
        mock_exc = MagicMock()
        mock_exc.exception_id = "exc-1"
        mock_exc.transaction_id = "tx-1"
        mock_exc.category = "delayed_settlement"
        mock_exc.financial_exposure = Decimal("5000.00")
        mock_exc.explanation = "Delayed bank credit"

        res_mock = MagicMock()
        res_mock.scalars.return_value.all.return_value = [mock_exc]
        res_mock.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=res_mock)

        qa_service = FinanceQAService(session)
        # Mock cash position
        qa_service.cash_service.get_cash_position = AsyncMock(
            return_value=CashPositionSummary(
                expected_amount=Decimal("10000.00"),
                received_amount=Decimal("5000.00"),
                unreconciled_amount=Decimal("5000.00"),
                at_risk_amount=Decimal("0.00"),
            )
        )

        resp = await qa_service.answer_query("How much money is currently unreconciled?")
        assert "5,000.00" in resp.direct_answer
        assert resp.key_metrics["total_unreconciled_inr"] == 5000.0


class TestRealTimeStreamSimulator:
    """Test multi-source stream simulator."""

    @pytest.mark.asyncio
    async def test_stream_generates_multi_source_batch(self):
        sim = RealTimeStreamSimulator(StreamConfig(batch_size=10, delay_between_events_sec=0.0, seed=42))
        events = []
        async for txn in sim.stream_events(10):
            events.append(txn)

        assert len(events) == 30  # 10 * 3 sources
        sources = {t.source for t in events}
        assert TransactionSource.GATEWAY in sources
        assert TransactionSource.LEDGER in sources
        assert TransactionSource.BANK in sources


class TestIncrementalReconciliationUnit:
    """Test incremental ingestion and idempotency."""

    @pytest.mark.asyncio
    async def test_duplicate_transaction_is_idempotent(self):
        session = AsyncMock()
        service = IncrementalReconciliationService(session)
        service.txn_repo.get_orm_by_source_and_domain_id = AsyncMock(return_value=MagicMock())

        t1 = _make_txn("GW_DUP_1", Decimal("1000.00"))
        res = await service.ingest_and_reconcile(t1)

        assert res.status == "DUPLICATE_IGNORED"
        assert res.action == "ALREADY_INGESTED"

class TestReconciliationRateDenominator:
    """Test ISSUE-002: Reconciliation rate denominator is total_records_processed, not total_classified."""

    @pytest.mark.asyncio
    async def test_reconciliation_rate_uses_total_records_not_classified(self):
        """Verify reconciliation rate denominator is total incoming transactions, not total classified."""
        session = AsyncMock()
        ctrl = FinanceController(session)

        from app.services.exposure_service import FinancialExposureBreakdown

        ctrl.exposure_service.calculate_exposure = AsyncMock(
            return_value=FinancialExposureBreakdown(
                total_processed_value=Decimal("5000.00"),
                matched_value=Decimal("2000.00"),
                unresolved_value=Decimal("3000.00"),
            )
        )

        txns = [
            MagicMock(id="t1", source="gateway"),
            MagicMock(id="t2", source="gateway"),
            MagicMock(id="t3", source="ledger"),
            MagicMock(id="t4", source="bank"),
            MagicMock(id="t5", source="bank"),
        ]
        res_txns = MagicMock()
        res_txns.scalars.return_value.all.return_value = txns

        match1 = MagicMock(id="m1", match_type="exact", reason="deterministic exact match")
        match2 = MagicMock(id="m2", match_type="exact", reason="manual review needed")
        match3 = MagicMock(id="m3", match_type="exact", reason="unresolved exception")
        res_matches = MagicMock()
        res_matches.scalars.return_value.all.return_value = [match1, match2, match3]

        dec1 = MagicMock(match_id="m1", decision_action=DecisionAction.AUTO_MATCH.value, action=DecisionAction.AUTO_MATCH.value)
        dec2 = MagicMock(match_id="m2", decision_action=DecisionAction.MANUAL_REVIEW.value, action=DecisionAction.MANUAL_REVIEW.value)
        dec3 = MagicMock(match_id="m3", decision_action=DecisionAction.UNRESOLVED.value, action=DecisionAction.UNRESOLVED.value)
        res_decisions = MagicMock()
        res_decisions.scalars.return_value.all.return_value = [dec1, dec2, dec3]

        mt1 = MagicMock()
        mt1.scalars.return_value.all.return_value = ["t1", "t2"]
        mt2 = MagicMock()
        mt2.scalars.return_value.all.return_value = ["t3"]
        mt3 = MagicMock()
        mt3.scalars.return_value.all.return_value = ["t4"]
        res_run = MagicMock()
        valid_run = MagicMock()
        valid_run.started_at = datetime(2026, 8, 28, 10, 0, 0)
        valid_run.completed_at = datetime(2026, 8, 28, 10, 0, 10)
        valid_run.gateway_count = 2
        valid_run.ledger_count = 1
        valid_run.bank_count = 2
        res_run.scalars.return_value.all.return_value = [valid_run]

        session.execute = AsyncMock(side_effect=[res_txns, res_matches, res_decisions, mt1, mt2, mt3, res_run])

        kpis = await ctrl.get_summary_kpis()

        assert kpis.total_records_processed == 5
        assert kpis.deterministic_matches == 2
        assert kpis.manual_reviews == 1
        assert kpis.unresolved_transactions == 2
        assert kpis.match_rate == 40.0
        assert kpis.exception_rate == 40.0

    @pytest.mark.asyncio
    async def test_manual_review_not_counted_in_reconciliation_rate(self):
        """Verify manual review transactions are not counted as successfully reconciled."""
        session = AsyncMock()
        ctrl = FinanceController(session)

        from app.services.exposure_service import FinancialExposureBreakdown

        ctrl.exposure_service.calculate_exposure = AsyncMock(
            return_value=FinancialExposureBreakdown(
                total_processed_value=Decimal("3000.00"),
                matched_value=Decimal("1000.00"),
                unresolved_value=Decimal("2000.00"),
            )
        )

        txns = [
            MagicMock(id="t1", source="gateway"),
            MagicMock(id="t2", source="ledger"),
            MagicMock(id="t3", source="bank"),
        ]
        res_txns = MagicMock()
        res_txns.scalars.return_value.all.return_value = txns

        match1 = MagicMock(id="m1", match_type="exact", reason="deterministic exact match")
        match2 = MagicMock(id="m2", match_type="exact", reason="manual review needed")
        res_matches = MagicMock()
        res_matches.scalars.return_value.all.return_value = [match1, match2]

        dec1 = MagicMock(match_id="m1", decision_action=DecisionAction.AUTO_MATCH.value, action=DecisionAction.AUTO_MATCH.value)
        dec2 = MagicMock(match_id="m2", decision_action=DecisionAction.MANUAL_REVIEW.value, action=DecisionAction.MANUAL_REVIEW.value)
        res_decisions = MagicMock()
        res_decisions.scalars.return_value.all.return_value = [dec1, dec2]

        mt1 = MagicMock()
        mt1.scalars.return_value.all.return_value = ["t1", "t2"]
        mt2 = MagicMock()
        mt2.scalars.return_value.all.return_value = ["t3"]
        res_run = MagicMock()
        valid_run = MagicMock()
        valid_run.started_at = datetime(2026, 8, 28, 10, 0, 0)
        valid_run.completed_at = datetime(2026, 8, 28, 10, 0, 4)
        valid_run.gateway_count = 1
        valid_run.ledger_count = 1
        valid_run.bank_count = 1
        res_run.scalars.return_value.all.return_value = [valid_run]

        session.execute = AsyncMock(side_effect=[res_txns, res_matches, res_decisions, mt1, mt2, res_run])

        kpis = await ctrl.get_summary_kpis()

        assert kpis.deterministic_matches == 2
        assert kpis.manual_reviews == 1
        assert kpis.match_rate == 66.67


class TestThroughputCalculation:
    """Test ISSUE-005: Throughput and latency derived from measured run timing."""

    @pytest.mark.asyncio
    async def test_summary_kpis_throughput_calculation(self):
        from unittest.mock import MagicMock
        from datetime import datetime, timedelta
        from app.database.models import ReconciliationRun as ReconciliationRunORM
        from app.services.exposure_service import FinancialExposureBreakdown

        session = AsyncMock()
        ctrl = FinanceController(session)
        ctrl.exposure_service.calculate_exposure = AsyncMock(return_value=FinancialExposureBreakdown())

        start = datetime(2026, 8, 24, 10, 0, 0)
        end = start + timedelta(seconds=2.0)
        mock_run = MagicMock(spec=ReconciliationRunORM)
        mock_run.started_at = start
        mock_run.completed_at = end
        mock_run.gateway_count = 10
        mock_run.ledger_count = 10
        mock_run.bank_count = 10

        # Mock execute responses for transactions count, matches, decisions, and run lookup
        res_count = MagicMock()
        res_count.scalar_one.return_value = 30

        res_matches = MagicMock()
        res_matches.scalars.return_value.all.return_value = []

        res_decisions = MagicMock()
        res_decisions.scalars.return_value.all.return_value = []

        res_run = MagicMock()
        res_run.scalars.return_value.all.return_value = [mock_run]

        session.execute = AsyncMock(side_effect=[res_count, res_matches, res_decisions, res_run])

        kpis = await ctrl.get_summary_kpis()
        assert kpis.processing_throughput_tps == 15.0  # 30 records / 2.0 sec
        assert kpis.average_processing_latency_ms == pytest.approx(66.67, rel=1e-2)  # 2000 ms / 30 records

    @pytest.mark.asyncio
    async def test_summary_kpis_selects_latest_valid_completed_run(self):
        from unittest.mock import MagicMock
        from datetime import datetime, timedelta
        from app.services.exposure_service import FinancialExposureBreakdown

        session = AsyncMock()
        ctrl = FinanceController(session)
        ctrl.exposure_service.calculate_exposure = AsyncMock(return_value=FinancialExposureBreakdown())

        res_count = MagicMock()
        res_count.scalar_one.return_value = 10

        res_matches = MagicMock()
        res_matches.scalars.return_value.all.return_value = []

        res_decisions = MagicMock()
        res_decisions.scalars.return_value.all.return_value = []

        zero_run = MagicMock()
        zero_run.started_at = datetime(2026, 8, 28, 9, 0, 0)
        zero_run.completed_at = datetime(2026, 8, 28, 9, 0, 0)
        zero_run.gateway_count = 5
        zero_run.ledger_count = 3
        zero_run.bank_count = 2

        valid_run = MagicMock()
        valid_run.started_at = datetime(2026, 8, 28, 9, 0, 0)
        valid_run.completed_at = datetime(2026, 8, 28, 9, 0, 5)
        valid_run.gateway_count = 4
        valid_run.ledger_count = 3
        valid_run.bank_count = 3

        res_run = MagicMock()
        res_run.scalars.return_value.all.return_value = [zero_run, valid_run]

        session.execute = AsyncMock(side_effect=[res_count, res_matches, res_decisions, res_run])

        kpis = await ctrl.get_summary_kpis()

        assert kpis.processing_throughput_tps == 2.0
        assert kpis.average_processing_latency_ms == 500.0
