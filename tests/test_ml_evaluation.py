"""
Tests for ML Realistic Evaluation Phase.

1. A deterministic case bypasses ML.
2. A corrupted-but-matchable case reaches ML.
3. An ambiguous candidate reaches ML/DecisionPolicy.
4. A true non-match does not become AUTO_MATCH.
5. The evaluation can count actual ML invocations.
6. The production ReconciliationService path is used.
7. Full suite passes.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.matching.decision import DecisionPolicy
from app.matching.ml_scorer import MLScorer
from app.models.decision_result import DecisionAction
from app.models.match_result import MatchType
from app.models.transaction import Transaction, TransactionSource, TransactionStatus
from app.services.reconciliation import ReconciliationService
from eval.config import BenchmarkConfig, EvaluationConfig
from eval.dataset import generate_benchmark_dataset
from eval.evaluator import ReconciliationEvaluator


def _ts(offset_days: int = 0) -> datetime:
    return datetime(2024, 1, 1, tzinfo=timezone.utc) + timedelta(days=offset_days)


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


class TestMLEvaluationScenarios:
    """Test suite for ML realistic evaluation phase."""

    @pytest.mark.asyncio
    async def test_1_deterministic_case_bypasses_ml(self):
        """Test 1: A deterministic high-confidence match bypasses ML."""
        gw = Transaction(
            txn_id="G1",
            source=TransactionSource.GATEWAY,
            amount=Decimal("1000.00"),
            currency="INR",
            timestamp=_ts(),
            status=TransactionStatus.COMPLETED,
            order_id="ORD001",
            reference_number="UTR001",
        )
        le = Transaction(
            txn_id="L1",
            source=TransactionSource.LEDGER,
            amount=Decimal("1000.00"),
            currency="INR",
            timestamp=_ts(),
            status=TransactionStatus.COMPLETED,
            order_id="ORD001",
            reference_number="REF001",
        )

        ml_scorer = MagicMock(spec=MLScorer)
        ml_scorer.model_type = "xgboost"
        ml_scorer.predict = MagicMock()
        ml_scorer.train = MagicMock()

        tr, rr, mr, dr, er, ar, session = _make_mock_repos()
        svc = ReconciliationService(
            session=session,
            transaction_repo=tr,
            reconciliation_repo=rr,
            match_repo=mr,
            decision_repo=dr,
            exception_repo=er,
            audit_repo=ar,
            ml_scorer=ml_scorer,
        )

        summary = await svc.run_reconciliation(
            {TransactionSource.GATEWAY: [gw], TransactionSource.LEDGER: [le]},
            run_id="eval_det_test",
        )

        assert summary.deterministic_matches >= 1
        assert summary.ml_proposals == 0
        ml_scorer.train.assert_not_called()
        ml_scorer.predict.assert_not_called()

    @pytest.mark.asyncio
    async def test_2_corrupted_matchable_case_reaches_ml(self):
        """Test 2: A corrupted-but-matchable case reaches ML and produces an ML proposal."""
        gw_anchor = Transaction(
            txn_id="G_ANC",
            source=TransactionSource.GATEWAY,
            amount=Decimal("500.00"),
            currency="INR",
            timestamp=_ts(),
            status=TransactionStatus.COMPLETED,
            order_id="ORD_ANC",
            reference_number="UTR_ANC",
        )
        le_anchor = Transaction(
            txn_id="L_ANC",
            source=TransactionSource.LEDGER,
            amount=Decimal("500.00"),
            currency="INR",
            timestamp=_ts(),
            status=TransactionStatus.COMPLETED,
            order_id="ORD_ANC",
            reference_number="REF_ANC",
        )

        gw_corr = Transaction(
            txn_id="G_CORR",
            source=TransactionSource.GATEWAY,
            amount=Decimal("2500.00"),
            currency="INR",
            timestamp=_ts(1),
            status=TransactionStatus.COMPLETED,
            order_id="ORD_CORRUPT_GW",
            reference_number="UTR_CORRUPT_GW",
        )
        le_corr = Transaction(
            txn_id="L_CORR",
            source=TransactionSource.LEDGER,
            amount=Decimal("2500.00"),
            currency="INR",
            timestamp=_ts(),
            status=TransactionStatus.COMPLETED,
            order_id="ORD_CORRUPT_LD",
            reference_number="REF_CORRUPT_LD",
        )

        real_scorer = MLScorer(model_type="logistic")
        tr, rr, mr, dr, er, ar, session = _make_mock_repos()
        svc = ReconciliationService(
            session=session,
            transaction_repo=tr,
            reconciliation_repo=rr,
            match_repo=mr,
            decision_repo=dr,
            exception_repo=er,
            audit_repo=ar,
            ml_scorer=real_scorer,
        )

        summary = await svc.run_reconciliation(
            {
                TransactionSource.GATEWAY: [gw_anchor, gw_corr],
                TransactionSource.LEDGER: [le_anchor, le_corr],
            },
            run_id="eval_corr_test",
        )

        assert summary.deterministic_matches >= 1
        assert summary.ml_proposals >= 1

    def test_3_ambiguous_candidate_reaches_ml_decision_policy(self):
        """Test 3: An ambiguous candidate is evaluated by DecisionPolicy via ML path."""
        policy = DecisionPolicy()
        t1 = Transaction(
            txn_id="G_AMB",
            source=TransactionSource.GATEWAY,
            amount=Decimal("1500.00"),
            currency="INR",
            timestamp=_ts(),
            status=TransactionStatus.COMPLETED,
        )
        t2 = Transaction(
            txn_id="L_AMB",
            source=TransactionSource.LEDGER,
            amount=Decimal("1500.00"),
            currency="INR",
            timestamp=_ts(),
            status=TransactionStatus.COMPLETED,
        )

        res_review = policy.evaluate_ml(
            t1, t2, probability=0.75,
            transactions_by_source={TransactionSource.GATEWAY: [t1], TransactionSource.LEDGER: [t2]},
        )
        assert res_review.action == DecisionAction.MANUAL_REVIEW

        res_unres = policy.evaluate_ml(
            t1, t2, probability=0.30,
            transactions_by_source={TransactionSource.GATEWAY: [t1], TransactionSource.LEDGER: [t2]},
        )
        assert res_unres.action == DecisionAction.UNRESOLVED

    def test_4_true_non_match_does_not_become_auto_match(self):
        """Test 4: A true non-match never becomes AUTO_MATCH."""
        policy = DecisionPolicy()
        t_gw = Transaction(
            txn_id="G_ORPHAN",
            source=TransactionSource.GATEWAY,
            amount=Decimal("9999.00"),
            currency="INR",
            timestamp=_ts(),
            status=TransactionStatus.COMPLETED,
        )
        t_ld = Transaction(
            txn_id="L_OTHER",
            source=TransactionSource.LEDGER,
            amount=Decimal("100.00"),
            currency="INR",
            timestamp=_ts(10),
            status=TransactionStatus.COMPLETED,
        )

        res = policy.evaluate_ml(
            t_gw, t_ld, probability=0.05,
            transactions_by_source={TransactionSource.GATEWAY: [t_gw], TransactionSource.LEDGER: [t_ld]},
        )
        assert res.action != DecisionAction.AUTO_MATCH
        assert res.action == DecisionAction.UNRESOLVED

    def test_5_evaluation_counts_actual_ml_invocations(self):
        """Test 5: ReconciliationEvaluator measures and counts ML proposals and rules."""
        eval_cfg = EvaluationConfig(
            benchmark_config=BenchmarkConfig(num_transactions=50, seed=42),
            enable_ml_scoring=True,
        )
        evaluator = ReconciliationEvaluator(eval_cfg)
        result = evaluator.evaluate_benchmark(eval_cfg.benchmark_config)

        assert "ml_scored" in result.rule_performance
        ml_rule = result.rule_performance["ml_scored"]
        assert ml_rule.matches_count > 0

    def test_6_production_reconciliation_service_path_is_used(self):
        """Test 6: ReconciliationEvaluator calls ReconciliationService.run_reconciliation directly."""
        eval_cfg = EvaluationConfig(
            benchmark_config=BenchmarkConfig(num_transactions=30, seed=42),
            enable_ml_scoring=True,
        )
        evaluator = ReconciliationEvaluator(eval_cfg)

        with patch.object(
            ReconciliationService,
            "run_reconciliation",
            autospec=True,
            side_effect=ReconciliationService.run_reconciliation,
        ) as spy:
            dataset = generate_benchmark_dataset(eval_cfg.benchmark_config)
            evaluator.evaluate_dataset(dataset)
            spy.assert_called_once()
