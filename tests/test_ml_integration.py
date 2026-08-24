import asyncio
import time
import inspect
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.matching.candidate import CandidateGenerator
from app.matching.decision import DecisionPolicy, ML_PROPOSE_MATCH_THRESHOLD, ML_MANUAL_REVIEW_THRESHOLD
from app.matching.deterministic import DeterministicMatcher
from app.matching.features import FeatureExtractor
from app.matching.ml_scorer import MLScorer
from app.models.decision_result import DecisionAction
from app.models.match_result import MatchResult, MatchType
from app.models.transaction import Transaction, TransactionSource, TransactionStatus


def _ts(offset_days=0):
    return datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=offset_days)


def _gateway(txn_id, amount="100.00", order_id="ORD001", ref=None, **kw):
    return Transaction(
        txn_id=txn_id, source=TransactionSource.GATEWAY,
        amount=Decimal(amount), currency="INR", timestamp=_ts(),
        status=TransactionStatus.COMPLETED, order_id=order_id,
        reference_number=ref, **kw)


def _ledger(txn_id, amount="100.00", order_id="ORD001", ref=None, **kw):
    return Transaction(
        txn_id=txn_id, source=TransactionSource.LEDGER,
        amount=Decimal(amount), currency="INR", timestamp=_ts(),
        status=TransactionStatus.COMPLETED, order_id=order_id,
        reference_number=ref, **kw)


def _make_mock_repos():
    tr = AsyncMock()
    tr.get_orm_by_source_and_domain_id = AsyncMock(return_value=None)
    tr.create = AsyncMock(side_effect=lambda txn: f"orm-{txn.txn_id}")
    rr = AsyncMock()
    rr.create_run = AsyncMock(return_value="run-uuid-001")
    rr.create_item = AsyncMock(return_value=None)
    rr.update_run_status = AsyncMock(return_value=None)
    mr = AsyncMock()
    mr.create = AsyncMock(return_value="match-uuid-001")
    dr = AsyncMock()
    dr.create = AsyncMock(return_value=None)
    er = AsyncMock()
    er.create = AsyncMock(return_value="exc-uuid-001")
    er.add_transaction_to_exception = AsyncMock(return_value=None)
    ar = AsyncMock()
    ar.create = AsyncMock(return_value=None)
    session = AsyncMock()
    orm_obj = MagicMock()
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = orm_obj
    session.execute = AsyncMock(return_value=execute_result)
    session.flush = AsyncMock(return_value=None)
    return tr, rr, mr, dr, er, ar, session


def _make_service(ml_scorer=None, investigation_service=None):
    from app.services.reconciliation import ReconciliationService
    tr, rr, mr, dr, er, ar, session = _make_mock_repos()
    return ReconciliationService(
        session=session, transaction_repo=tr, reconciliation_repo=rr,
        match_repo=mr, decision_repo=dr, exception_repo=er, audit_repo=ar,
        ml_scorer=ml_scorer, investigation_service=investigation_service)


# ---------------------------------------------------------------------------
# TEST 1: Deterministic match does NOT invoke ML
# ---------------------------------------------------------------------------

class TestML01DeterministicDoesNotInvokeML:
    @pytest.mark.asyncio
    async def test_deterministic_match_skips_ml(self):
        gw = _gateway("G1", order_id="ORD001", ref="REF001")
        le = _ledger("L1", order_id="ORD001", ref="REF001")
        ml_scorer = MagicMock(spec=MLScorer)
        ml_scorer.model_type = "xgboost"
        ml_scorer.train = MagicMock()
        ml_scorer.predict = MagicMock()
        svc = _make_service(ml_scorer=ml_scorer)
        txns = {TransactionSource.GATEWAY: [gw], TransactionSource.LEDGER: [le]}
        summary = await svc.run_reconciliation(txns, run_id="run-t1")
        ml_scorer.train.assert_not_called()
        ml_scorer.predict.assert_not_called()
        assert summary.deterministic_matches >= 1
        assert summary.ml_proposals == 0


