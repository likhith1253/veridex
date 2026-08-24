import os
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from dotenv import load_dotenv
import pytest
import pytest_asyncio
from pydantic import ValidationError

load_dotenv()

from app.database.models import (
    Exception as ExceptionORM,
    ExceptionCategory as ExceptionCategoryORM,
    ReconciliationRun as ReconciliationRunORM,
    ReconciliationRunStatus,
)
from app.database.repositories.investigation_repository import InvestigationRepository
from app.database.session import create_app_engine
from app.graph.investigation_graph import InvestigationGraphRunner
from app.graph.state import InvestigationStage, InvestigationState
from app.investigation.analyzer import DeterministicAnalysisResult, DeterministicAnalyzer
from app.investigation.evidence import (
    InvestigationContext,
    InvestigationContextBuilder,
    InvestigationEvidence,
    TransactionSnapshot,
)
from app.investigation.exposure import ExposureCalculator
from app.investigation.llm_client import FakeLLMClient, GeminiLLMClient
from app.investigation.retrieval import (
    FakeHistoricalRetriever,
    QdrantHistoricalRetriever,
)
from app.models.decision_result import DecisionAction, DecisionResult
from app.models.exception_record import ExceptionCategory
from app.models.investigation_result import (
    InvestigationConclusion,
    InvestigationMethod,
    InvestigationStatus,
)
from app.models.llm_result import (
    LLMEvidenceItem,
    LLMInvestigationResult,
    RecommendedAction,
)
from app.models.transaction import Transaction, TransactionSource, TransactionStatus
from app.risk.calculator import RiskCalculator
from app.risk.interface import RiskBucket, RiskInput, RiskOutput
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy import text


