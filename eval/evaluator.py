import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from typing import Any, Optional

from app.matching.candidate import CandidateGenerator
from app.matching.decision import DecisionPolicy
from app.matching.deterministic import DeterministicMatcher
from app.matching.ml_scorer import MLScorer
from app.models.decision_result import DecisionAction, DecisionResult
from app.models.match_result import MatchResult, MatchType
from app.models.transaction import Transaction, TransactionSource
from eval.config import BenchmarkConfig, EvaluationConfig, RiskBucketConfig
from eval.dataset import BenchmarkDataset, generate_benchmark_dataset
from eval.ground_truth import GroundTruthIndex
from eval.metrics import (
    DecisionDistributionMetrics,
    EvaluationResult,
    MatchingMetrics,
    RiskBucketMetrics,
    RulePerformanceMetrics,
    ScenarioPerformanceMetrics,
    safe_div,
)
from simulator.ground_truth import GroundTruth


import asyncio
from unittest.mock import MagicMock
from app.services.reconciliation import ReconciliationService


class ReconciliationEvaluator:
    """Evaluates reconciliation engine performance against ground truth."""

    def __init__(self, config: Optional[EvaluationConfig] = None):
        self.config = config or EvaluationConfig()

    def evaluate_dataset(
        self,
        dataset: BenchmarkDataset,
        ml_scorer: Optional[MLScorer] = None,
    ) -> EvaluationResult:
        """Run evaluation on a pre-generated benchmark dataset.

        Args:
            dataset: BenchmarkDataset with transactions and ground truth.
            ml_scorer: Optional ML scorer to evaluate ML fallback.

        Returns:
            EvaluationResult containing all computed metrics.
        """
        return self.evaluate_pipeline(
            transactions_by_source=dataset.transactions_by_source,
            ground_truth=dataset.ground_truth,
            dataset_name=dataset.name,
            ml_scorer=ml_scorer,
        )

    def evaluate_benchmark(
        self,
        benchmark_config: Optional[BenchmarkConfig] = None,
        ml_scorer: Optional[MLScorer] = None,
    ) -> EvaluationResult:
        """Generate benchmark data and run evaluation.

        Args:
            benchmark_config: Benchmark configuration (uses default if None).
            ml_scorer: Optional ML scorer.

        Returns:
            EvaluationResult
        """
        cfg = benchmark_config or self.config.benchmark_config
        dataset = generate_benchmark_dataset(cfg)
        return self.evaluate_dataset(dataset, ml_scorer=ml_scorer)

    def evaluate_pipeline(
        self,
        transactions_by_source: dict[TransactionSource, list[Transaction]],
        ground_truth: GroundTruth,
        dataset_name: str = "reconciliation_evaluation",
        ml_scorer: Optional[MLScorer] = None,
    ) -> EvaluationResult:
        """Execute the production ReconciliationService pipeline and evaluate against ground truth.

        Args:
            transactions_by_source: Normalized transactions grouped by source.
            ground_truth: GroundTruth records from simulator or benchmark.
            dataset_name: Identifier for the dataset.
            ml_scorer: Optional MLScorer instance.

        Returns:
            EvaluationResult
        """
        start_time = time.perf_counter()

        # Step 1: Instantiate MLScorer if enabled or provided
        effective_ml_scorer = ml_scorer or (
            MLScorer(model_type="xgboost") if self.config.enable_ml_scoring else None
        )

        # In-memory repository implementations capturing real ReconciliationService outputs
        class InMemMatchRepo:
            def __init__(self):
                self.matches: list[MatchResult] = []

            async def create(self, match: MatchResult, run_id: str) -> str:
                self.matches.append(match)
                return f"match_{len(self.matches)}"

        class InMemDecisionRepo:
            def __init__(self):
                self.decisions: list[DecisionResult] = []

            async def create(self, decision: DecisionResult, run_id: str, match_id: str) -> str:
                self.decisions.append(decision)
                return f"dec_{len(self.decisions)}"

        class InMemTxnRepo:
            async def get_orm_by_source_and_domain_id(self, source: str, txn_id: str):
                return None

            async def create(self, txn: Transaction) -> str:
                return txn.txn_id

        class InMemReconRepo:
            async def create_run(self, run_domain) -> str:
                return run_domain.run_id

            async def create_item(self, run_id: str, txn_id: str, status: str) -> None:
                pass

            async def update_run_status(self, run_id: str, status: str) -> None:
                pass

        class InMemExceptionRepo:
            async def create(self, exception, run_id: str, first_txn_id: str) -> str:
                return f"exc_{first_txn_id}"

            async def add_transaction_to_exception(self, exception_id: str, txn_id: str) -> None:
                pass

        class InMemAuditRepo:
            async def create(self, event) -> None:
                pass

        class InMemSession:
            async def execute(self, query):
                mock_res = MagicMock()
                mock_res.scalar_one_or_none.return_value = None
                return mock_res

            async def flush(self) -> None:
                pass

        match_repo = InMemMatchRepo()
        decision_repo = InMemDecisionRepo()

        service = ReconciliationService(
            session=InMemSession(),
            transaction_repo=InMemTxnRepo(),
            reconciliation_repo=InMemReconRepo(),
            match_repo=match_repo,
            decision_repo=decision_repo,
            exception_repo=InMemExceptionRepo(),
            audit_repo=InMemAuditRepo(),
            ml_scorer=effective_ml_scorer,
            investigation_service=None,
        )

        # Execute the real ReconciliationService production path without crashing when called from an
        # already-running async context (e.g. FastAPI route handlers).
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(service.run_reconciliation(transactions_by_source, run_id=f"eval_{dataset_name}"))
        else:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(
                    asyncio.run,
                    service.run_reconciliation(transactions_by_source, run_id=f"eval_{dataset_name}"),
                )
                future.result()

        all_matches = match_repo.matches
        decisions = decision_repo.decisions
        exec_time = time.perf_counter() - start_time

        # Step 2: Evaluate all metrics against Ground Truth
        return self._compute_metrics(
            transactions_by_source=transactions_by_source,
            ground_truth=ground_truth,
            matches=all_matches,
            decisions=decisions,
            dataset_name=dataset_name,
            exec_time=exec_time,
        )

    def _compute_metrics(
        self,
        transactions_by_source: dict[TransactionSource, list[Transaction]],
        ground_truth: GroundTruth,
        matches: list[MatchResult],
        decisions: list[DecisionResult],
        dataset_name: str,
        exec_time: float,
    ) -> EvaluationResult:
        """Calculate quantitative metrics comparing engine outputs against ground truth."""
        gt_index = GroundTruthIndex(ground_truth)

        total_txns = sum(len(txns) for txns in transactions_by_source.values())
        all_txns_list: list[Transaction] = []
        for txns in transactions_by_source.values():
            all_txns_list.extend(txns)

        # 1. Matching evaluation (TP, FP, FN, TN)
        tp = 0
        fp = 0
        rule_stats: dict[str, dict[str, int]] = defaultdict(lambda: {"count": 0, "tp": 0, "fp": 0})
        matched_logical_ids: set[str] = set()

        # Group matches by logical ID for scenario breakdown
        scenario_counts: dict[str, int] = defaultdict(int)
        scenario_tp: dict[str, int] = defaultdict(int)
        scenario_fp: dict[str, int] = defaultdict(int)
        scenario_matched_records: dict[str, int] = defaultdict(int)

        # Count total logical records per scenario
        for logical_id, rec in ground_truth.records.items():
            scenario_counts[rec.scenario] += 1

        for match in matches:
            rule_key = self._classify_rule(match)
            rule_stats[rule_key]["count"] += 1

            is_valid, gt_rec = gt_index.is_valid_match_group(match.transaction_ids)
            if is_valid and gt_rec:
                tp += 1
                rule_stats[rule_key]["tp"] += 1
                matched_logical_ids.add(gt_rec.logical_transaction_id)
                scenario_tp[gt_rec.scenario] += 1
                scenario_matched_records[gt_rec.scenario] += 1
            else:
                fp += 1
                rule_stats[rule_key]["fp"] += 1
                if gt_rec:
                    scenario_fp[gt_rec.scenario] += 1

        # Calculate FN and TN from ground truth records
        fn = 0
        tn = 0
        scenario_fn: dict[str, int] = defaultdict(int)
        scenario_unresolved: dict[str, int] = defaultdict(int)

        for logical_id, rec in ground_truth.records.items():
            if rec.true_match:
                if logical_id not in matched_logical_ids:
                    fn += 1
                    scenario_fn[rec.scenario] += 1
                    scenario_unresolved[rec.scenario] += 1
            else:
                # Should not be matched (e.g. duplicate / invalid)
                if logical_id not in matched_logical_ids:
                    tn += 1
                scenario_unresolved[rec.scenario] += 1

        total_proposed = len(matches)
        precision = safe_div(tp, tp + fp)
        recall = safe_div(tp, tp + fn)
        f1 = safe_div(2 * precision * recall, precision + recall)
        false_match_rate = safe_div(fp, total_proposed)
        unresolved_count = max(0, len(ground_truth.records) - len(matched_logical_ids))
        unresolved_rate = safe_div(unresolved_count, len(ground_truth.records))
        accuracy = safe_div(tp + tn, tp + tn + fp + fn)

        overall_matching = MatchingMetrics(
            total_proposed_matches=total_proposed,
            true_positives=tp,
            false_positives=fp,
            false_negatives=fn,
            true_negatives=tn,
            precision=precision,
            recall=recall,
            f1_score=f1,
            false_match_rate=false_match_rate,
            unresolved_rate=unresolved_rate,
            accuracy=accuracy,
        )

        # 2. Decision distribution & precision
        total_decisions = len(decisions)
        auto_match_count = sum(1 for d in decisions if d.action == DecisionAction.AUTO_MATCH)
        manual_review_count = sum(1 for d in decisions if d.action in (DecisionAction.MANUAL_REVIEW, DecisionAction.PROPOSE_MATCH))
        ambiguous_count = sum(1 for d in decisions if d.action == DecisionAction.AMBIGUOUS)
        reject_count = sum(1 for d in decisions if d.action == DecisionAction.REJECT)
        unresolved_decision_count = sum(1 for d in decisions if d.action == DecisionAction.UNRESOLVED)

        # AUTO_MATCH precision
        auto_match_tp = 0
        auto_match_fp = 0
        for d in decisions:
            if d.action == DecisionAction.AUTO_MATCH:
                is_valid, _ = gt_index.is_valid_match_group(d.transaction_ids)
                if is_valid:
                    auto_match_tp += 1
                else:
                    auto_match_fp += 1
        auto_match_precision = safe_div(auto_match_tp, auto_match_tp + auto_match_fp, default=1.0 if auto_match_count == 0 else 0.0)

        decision_dist = DecisionDistributionMetrics(
            total_decisions=total_decisions,
            auto_match_count=auto_match_count,
            auto_match_rate=safe_div(auto_match_count, total_decisions),
            auto_match_precision=auto_match_precision,
            manual_review_count=manual_review_count,
            manual_review_rate=safe_div(manual_review_count, total_decisions),
            ambiguous_count=ambiguous_count,
            ambiguous_rate=safe_div(ambiguous_count, total_decisions),
            reject_count=reject_count,
            reject_rate=safe_div(reject_count, total_decisions),
            unresolved_count=unresolved_decision_count,
            unresolved_rate=safe_div(unresolved_decision_count, total_decisions),
        )

        # 3. Rule breakdown
        rule_performance: dict[str, RulePerformanceMetrics] = {}
        for r_name, r_data in rule_stats.items():
            r_prec = safe_div(r_data["tp"], r_data["tp"] + r_data["fp"])
            rule_performance[r_name] = RulePerformanceMetrics(
                rule_name=r_name,
                matches_count=r_data["count"],
                true_positives=r_data["tp"],
                false_positives=r_data["fp"],
                precision=r_prec,
            )

        # 4. Scenario breakdown
        scenario_performance: dict[str, ScenarioPerformanceMetrics] = {}
        for scenario_name, total_s_records in scenario_counts.items():
            s_tp = scenario_tp[scenario_name]
            s_fp = scenario_fp[scenario_name]
            s_fn = scenario_fn[scenario_name]
            s_matched = scenario_matched_records[scenario_name]
            s_unres = scenario_unresolved[scenario_name]
            s_prec = safe_div(s_tp, s_tp + s_fp)
            s_rec = safe_div(s_tp, s_tp + s_fn)
            s_f1 = safe_div(2 * s_prec * s_rec, s_prec + s_rec)

            scenario_performance[scenario_name] = ScenarioPerformanceMetrics(
                scenario=scenario_name,
                total_records=total_s_records,
                matched_records=s_matched,
                correct_matches=s_tp,
                false_matches=s_fp,
                false_negatives=s_fn,
                unresolved_records=s_unres,
                precision=s_prec,
                recall=s_rec,
                f1_score=s_f1,
            )

        # 5. Risk bucket performance
        risk_performance = self._compute_risk_bucket_metrics(
            ground_truth=ground_truth,
            matches=matches,
            gt_index=gt_index,
            matched_logical_ids=matched_logical_ids,
        )

        return EvaluationResult(
            dataset_name=dataset_name,
            total_transactions=total_txns,
            execution_time_seconds=exec_time,
            overall_matching=overall_matching,
            decision_distribution=decision_dist,
            rule_performance=rule_performance,
            scenario_performance=scenario_performance,
            risk_performance=risk_performance,
        )

    def _classify_rule(self, match: MatchResult) -> str:
        """Classify a match result into its governing rule category."""
        reason_lower = match.reason.lower()
        if "ml" in reason_lower:
            return "ml_scored"
        elif "utr" in reason_lower:
            return "exact_utr"
        elif "order id" in reason_lower:
            return "exact_order_id"
        elif "transaction reference" in reason_lower or "reference" in reason_lower:
            return "exact_txn_reference"
        elif "amount + date" in reason_lower or "amount_date" in reason_lower:
            return "amount_date"
        elif match.match_type == MatchType.PROBABLE:
            return "ml_scored"
        return "other"

    def _compute_risk_bucket_metrics(
        self,
        ground_truth: GroundTruth,
        matches: list[MatchResult],
        gt_index: GroundTruthIndex,
        matched_logical_ids: set[str],
    ) -> dict[str, RiskBucketMetrics]:
        """Compute performance metrics segmented by monetary risk buckets."""
        risk_cfg = self.config.risk_config
        buckets_def = [
            ("Low (<10k)", Decimal("0"), risk_cfg.low_threshold),
            ("Medium (10k-50k)", risk_cfg.low_threshold, risk_cfg.medium_threshold),
            ("High (50k-200k)", risk_cfg.medium_threshold, risk_cfg.high_threshold),
            ("Critical (>200k)", risk_cfg.high_threshold, None),
        ]

        bucket_records: dict[str, list] = defaultdict(list)
        bucket_matched_tp: dict[str, int] = defaultdict(int)
        bucket_matched_fp: dict[str, int] = defaultdict(int)
        bucket_fp_exposure: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        bucket_exposure: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))

        for logical_id, rec in ground_truth.records.items():
            b_name = self._get_bucket_name(rec.true_amount, buckets_def)
            bucket_records[b_name].append(rec)
            bucket_exposure[b_name] += rec.true_amount

        for match in matches:
            is_valid, gt_rec = gt_index.is_valid_match_group(match.transaction_ids)
            if gt_rec:
                b_name = self._get_bucket_name(gt_rec.true_amount, buckets_def)
                if is_valid:
                    bucket_matched_tp[b_name] += 1
                else:
                    bucket_matched_fp[b_name] += 1
                    bucket_fp_exposure[b_name] += gt_rec.true_amount

        result: dict[str, RiskBucketMetrics] = {}
        for name, min_amt, max_amt in buckets_def:
            records = bucket_records[name]
            count = len(records)
            exp = bucket_exposure[name]
            tp = bucket_matched_tp[name]
            fp = bucket_matched_fp[name]
            fn = sum(1 for r in records if r.true_match and r.logical_transaction_id not in matched_logical_ids)
            matches_count = tp + fp
            prec = safe_div(tp, tp + fp)
            rec = safe_div(tp, tp + fn)

            result[name] = RiskBucketMetrics(
                bucket_name=name,
                min_amount=min_amt,
                max_amount=max_amt,
                transaction_count=count,
                total_exposure_amount=exp,
                matches_count=matches_count,
                true_positives=tp,
                false_positives=fp,
                precision=prec,
                recall=rec,
                false_positive_exposure=bucket_fp_exposure[name],
            )

        return result

    def _get_bucket_name(self, amount: Decimal, buckets_def: list[tuple]) -> str:
        for name, min_amt, max_amt in buckets_def:
            if max_amt is None:
                if amount >= min_amt:
                    return name
            elif min_amt <= amount < max_amt:
                return name
        return buckets_def[-1][0]