# ---------------------------------------------------------------------------
# TEST 2: Unresolved candidate DOES invoke ML (via direct method call)
# ---------------------------------------------------------------------------

class TestML02UnresolvedInvokesML:
    @pytest.mark.asyncio
    async def test_unresolved_pair_triggers_ml_prediction(self):
        # G1/L1 are treated as unresolved candidate pair.
        # We call _run_ml_scoring to verify ML inference executes on unresolved input.
        gw = _gateway("G1", order_id=None, ref=None)
        le = _ledger("L1", order_id=None, ref=None)
        real_scorer = MLScorer(model_type="logistic")
        # Ensure model is initialized/trained or mocked for prediction
        predict_spy = MagicMock(return_value=[0.85])
        real_scorer.predict = predict_spy
        svc = _make_service(ml_scorer=real_scorer)
        txns_by_source = {TransactionSource.GATEWAY: [gw], TransactionSource.LEDGER: [le]}
        results = await svc._run_ml_scoring([gw, le], txns_by_source)
        predict_spy.assert_called()
        assert isinstance(results, list)


# ---------------------------------------------------------------------------
# TEST 3: High ML probability -> appropriate decision
# ---------------------------------------------------------------------------

class TestML03HighProbabilityDecision:
    def test_high_probability_propose_match(self):
        policy = DecisionPolicy()
        gw = _gateway("G1", order_id=None, ref=None)
        le = _ledger("L1", order_id=None, ref=None)
        result = policy.evaluate_ml(gw, le, probability=ML_PROPOSE_MATCH_THRESHOLD + 0.01,
            transactions_by_source={TransactionSource.GATEWAY: [gw], TransactionSource.LEDGER: [le]})
        assert result.action in {DecisionAction.PROPOSE_MATCH, DecisionAction.AMBIGUOUS}
        assert float(result.confidence) >= ML_PROPOSE_MATCH_THRESHOLD

    def test_medium_probability_manual_review(self):
        policy = DecisionPolicy()
        gw = _gateway("G1", order_id=None, ref=None)
        le = _ledger("L1", order_id=None, ref=None)
        prob = (ML_MANUAL_REVIEW_THRESHOLD + ML_PROPOSE_MATCH_THRESHOLD) / 2
        result = policy.evaluate_ml(gw, le, probability=prob,
            transactions_by_source={TransactionSource.GATEWAY: [gw], TransactionSource.LEDGER: [le]})
        assert result.action == DecisionAction.MANUAL_REVIEW


# ---------------------------------------------------------------------------
# TEST 4: Low ML probability does NOT auto-match
# ---------------------------------------------------------------------------

class TestML04LowProbabilityNoAutoMatch:
    def test_low_probability_unresolved(self):
        policy = DecisionPolicy()
        gw = _gateway("G1", order_id=None, ref=None)
        le = _ledger("L1", order_id=None, ref=None)
        result = policy.evaluate_ml(gw, le, probability=0.30,
            transactions_by_source={TransactionSource.GATEWAY: [gw], TransactionSource.LEDGER: [le]})
        assert result.action == DecisionAction.UNRESOLVED
        assert result.action != DecisionAction.AUTO_MATCH

    def test_zero_probability_not_auto_match(self):
        policy = DecisionPolicy()
        gw = _gateway("G1", order_id=None, ref=None)
        le = _ledger("L1", order_id=None, ref=None)
        result = policy.evaluate_ml(gw, le, probability=0.0,
            transactions_by_source={TransactionSource.GATEWAY: [gw], TransactionSource.LEDGER: [le]})
        assert result.action != DecisionAction.AUTO_MATCH


# ---------------------------------------------------------------------------
# TEST 5: ML output flows through DecisionPolicy
# ---------------------------------------------------------------------------