@pytest_asyncio.fixture
async def db_session():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL not set")

    engine = create_app_engine(database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.execute(text(
            "TRUNCATE TABLE investigations, audit_events, exception_transactions, match_transactions, "
            "decisions, exceptions, matches, reconciliation_items, reconciliation_runs, transactions CASCADE;"
        ))

    async with session_factory() as session:
        yield session

    await engine.dispose()


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def make_txn(
    txn_id: str,
    source: TransactionSource,
    amount: Decimal = Decimal("1000.00"),
    currency: str = "INR",
    timestamp: datetime = None,
    order_id: str = "ORD123",
    ref: str = "REF123",
    fee: Decimal = None,
    tax: Decimal = None,
) -> Transaction:
    return Transaction(
        txn_id=txn_id,
        source=source,
        amount=amount,
        currency=currency,
        timestamp=timestamp or datetime(2026, 8, 24, 10, 0, 0),
        order_id=order_id,
        reference_number=ref,
        narration="Test transaction",
        fee=fee,
        tax=tax,
        status=TransactionStatus.COMPLETED,
    )


# -------------------------------------------------------------------------
# A. DeterministicAnalyzer Tests
# -------------------------------------------------------------------------

class TestDeterministicAnalyzer:

    def test_duplicate_detection(self):
        t1 = make_txn("T1", TransactionSource.GATEWAY, Decimal("5000.00"), order_id="ORD1", ref="REF1")
        t2 = make_txn("T2", TransactionSource.GATEWAY, Decimal("5000.00"), order_id="ORD1", ref="REF1")
        ctx = InvestigationContextBuilder.build("EXC1", "RUN1", [t1, t2])
        res = DeterministicAnalyzer.analyze(ctx.evidence, [t1, t2])

        assert res.detected_category == ExceptionCategory.DUPLICATE_ENTRY
        assert res.recommended_action == "flag_duplicate"
        assert res.confidence >= Decimal("0.90")
        assert res.requires_llm_escalation is False

    def test_fee_mismatch_detection(self):
        # Gateway: 1000, fee: 20, tax: 3.60 -> Expected Bank: 976.40. Actual Bank: 970.00 (mismatch)
        t_gw = make_txn("T_GW", TransactionSource.GATEWAY, Decimal("1000.00"), fee=Decimal("20.00"), tax=Decimal("3.60"))
        t_bk = make_txn("T_BK", TransactionSource.BANK, Decimal("970.00"))
        ctx = InvestigationContextBuilder.build("EXC2", "RUN1", [t_gw, t_bk])
        res = DeterministicAnalyzer.analyze(ctx.evidence, [t_gw, t_bk])

        assert res.detected_category == ExceptionCategory.FEE_MISMATCH
        assert res.recommended_action == "request_credit_note"
        assert res.confidence >= Decimal("0.90")
        assert res.requires_llm_escalation is False

    def test_currency_rounding_detection(self):
        t1 = make_txn("T1", TransactionSource.GATEWAY, Decimal("1000.00"))
        t2 = make_txn("T2", TransactionSource.LEDGER, Decimal("1000.50"))
        ctx = InvestigationContextBuilder.build("EXC3", "RUN1", [t1, t2])
        res = DeterministicAnalyzer.analyze(ctx.evidence, [t1, t2])

        assert res.detected_category == ExceptionCategory.CURRENCY_ROUNDING
        assert res.recommended_action == "write_off"
        assert res.confidence >= Decimal("0.95")
        assert res.requires_llm_escalation is False

    def test_partial_refund_detection(self):
        t_gw = make_txn("T_GW", TransactionSource.GATEWAY, Decimal("5000.00"))
        t_ld = make_txn("T_LD", TransactionSource.LEDGER, Decimal("3500.00"))
        ctx = InvestigationContextBuilder.build("EXC4", "RUN1", [t_gw, t_ld])
        res = DeterministicAnalyzer.analyze(ctx.evidence, [t_gw, t_ld])

        assert res.detected_category == ExceptionCategory.PARTIAL_REFUND
        assert res.recommended_action == "approve_match"
        assert res.confidence >= Decimal("0.80")
        assert res.requires_llm_escalation is False

    def test_delayed_settlement_detection(self):
        t1 = make_txn("T1", TransactionSource.GATEWAY, Decimal("1000.00"), timestamp=datetime(2026, 8, 1, 10, 0, 0))
        t2 = make_txn("T2", TransactionSource.BANK, Decimal("1000.00"), timestamp=datetime(2026, 8, 6, 10, 0, 0))
        ctx = InvestigationContextBuilder.build("EXC5", "RUN1", [t1, t2])
        res = DeterministicAnalyzer.analyze(ctx.evidence, [t1, t2])

        assert res.detected_category == ExceptionCategory.DELAYED_SETTLEMENT
        assert res.recommended_action == "approve_match"
        assert res.confidence >= Decimal("0.85")

    def test_wrong_reference_detection(self):
        t1 = make_txn("T1", TransactionSource.GATEWAY, Decimal("1000.00"), order_id="ORD999", ref="REF_AAA")
        t2 = make_txn("T2", TransactionSource.BANK, Decimal("1000.00"), order_id="ORD999", ref="REF_BBB")
        ctx = InvestigationContextBuilder.build("EXC6", "RUN1", [t1, t2])
        res = DeterministicAnalyzer.analyze(ctx.evidence, [t1, t2])

        assert res.detected_category == ExceptionCategory.WRONG_REFERENCE
        assert res.recommended_action == "investigate_further"
        assert res.confidence >= Decimal("0.80")

    def test_ambiguous_decision_escalates(self):
        t1 = make_txn("T1", TransactionSource.GATEWAY, Decimal("1000.00"))
        t2 = make_txn("T2", TransactionSource.BANK, Decimal("1000.00"))
        decision = DecisionResult(
            transaction_ids=["T1", "T2"],
            action=DecisionAction.AMBIGUOUS,
            confidence=Decimal("0.50"),
            evidence={"margin": 0.02},
            reason="Ambiguous candidates with narrow margin",
        )
        ctx = InvestigationContextBuilder.build("EXC7", "RUN1", [t1, t2], decision=decision)
        res = DeterministicAnalyzer.analyze(ctx.evidence, [t1, t2], decision=decision)

        assert res.detected_category == ExceptionCategory.AMBIGUOUS_MATCH
        assert res.requires_llm_escalation is True

    def test_unexplained_fallback_escalates(self):
        # Discrepancy > 1.00 that doesn't fit refund/fee
        t1 = make_txn("T1", TransactionSource.GATEWAY, Decimal("1000.00"))
        t2 = make_txn("T2", TransactionSource.BANK, Decimal("1500.00"))
        ctx = InvestigationContextBuilder.build("EXC8", "RUN1", [t1, t2])
        res = DeterministicAnalyzer.analyze(ctx.evidence, [t1, t2])

        assert res.detected_category == ExceptionCategory.UNEXPLAINED
        assert res.requires_llm_escalation is True


# -------------------------------------------------------------------------
# B. RiskCalculator Tests
# -------------------------------------------------------------------------

class TestRiskCalculator:

    def test_all_risk_buckets(self):
        # LOW: < 10,000
        out_low = RiskCalculator.calculate(RiskInput(ExceptionCategory.CURRENCY_ROUNDING, Decimal("500.00"), Decimal("0.95")))
        assert out_low.risk_bucket == RiskBucket.LOW

        # MEDIUM: 10,000 - 50,000
        out_med = RiskCalculator.calculate(RiskInput(ExceptionCategory.FEE_MISMATCH, Decimal("25000.00"), Decimal("0.90")))
        assert out_med.risk_bucket == RiskBucket.MEDIUM

        # HIGH: 50,000 - 200,000
        out_high = RiskCalculator.calculate(RiskInput(ExceptionCategory.PARTIAL_REFUND, Decimal("100000.00"), Decimal("0.85")))
        assert out_high.risk_bucket == RiskBucket.HIGH

        # CRITICAL: > 200,000
        out_crit = RiskCalculator.calculate(RiskInput(ExceptionCategory.DUPLICATE_ENTRY, Decimal("300000.00"), Decimal("0.90")))
        assert out_crit.risk_bucket == RiskBucket.CRITICAL

    def test_boundary_values(self):
        # Exactly 10,000 -> MEDIUM
        out_10k = RiskCalculator.calculate(RiskInput(ExceptionCategory.FEE_MISMATCH, Decimal("10000.00"), Decimal("0.90")))
        assert out_10k.risk_bucket == RiskBucket.MEDIUM

        # Exactly 50,000 -> HIGH
        out_50k = RiskCalculator.calculate(RiskInput(ExceptionCategory.FEE_MISMATCH, Decimal("50000.00"), Decimal("0.90")))
        assert out_50k.risk_bucket == RiskBucket.HIGH

        # Exactly 200,000 -> CRITICAL
        out_200k = RiskCalculator.calculate(RiskInput(ExceptionCategory.FEE_MISMATCH, Decimal("200000.00"), Decimal("0.90")))
        assert out_200k.risk_bucket == RiskBucket.CRITICAL

    def test_duplicate_and_immediate_review(self):
        out = RiskCalculator.calculate(
            RiskInput(ExceptionCategory.DUPLICATE_ENTRY, Decimal("80000.00"), Decimal("0.95"), is_duplicate=True)
        )
        assert out.requires_immediate_review is True
        assert out.expected_cost > Decimal("0")


# -------------------------------------------------------------------------
# C. ExposureCalculator Tests
# -------------------------------------------------------------------------

class TestExposureCalculator:

    def test_exposure_calculation(self):
        t1 = make_txn("T1", TransactionSource.GATEWAY, Decimal("1000.00"))
        t2 = make_txn("T2", TransactionSource.BANK, Decimal("5000.00"))
        assert ExposureCalculator.calculate_exposure([t1, t2]) == Decimal("5000.00")
        assert ExposureCalculator.calculate_exposure([]) == Decimal("0")

    def test_should_escalate_to_llm(self):
        # High value with moderate confidence -> escalate
        should, reason = ExposureCalculator.should_escalate_to_llm(
            financial_exposure=Decimal("150000.00"),
            category=ExceptionCategory.WRONG_REFERENCE,
            deterministic_confidence=Decimal("0.70"),
            is_duplicate=False,
        )
        assert should is True

        # Unexplained -> escalate
        should, _ = ExposureCalculator.should_escalate_to_llm(
            financial_exposure=Decimal("5000.00"),
            category=ExceptionCategory.UNEXPLAINED,
            deterministic_confidence=Decimal("0.30"),
            is_duplicate=False,
        )
        assert should is True

        # Clean rounding low value -> no escalation
        should, _ = ExposureCalculator.should_escalate_to_llm(
            financial_exposure=Decimal("500.00"),
            category=ExceptionCategory.CURRENCY_ROUNDING,
            deterministic_confidence=Decimal("0.98"),
            is_duplicate=False,
        )
        assert should is False


# -------------------------------------------------------------------------
# D. InvestigationContextBuilder Tests
# -------------------------------------------------------------------------

class TestInvestigationContextBuilder:

    def test_context_construction(self):
        t_gw = make_txn("T_GW", TransactionSource.GATEWAY, Decimal("2000.00"), fee=Decimal("10.00"))
        t_ld = make_txn("T_LD", TransactionSource.LEDGER, Decimal("2000.00"))
        t_bk = make_txn("T_BK", TransactionSource.BANK, Decimal("1990.00"))

        ctx = InvestigationContextBuilder.build(
            exception_id="EXC_TEST",
            run_id="RUN_TEST",
            transactions=[t_gw, t_ld, t_bk],
        )

        assert ctx.exception_id == "EXC_TEST"
        assert ctx.run_id == "RUN_TEST"
        assert len(ctx.evidence.gateway_snapshots) == 1
        assert len(ctx.evidence.ledger_snapshots) == 1
        assert len(ctx.evidence.bank_snapshots) == 1
        assert ctx.evidence.expected_bank_amount == Decimal("1990.00")
        assert ctx.evidence.actual_bank_amount == Decimal("1990.00")
        assert ctx.evidence.has_fee_difference is False


# -------------------------------------------------------------------------
# E. LLM Output Validation Tests
# -------------------------------------------------------------------------

class TestLLMOutputValidation:

    def test_valid_structured_output(self):
        res = LLMInvestigationResult(
            root_cause="Duplicate settlement initiated due to timeout retry",
            classification="duplicate_entry",
            confidence=0.92,
            evidence=[
                LLMEvidenceItem(
                    observation="Two identical gateway settlements found within 3 seconds",
                    source="gateway",
                    relevance="Supports duplicate detection",
                )
            ],
            financial_exposure=Decimal("15000.00"),
            recommended_action=RecommendedAction.FLAG_DUPLICATE,
            requires_human_review=False,
            reasoning_summary="Observed two identical gateway records for the same internal order ID.",
        )
        assert res.classification == "duplicate_entry"
        assert res.confidence == 0.92

    def test_invalid_classification_rejected(self):
        with pytest.raises(ValidationError):
            LLMInvestigationResult(
                root_cause="Some arbitrary reason not in enum",
                classification="non_existent_category",
                confidence=0.80,
                evidence=[LLMEvidenceItem(observation="test", source="test", relevance="test")],
                financial_exposure=Decimal("100.00"),
                recommended_action=RecommendedAction.APPROVE_MATCH,
                requires_human_review=False,
                reasoning_summary="Valid reasoning summary description here.",
            )

    def test_invalid_confidence_rejected(self):
        with pytest.raises(ValidationError):
            LLMInvestigationResult(
                root_cause="Valid root cause description",
                classification="currency_rounding",
                confidence=1.50,  # Invalid: must be <= 1.0
                evidence=[LLMEvidenceItem(observation="test", source="test", relevance="test")],
                financial_exposure=Decimal("100.00"),
                recommended_action=RecommendedAction.WRITE_OFF,
                requires_human_review=False,
                reasoning_summary="Valid reasoning summary description here.",
            )


# -------------------------------------------------------------------------
# F. FakeLLMClient Tests
# -------------------------------------------------------------------------

class TestFakeLLMClient:

    @pytest.mark.asyncio
    async def test_fake_llm_deterministic_output(self):
        client = FakeLLMClient()
        ctx = {"category": "fee_mismatch", "financial_exposure": "1200.00", "transactions": [{"txn_id": "T1"}]}
        result = await client.reason(ctx)

        assert isinstance(result, LLMInvestigationResult)
        assert result.classification == "fee_mismatch"
        assert result.financial_exposure == Decimal("1200.00")
        assert client.invocation_count == 1

    @pytest.mark.asyncio
    async def test_fake_llm_raise_error(self):
        client = FakeLLMClient(raise_error=TimeoutError("LLM timed out"))
        with pytest.raises(TimeoutError):
            await client.reason({})


# -------------------------------------------------------------------------
# G. HistoricalRetriever Tests
# -------------------------------------------------------------------------

class TestHistoricalRetriever:

    @pytest.mark.asyncio
    async def test_fake_historical_retriever(self):
        retriever = FakeHistoricalRetriever()
        conclusion = InvestigationConclusion(
            investigation_id="INV1",
            exception_id="EXC1",
            run_id="RUN1",
            method=InvestigationMethod.DETERMINISTIC,
            root_cause="Duplicate entry detected",
            classification=ExceptionCategory.DUPLICATE_ENTRY,
            confidence=Decimal("0.95"),
            financial_exposure=Decimal("5000.00"),
            expected_cost=Decimal("4750.00"),
            recommended_action="flag_duplicate",
            requires_human_review=False,
        )
        await retriever.index_investigation(conclusion)

        results = await retriever.retrieve(ExceptionCategory.DUPLICATE_ENTRY, Decimal("5000.00"), {})
        assert len(results) == 1
        assert results[0]["category"] == "duplicate_entry"

    @pytest.mark.asyncio
    async def test_qdrant_retriever_offline_fallback(self):
        # Qdrant client offline -> should gracefully fallback to in-memory fake without raising
        qdrant = QdrantHistoricalRetriever(host="invalid_host", port=9999)
        results = await qdrant.retrieve(ExceptionCategory.FEE_MISMATCH, Decimal("100.00"), {})
        assert isinstance(results, list)


# -------------------------------------------------------------------------
# H. InvestigationGraphRunner Tests
# -------------------------------------------------------------------------

class TestInvestigationGraphRunner:

    @pytest.mark.asyncio
    async def test_deterministic_path_does_not_invoke_llm(self):
        fake_llm = FakeLLMClient()
        runner = InvestigationGraphRunner(llm_client=fake_llm)

        t1 = make_txn("T1", TransactionSource.GATEWAY, Decimal("1000.00"))
        t2 = make_txn("T2", TransactionSource.LEDGER, Decimal("1000.50"))

        state = InvestigationState(
            investigation_id="INV_DET_1",
            exception_id="EXC_1",
            run_id="RUN_1",
            transactions=[t1.model_dump(), t2.model_dump()],
        )

        conclusion = await runner.run(state)

        assert conclusion.classification == ExceptionCategory.CURRENCY_ROUNDING
        assert conclusion.method == InvestigationMethod.DETERMINISTIC
        assert conclusion.llm_invoked is False
        assert fake_llm.invocation_count == 0

    @pytest.mark.asyncio
    async def test_ambiguous_path_invokes_llm(self):
        fake_llm = FakeLLMClient()
        runner = InvestigationGraphRunner(llm_client=fake_llm)

        t1 = make_txn("T1", TransactionSource.GATEWAY, Decimal("1000.00"))
        t2 = make_txn("T2", TransactionSource.BANK, Decimal("1000.00"))
        decision = DecisionResult(
            transaction_ids=["T1", "T2"],
            action=DecisionAction.AMBIGUOUS,
            confidence=Decimal("0.50"),
            evidence={"margin": 0.01},
            reason="Ambiguous candidates",
        )

        state = InvestigationState(
            investigation_id="INV_LLM_1",
            exception_id="EXC_2",
            run_id="RUN_1",
            decision=decision.model_dump(),
            transactions=[t1.model_dump(), t2.model_dump()],
        )

        conclusion = await runner.run(state)

        assert conclusion.llm_invoked is True
        assert conclusion.method == InvestigationMethod.LLM_ASSISTED
        assert fake_llm.invocation_count == 1

    @pytest.mark.asyncio
    async def test_llm_failure_routes_to_fallback(self):
        failing_llm = FakeLLMClient(raise_error=TimeoutError("LLM Gateway timeout"))
        runner = InvestigationGraphRunner(llm_client=failing_llm)

        # Unexplained discrepancy triggers LLM
        t1 = make_txn("T1", TransactionSource.GATEWAY, Decimal("1000.00"))
        t2 = make_txn("T2", TransactionSource.BANK, Decimal("2500.00"))

        state = InvestigationState(
            investigation_id="INV_FALLBACK_1",
            exception_id="EXC_3",
            run_id="RUN_1",
            transactions=[t1.model_dump(), t2.model_dump()],
        )

        conclusion = await runner.run(state)

        assert conclusion.llm_invoked is True
        assert conclusion.method == InvestigationMethod.FALLBACK
        assert conclusion.requires_human_review is True
        assert conclusion.llm_error is not None


# -------------------------------------------------------------------------
# I. InvestigationRepository Persistence Tests
# -------------------------------------------------------------------------

class TestInvestigationPersistence:

    @pytest.mark.asyncio
    async def test_create_and_retrieve_investigation(self, db_session):
        # Create prerequisite Run and Exception in PostgreSQL
        run_orm = ReconciliationRunORM(
            id="RUN_DB_1",
            run_id="RUN_DB_1",
            status=ReconciliationRunStatus.COMPLETED,
            gateway_count=1,
            ledger_count=1,
            bank_count=1,
            match_count=0,
            exception_count=1,
            created_at=datetime.utcnow(),
        )
        db_session.add(run_orm)
        await db_session.flush()

        exc_orm = ExceptionORM(
            id="EXC_DB_1",
            run_id="RUN_DB_1",
            exception_category=ExceptionCategoryORM.DUPLICATE_RECORD,
            status="open",
            confidence=Decimal("0.95"),
            financial_exposure=Decimal("5000.00"),
            expected_cost=Decimal("4750.00"),
            explanation="Duplicate entry",
            evidence={},
            resolved=False,
            created_at=datetime.utcnow(),
        )
        db_session.add(exc_orm)
        await db_session.flush()

        repo = InvestigationRepository(db_session)
        conclusion = InvestigationConclusion(
            investigation_id="INV_DB_1",
            exception_id="EXC_DB_1",
            run_id="RUN_DB_1",
            method=InvestigationMethod.DETERMINISTIC,
            root_cause="Duplicate transaction records detected",
            classification=ExceptionCategory.DUPLICATE_ENTRY,
            confidence=Decimal("0.95"),
            financial_exposure=Decimal("5000.00"),
            expected_cost=Decimal("4750.00"),
            recommended_action="flag_duplicate",
            requires_human_review=False,
            evidence={"duplicate_count": 2},
        )

        db_id = await repo.create(conclusion)
        assert db_id is not None

        # Retrieve by investigation_id
        fetched = await repo.get_by_investigation_id("INV_DB_1")
        assert fetched is not None
        assert fetched.root_cause == "Duplicate transaction records detected"
        assert fetched.classification == ExceptionCategory.DUPLICATE_ENTRY

        # Test idempotency (creating again with same investigation_id returns existing)
        db_id_2 = await repo.create(conclusion)
        assert db_id_2 == "INV_DB_1"
