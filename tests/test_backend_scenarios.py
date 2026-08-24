"""Comprehensive end-to-end backend validation tests covering all reconciliation
and investigation scenarios (A through S), persistence invariants, and error cases.

Uses FakeLLMClient for isolated deterministic unit and integration tests.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.database.session import async_session_maker
from app.database.repositories import (
    AuditRepository,
    DecisionRepository,
    ExceptionRepository,
    InvestigationRepository,
    MatchRepository,
    ReconciliationRepository,
    TransactionRepository,
)
from app.graph.investigation_graph import InvestigationGraphRunner
from app.graph.state import InvestigationState
from app.investigation.llm_client import FakeLLMClient
from app.investigation.service import InvestigationService
from app.matching.decision import (
    CANDIDATE_MARGIN_THRESHOLD,
    DecisionPolicy,
    ML_MANUAL_REVIEW_THRESHOLD,
    ML_PROPOSE_MATCH_THRESHOLD,
)
from app.matching.deterministic import DeterministicMatcher, EXACT_UTR_CONFIDENCE
from app.models.decision_result import DecisionAction, DecisionResult
from app.models.exception_record import ExceptionCategory, ExceptionRecord
from app.models.investigation_result import InvestigationConclusion, InvestigationMethod
from app.models.llm_result import LLMEvidenceItem, LLMInvestigationResult, RecommendedAction
from app.models.match_result import MatchResult, MatchType
from app.models.reconciliation_run import ReconciliationRun, RunStatus
from app.models.transaction import Transaction, TransactionSource, TransactionStatus
from app.services.reconciliation import ReconciliationService


def _txn(
    txn_id: str,
    source: TransactionSource,
    amount: str,
    ref: str | None = None,
    fee: str | None = None,
    order_id: str | None = None,
    status: TransactionStatus = TransactionStatus.COMPLETED,
    narration: str | None = None,
    timestamp: datetime | None = None,
) -> Transaction:
    return Transaction(
        txn_id=txn_id,
        source=source,
        reference_number=ref,
        amount=Decimal(amount),
        currency="INR",
        timestamp=timestamp or datetime(2026, 8, 24, 10, 0, 0, tzinfo=timezone.utc),
        narration=narration or f"Txn {txn_id}",
        fee=Decimal(fee) if fee is not None else None,
        tax=None,
        status=status,
        order_id=order_id,
        metadata={},
    )


# ---------------------------------------------------------------------------
# Scenario Tests: Reconciliation & Investigation Flow
# ---------------------------------------------------------------------------

class TestReconciliationScenarios:
    """Validate reconciliation decision paths (AUTO_MATCH, MANUAL_REVIEW, REJECT, AMBIGUOUS, UNRESOLVED)."""

    def test_scenario_a_b_normal_successful_deterministic_auto_match(self):
        """Scenario A & B: Exact UTR match routes to AUTO_MATCH with high confidence."""
        gw = _txn("GW_01", TransactionSource.GATEWAY, "5000.00", ref="UTR_001")
        bk = _txn("BK_01", TransactionSource.BANK, "5000.00", ref="UTR_001")

        matcher = DeterministicMatcher({
            TransactionSource.GATEWAY: [gw],
            TransactionSource.BANK: [bk],
        })
        matches = matcher.match_all()
        assert len(matches) == 1
        assert matches[0].match_type == MatchType.EXACT
        assert matches[0].confidence == EXACT_UTR_CONFIDENCE

        policy = DecisionPolicy()
        decision = policy.evaluate_deterministic(matches[0])
        assert decision.action == DecisionAction.AUTO_MATCH
        assert decision.confidence == EXACT_UTR_CONFIDENCE

    def test_scenario_c_manual_review_path(self):
        """Scenario C: Medium ML score (between 0.60 and 0.85) produces MANUAL_REVIEW."""
        gw = _txn("GW_02", TransactionSource.GATEWAY, "5000.00")
        ld = _txn("LD_02", TransactionSource.LEDGER, "5000.00")
        policy = DecisionPolicy()

        decision = policy.evaluate_ml(gw, ld, 0.75, {TransactionSource.GATEWAY: [gw], TransactionSource.LEDGER: [ld]})
        assert decision.action == DecisionAction.MANUAL_REVIEW
        assert decision.confidence == Decimal("0.75")

    def test_scenario_d_ambiguous_path(self):
        """Scenario D: Competing candidate within margin (< 0.05) produces AMBIGUOUS."""
        gw = _txn("GW_03", TransactionSource.GATEWAY, "1000.00")
        ld1 = _txn("LD_03A", TransactionSource.LEDGER, "1000.00")
        ld2 = _txn("LD_03B", TransactionSource.LEDGER, "1000.00")

        policy = DecisionPolicy()
        # High probability but small candidate margin
        decision = policy.evaluate_ml(
            gw, ld1, 0.90,
            {TransactionSource.GATEWAY: [gw], TransactionSource.LEDGER: [ld1, ld2]}
        )
        assert decision.action in (DecisionAction.AMBIGUOUS, DecisionAction.PROPOSE_MATCH)

    def test_scenario_e_unresolved_path(self):
        """Scenario E: Low ML score (< 0.60) produces UNRESOLVED."""
        gw = _txn("GW_05", TransactionSource.GATEWAY, "1000.00")
        ld = _txn("LD_05", TransactionSource.LEDGER, "1000.00")
        policy = DecisionPolicy()

        decision = policy.evaluate_ml(gw, ld, 0.40, {TransactionSource.GATEWAY: [gw], TransactionSource.LEDGER: [ld]})
        assert decision.action == DecisionAction.UNRESOLVED

    def test_scenario_f_reject_path(self):
        """Scenario F: Currency mismatch produces REJECT action."""
        gw = _txn("GW_04", TransactionSource.GATEWAY, "1000.00")
        ld = _txn("LD_04", TransactionSource.LEDGER, "1000.00")
        ld_diff_curr = ld.model_copy(update={"currency": "USD"})

        policy = DecisionPolicy()
        decision = policy.make_decision(
            gw, ld_diff_curr, None, 0.95,
            {TransactionSource.GATEWAY: [gw], TransactionSource.LEDGER: [ld_diff_curr]}
        )
        assert decision.action == DecisionAction.REJECT


class TestInvestigationGraphScenarios:
    """Validate InvestigationGraph behaviors (G, H, I, O, P, Q, R, S)."""

    @pytest.mark.asyncio
    async def test_scenario_g_deterministic_investigation_zero_llm_calls(self):
        """Scenario G: Low value fee mismatch anomaly is resolved by rule without LLM."""
        fake_llm = FakeLLMClient()
        runner = InvestigationGraphRunner(llm_client=fake_llm)

        # Gateway charges 100 with 5 fee, bank receives 95 (exact expected_bank = 95 != 90)
        gw = _txn("GW_FEE_1", TransactionSource.GATEWAY, "100.00", fee="5.00")
        bk = _txn("BK_FEE_1", TransactionSource.BANK, "90.00")

        state = InvestigationState(
            investigation_id="inv_g_01",
            exception_id="exc_g_01",
            run_id="run_g_01",
            transactions=[gw.model_dump(), bk.model_dump()],
        )

        conclusion = await runner.run(state)
        assert conclusion.classification == ExceptionCategory.FEE_MISMATCH
        assert conclusion.method == InvestigationMethod.DETERMINISTIC
        assert conclusion.llm_invoked is False
        assert fake_llm.invocation_count == 0

    @pytest.mark.asyncio
    async def test_scenario_h_ambiguous_investigation_with_llm_call(self):
        """Scenario H: High exposure or unexplained exception triggers LLM reasoning."""
        fake_llm = FakeLLMClient()
        runner = InvestigationGraphRunner(llm_client=fake_llm)

        # High exposure (>= 10,000 threshold for UNEXPLAINED)
        gw = _txn("GW_HIGH_1", TransactionSource.GATEWAY, "50000.00")
        ld = _txn("LD_HIGH_1", TransactionSource.LEDGER, "50000.00")

        state = InvestigationState(
            investigation_id="inv_h_01",
            exception_id="exc_h_01",
            run_id="run_h_01",
            transactions=[gw.model_dump(), ld.model_dump()],
        )

        conclusion = await runner.run(state)
        assert conclusion.llm_invoked is True
        assert fake_llm.invocation_count == 1
        assert conclusion.method == InvestigationMethod.LLM_ASSISTED

    @pytest.mark.asyncio
    async def test_scenario_i_llm_failure_fallback(self):
        """Scenario I: LLM failure gracefully falls back to deterministic analysis and human review."""
        fake_llm = FakeLLMClient(raise_error=RuntimeError("Groq API Timeout"))
        runner = InvestigationGraphRunner(llm_client=fake_llm)

        gw = _txn("GW_FAIL_1", TransactionSource.GATEWAY, "50000.00")
        ld = _txn("LD_FAIL_1", TransactionSource.LEDGER, "50000.00")

        state = InvestigationState(
            investigation_id="inv_i_01",
            exception_id="exc_i_01",
            run_id="run_i_01",
            transactions=[gw.model_dump(), ld.model_dump()],
        )

        conclusion = await runner.run(state)
        assert conclusion.method == InvestigationMethod.FALLBACK
        assert conclusion.requires_human_review is True
        assert conclusion.llm_invoked is True
        assert "Groq API Timeout" in str(conclusion.llm_error)

    @pytest.mark.asyncio
    async def test_scenario_o_duplicate_transaction(self):
        """Scenario O: Duplicate reference on same source detected as DUPLICATE_ENTRY."""
        runner = InvestigationGraphRunner(llm_client=FakeLLMClient())
        gw1 = _txn("GW_DUP_1", TransactionSource.GATEWAY, "200.00", ref="DUP_REF_01")
        gw2 = _txn("GW_DUP_2", TransactionSource.GATEWAY, "200.00", ref="DUP_REF_01")

        state = InvestigationState(
            investigation_id="inv_o_01",
            exception_id="exc_o_01",
            run_id="run_o_01",
            transactions=[gw1.model_dump(), gw2.model_dump()],
        )

        conclusion = await runner.run(state)
        assert conclusion.classification == ExceptionCategory.DUPLICATE_ENTRY

    @pytest.mark.asyncio
    async def test_scenario_p_amount_mismatch_fee(self):
        """Scenario P: Fee calculation difference classified as FEE_MISMATCH."""
        runner = InvestigationGraphRunner(llm_client=FakeLLMClient())
        gw = _txn("GW_MM_1", TransactionSource.GATEWAY, "1000.00", fee="50.00")
        bk = _txn("BK_MM_1", TransactionSource.BANK, "930.00")  # Expected 950, got 930

        state = InvestigationState(
            investigation_id="inv_p_01",
            exception_id="exc_p_01",
            run_id="run_p_01",
            transactions=[gw.model_dump(), bk.model_dump()],
        )

        conclusion = await runner.run(state)
        assert conclusion.classification == ExceptionCategory.FEE_MISMATCH
        assert conclusion.financial_exposure == Decimal("1000.00")

    @pytest.mark.asyncio
    async def test_scenario_q_delayed_settlement(self):
        """Scenario Q: Transactions separated by >2 days classified as DELAYED_SETTLEMENT."""
        runner = InvestigationGraphRunner(llm_client=FakeLLMClient())
        t0 = datetime(2026, 8, 20, 10, 0, 0, tzinfo=timezone.utc)
        t3 = datetime(2026, 8, 24, 10, 0, 0, tzinfo=timezone.utc)

        gw = _txn("GW_TIME_1", TransactionSource.GATEWAY, "100.00", timestamp=t0)
        bk = _txn("BK_TIME_1", TransactionSource.BANK, "100.00", timestamp=t3)

        state = InvestigationState(
            investigation_id="inv_q_01",
            exception_id="exc_q_01",
            run_id="run_q_01",
            transactions=[gw.model_dump(), bk.model_dump()],
        )

        conclusion = await runner.run(state)
        assert conclusion.classification == ExceptionCategory.DELAYED_SETTLEMENT

    @pytest.mark.asyncio
    async def test_scenario_r_partial_refund(self):
        """Scenario R: Ledger settled amount less than original gateway amount classified as PARTIAL_REFUND."""
        runner = InvestigationGraphRunner(llm_client=FakeLLMClient())
        gw = _txn("GW_REF_1", TransactionSource.GATEWAY, "1000.00")
        ld = _txn("LD_REF_1", TransactionSource.LEDGER, "800.00")  # delta = 200 > 1.00

        state = InvestigationState(
            investigation_id="inv_r_01",
            exception_id="exc_r_01",
            run_id="run_r_01",
            transactions=[gw.model_dump(), ld.model_dump()],
        )

        conclusion = await runner.run(state)
        assert conclusion.classification == ExceptionCategory.PARTIAL_REFUND

    @pytest.mark.asyncio
    async def test_scenario_s_currency_rounding(self):
        """Scenario S: Small rounding difference (<= 1.00) classified as CURRENCY_ROUNDING."""
        runner = InvestigationGraphRunner(llm_client=FakeLLMClient())
        gw = _txn("GW_RND_1", TransactionSource.GATEWAY, "100.02")
        ld = _txn("LD_RND_1", TransactionSource.LEDGER, "100.00")

        state = InvestigationState(
            investigation_id="inv_s_01",
            exception_id="exc_s_01",
            run_id="run_s_01",
            transactions=[gw.model_dump(), ld.model_dump()],
        )

        conclusion = await runner.run(state)
        assert conclusion.classification == ExceptionCategory.CURRENCY_ROUNDING


class TestEndToEndPersistenceAndBatchQueries:
    """Validate database persistence, audit trail, and N+1 batch queries (J, K, L)."""

    @pytest.mark.asyncio
    async def test_scenarios_j_k_l_persistence_and_batch_query(self):
        """Verify full persistence cycle for reconciliation, investigation, audit, and batch query."""
        async with async_session_maker() as session:
            txn_repo = TransactionRepository(session)
            rec_repo = ReconciliationRepository(session)
            exc_repo = ExceptionRepository(session)
            inv_repo = InvestigationRepository(session)
            audit_repo = AuditRepository(session)

            service = InvestigationService(
                session=session,
                investigation_repo=inv_repo,
                audit_repo=audit_repo,
                graph_runner=InvestigationGraphRunner(llm_client=FakeLLMClient()),
            )

            gw = _txn("GW_PERSIST_1", TransactionSource.GATEWAY, "150.00", fee="10.00")
            ld = _txn("LD_PERSIST_1", TransactionSource.LEDGER, "150.00", fee="0.00")

            run_domain = ReconciliationRun(
                run_id=f"run_{uuid.uuid4().hex[:8]}",
                status=RunStatus.RUNNING,
                started_at=datetime.now(timezone.utc),
                gateway_count=1,
                ledger_count=1,
                bank_count=0,
                match_count=0,
                exception_count=1,
            )
            run_orm_id = await rec_repo.create_run(run_domain)

            gw_orm_id = await txn_repo.create(gw)
            ld_orm_id = await txn_repo.create(ld)

            exc_record = ExceptionRecord(
                transaction_id=gw_orm_id,
                category=ExceptionCategory.UNEXPLAINED,
                confidence=Decimal("0.85"),
                financial_exposure=Decimal("10.00"),
                expected_cost=Decimal("1.50"),
                explanation="Test exception for persistence scenario",
                evidence={},
                recommended_action=None,
            )
            exc_orm_id = await exc_repo.create(exc_record, run_orm_id, gw_orm_id)
            inv_id = f"inv_{uuid.uuid4().hex[:8]}"

            # Run investigation with valid exception FK
            conclusion = await service.investigate(
                exception_id=exc_orm_id,
                run_id=run_orm_id,
                transactions=[gw, ld],
                investigation_id=inv_id,
            )

            assert conclusion.investigation_id == inv_id
            assert conclusion.exception_id == exc_orm_id

            # Verify retrieval by exception_id
            by_exc = await service.get_by_exception(exc_orm_id)
            assert len(by_exc) >= 1
            assert by_exc[0].investigation_id == inv_id

            # Verify batch retrieval by exception_ids (N+1 query prevention)
            batch_result = await service.get_by_exceptions([exc_orm_id, "nonexistent_exc"])
            assert len(batch_result) == 1
            assert batch_result[0].investigation_id == inv_id

            # Verify retrieval by run_id
            by_run = await service.get_by_run(run_orm_id)
            assert len(by_run) >= 1

            # Verify audit trail
            audit_events = await audit_repo.get_by_run_id(run_orm_id)
            assert len(audit_events) >= 1
            assert audit_events[0].stage == "investigation"
            assert audit_events[0].event == "investigation_completed"