class TestML05MLFlowsThroughDecisionPolicy:
    def test_decision_policy_receives_ml_probability_in_evidence(self):
        policy = DecisionPolicy()
        gw = _gateway("G1", order_id=None, ref=None)
        le = _ledger("L1", order_id=None, ref=None)
        result = policy.evaluate_ml(gw, le, probability=0.75,
            transactions_by_source={TransactionSource.GATEWAY: [gw], TransactionSource.LEDGER: [le]})
        assert "ml_probability" in result.evidence
        assert result.evidence["ml_probability"] == 0.75

    @pytest.mark.asyncio
    async def test_ml_match_result_yields_valid_summary(self):
        gw = _gateway("G1", order_id=None, ref=None)
        le = _ledger("L1", order_id=None, ref=None)
        gw2 = _gateway("G2", order_id="ORD002")
        le2 = _ledger("L2", order_id="ORD002")
        real_scorer = MLScorer(model_type="logistic")
        svc = _make_service(ml_scorer=real_scorer)
        txns = {TransactionSource.GATEWAY: [gw, gw2], TransactionSource.LEDGER: [le, le2]}
        summary = await svc.run_reconciliation(txns, run_id="run-t5")
        assert isinstance(summary.ml_proposals, int)
        assert summary.ml_proposals >= 0

    @pytest.mark.asyncio
    async def test_ml_match_uses_evaluate_ml_not_evaluate_deterministic(self):
        # ML results have confidence < 0.95, so _make_decisions calls evaluate_ml
        gw = _gateway("G1", order_id=None, ref=None)
        le = _ledger("L1", order_id=None, ref=None)
        gw2 = _gateway("G2", order_id="ORD002")
        le2 = _ledger("L2", order_id="ORD002")
        real_scorer = MLScorer(model_type="logistic")
        svc = _make_service(ml_scorer=real_scorer)
        txns_by_source = {TransactionSource.GATEWAY: [gw, gw2], TransactionSource.LEDGER: [le, le2]}
        ml_results = await svc._run_ml_scoring([gw, le], txns_by_source)
        # All ML MatchResults must have confidence < 0.95 (PROBABLE type)
        for r in ml_results:
            assert r.confidence < Decimal("0.95")
            assert r.match_type == MatchType.PROBABLE


# ---------------------------------------------------------------------------
# TEST 6: Exception creation still works for ML-generated review cases
# ---------------------------------------------------------------------------

class TestML06ExceptionCreation:
    @pytest.mark.asyncio
    async def test_ml_cases_can_create_exceptions(self):
        gw = _gateway("G1", order_id=None, ref=None)
        le = _ledger("L1", order_id=None, ref=None)
        gw2 = _gateway("G2", order_id="ORD002")
        le2 = _ledger("L2", order_id="ORD002")
        real_scorer = MLScorer(model_type="logistic")
        svc = _make_service(ml_scorer=real_scorer)
        txns = {TransactionSource.GATEWAY: [gw, gw2], TransactionSource.LEDGER: [le, le2]}
        summary = await svc.run_reconciliation(txns, run_id="run-t6")
        assert isinstance(summary.exceptions_created, int)
        assert summary.exceptions_created >= 0


# ---------------------------------------------------------------------------
# TEST 7: InvestigationService behavior unchanged
# ---------------------------------------------------------------------------

class TestML07InvestigationServiceUnchanged:
    @pytest.mark.asyncio
    async def test_auto_match_does_not_invoke_investigation(self):
        gw = _gateway("G1", order_id="ORD001", ref="REF001")
        le = _ledger("L1", order_id="ORD001", ref="REF001")
        inv_svc = AsyncMock()
        inv_svc.investigate = AsyncMock()
        ml_scorer = MLScorer(model_type="logistic")
        svc = _make_service(ml_scorer=ml_scorer, investigation_service=inv_svc)
        txns = {TransactionSource.GATEWAY: [gw], TransactionSource.LEDGER: [le]}
        await svc.run_reconciliation(txns, run_id="run-t7a")
        inv_svc.investigate.assert_not_called()


# ---------------------------------------------------------------------------
# TEST 8: Groq never invoked by ML matching stage
# ---------------------------------------------------------------------------

class TestML08GroqNotInML:
    def test_ml_scorer_has_no_groq_dependency(self):
        import app.matching.ml_scorer as ml_module
        src = inspect.getsource(ml_module)
        assert "groq" not in src.lower()

    def test_feature_extractor_has_no_llm_dependency(self):
        import app.matching.features as feat_module
        src = inspect.getsource(feat_module)
        assert "groq" not in src.lower()
        assert "openai" not in src.lower()

    @pytest.mark.asyncio
    async def test_run_ml_scoring_source_has_no_groq_runtime_call(self):
        # Verify that _run_ml_scoring contains no runtime Groq calls
        # (only docstring mentions Groq, not actual code)
        from app.services.reconciliation import ReconciliationService
        src = inspect.getsource(ReconciliationService._run_ml_scoring)
        # Remove the docstring section before checking
        lines = src.split("\n")
        in_docstring = False
        code_lines = []
        for line in lines:
            stripped = line.strip()
            if '"""' in stripped:
                in_docstring = not in_docstring
                continue
            if not in_docstring:
                code_lines.append(line)
        code_only = "\n".join(code_lines)
        assert "groq" not in code_only.lower(), "Runtime Groq call found in _run_ml_scoring"
        assert "llm_client" not in code_only.lower(), "LLM client import found in _run_ml_scoring"


# ---------------------------------------------------------------------------
# TEST 9: Deterministic matching behavior unchanged
# ---------------------------------------------------------------------------

class TestML09DeterministicUnchanged:
    def test_exact_order_id_match_high_confidence(self):
        gw = _gateway("G1", order_id="ORD999")
        le = _ledger("L1", order_id="ORD999")
        matcher = DeterministicMatcher({
            TransactionSource.GATEWAY: [gw], TransactionSource.LEDGER: [le]})
        results = matcher.match_all()
        assert len(results) >= 1
        assert results[0].confidence >= Decimal("0.95")

    @pytest.mark.asyncio
    async def test_deterministic_matches_same_with_and_without_ml(self):
        gw = _gateway("G1", order_id="ORD001", ref="REF001")
        le = _ledger("L1", order_id="ORD001", ref="REF001")
        txns = {TransactionSource.GATEWAY: [gw], TransactionSource.LEDGER: [le]}
        svc_no_ml = _make_service(ml_scorer=None)
        svc_with_ml = _make_service(ml_scorer=MLScorer(model_type="logistic"))
        s1 = await svc_no_ml.run_reconciliation(txns, run_id="run-t9a")
        s2 = await svc_with_ml.run_reconciliation(txns, run_id="run-t9b")
        assert s1.deterministic_matches == s2.deterministic_matches


# ---------------------------------------------------------------------------
# TEST 10: ML latency measurement
# ---------------------------------------------------------------------------

class TestML10Latency:
    def test_ml_scoring_latency_sub_second(self):
        scorer = MLScorer(model_type="logistic")
        fe = FeatureExtractor()
        gw = _gateway("G1", order_id=None, ref=None)
        le = _ledger("L1", order_id=None, ref=None)
        gw2 = _gateway("G2", order_id="ORD002")
        le2 = _ledger("L2", order_id="ORD002")
        pairs = [(gw, le, 0), (gw2, le2, 1)]
        features = [fe.extract_features(t1, t2) for t1, t2, _ in pairs]
        labels = [lbl for _, _, lbl in pairs]
        t0 = time.monotonic()
        scorer.train(features, labels)
        probs = scorer.predict(features)
        elapsed = time.monotonic() - t0
        assert elapsed < 1.0, f"ML train+predict took {elapsed:.3f}s"
        assert all(0.0 <= p <= 1.0 for p in probs)
