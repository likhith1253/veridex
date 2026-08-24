import json
import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.matching.decision import DecisionPolicy
from app.matching.deterministic import DeterministicMatcher
from app.models.decision_result import DecisionAction, DecisionResult
from app.models.match_result import MatchResult, MatchType
from app.models.transaction import Transaction, TransactionSource, TransactionStatus
from eval.config import BenchmarkConfig, EvaluationConfig, RiskBucketConfig
from eval.dataset import BenchmarkDataset, generate_benchmark_dataset
from eval.evaluator import ReconciliationEvaluator
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
from eval.reporting import generate_json_report, generate_markdown_report, save_reports
from simulator.generator import DataGenerator, GeneratorConfig
from simulator.ground_truth import GroundTruth, GroundTruthRecord


# --- Tests for GroundTruthIndex & Lookup ---

def test_ground_truth_index_lookups():
    gt = GroundTruth()
    rec1 = GroundTruthRecord(
        logical_transaction_id="TXN001",
        gateway_record_id="STL001",
        ledger_record_id="ORD001",
        bank_record_id="BANK001",
        true_match=True,
        true_exception=None,
        true_amount=Decimal("100.00"),
        true_refund=None,
        true_settlement_date=datetime(2024, 1, 1),
        financial_exposure=Decimal("0"),
        scenario="normal",
    )
    rec2 = GroundTruthRecord(
        logical_transaction_id="TXN002",
        gateway_record_id="STL002",
        ledger_record_id="ORD002",
        bank_record_id="BANK002",
        true_match=False,
        true_exception=None,
        true_amount=Decimal("200.00"),
        true_refund=None,
        true_settlement_date=datetime(2024, 1, 1),
        financial_exposure=Decimal("200.00"),
        scenario="duplicate",
    )
    gt.add_record(rec1)
    gt.add_record(rec2)

    index = GroundTruthIndex(gt)

    assert index.get_logical_id("TXN001") == "TXN001"
    assert index.get_logical_id("ORD001") == "TXN001"
    assert index.get_logical_id("BANK001") == "TXN001"
    assert index.get_logical_id("NONEXISTENT") is None

    is_valid, r = index.is_valid_match_pair("TXN001", "ORD001")
    assert is_valid is True
    assert r.logical_transaction_id == "TXN001"

    # Mismatched pair
    is_valid, _ = index.is_valid_match_pair("TXN001", "ORD002")
    assert is_valid is False

    # False match scenario (duplicate)
    is_valid, r = index.is_valid_match_pair("TXN002", "ORD002")
    assert is_valid is False


# --- Tests for Metric Calculations & Edge Cases ---

def test_safe_div():
    assert safe_div(10, 2) == 5.0
    assert safe_div(10, 0) == 0.0
    assert safe_div(0, 0) == 0.0
    assert safe_div(10, 0, default=1.0) == 1.0


def test_perfect_matching_metrics():
    # 10 proposed, 10 true positives, 0 FP, 0 FN, 0 TN
    tp, fp, fn, tn = 10, 0, 0, 0
    p = safe_div(tp, tp + fp)
    r = safe_div(tp, tp + fn)
    f1 = safe_div(2 * p * r, p + r)

    assert p == 1.0
    assert r == 1.0
    assert f1 == 1.0


def test_known_false_positive_metrics():
    # 5 TP, 5 FP, 0 FN
    tp, fp, fn = 5, 5, 0
    p = safe_div(tp, tp + fp)
    r = safe_div(tp, tp + fn)
    f1 = safe_div(2 * p * r, p + r)

    assert p == 0.5
    assert r == 1.0
    assert f1 == pytest.approx(0.6667, rel=1e-3)


def test_known_false_negative_metrics():
    # 5 TP, 0 FP, 5 FN
    tp, fp, fn = 5, 0, 5
    p = safe_div(tp, tp + fp)
    r = safe_div(tp, tp + fn)
    f1 = safe_div(2 * p * r, p + r)

    assert p == 1.0
    assert r == 0.5
    assert f1 == pytest.approx(0.6667, rel=1e-3)


# --- Tests for Benchmark Dataset Generation ---

def test_benchmark_dataset_generation_reproducibility():
    config1 = BenchmarkConfig(num_transactions=30, seed=123)
    config2 = BenchmarkConfig(num_transactions=30, seed=123)

    ds1 = generate_benchmark_dataset(config1)
    ds2 = generate_benchmark_dataset(config2)

    assert ds1.total_transactions == ds2.total_transactions
    assert ds1.gateway_count == ds2.gateway_count
    assert ds1.ledger_count == ds2.ledger_count
    assert ds1.bank_count == ds2.bank_count
    assert len(ds1.ground_truth.records) == len(ds2.ground_truth.records)

    for lid in ds1.ground_truth.records:
        r1 = ds1.ground_truth.records[lid]
        r2 = ds2.ground_truth.records[lid]
        assert r1.true_amount == r2.true_amount
        assert r1.scenario == r2.scenario
        assert r1.true_match == r2.true_match


def test_benchmark_dataset_contains_all_scenarios():
    config = BenchmarkConfig(num_transactions=100, seed=42)
    dataset = generate_benchmark_dataset(config)

    scenarios_present = {rec.scenario for rec in dataset.ground_truth.records.values()}
    assert "normal" in scenarios_present
    assert "delayed_settlement" in scenarios_present
    assert "fee_mismatch" in scenarios_present
    assert "duplicate" in scenarios_present


# --- Tests for ReconciliationEvaluator Pipeline Execution ---

def test_evaluator_runs_on_synthetic_data():
    config = BenchmarkConfig(num_transactions=40, seed=42)
    evaluator = ReconciliationEvaluator()
    result = evaluator.evaluate_benchmark(config)

    assert isinstance(result, EvaluationResult)
    assert result.total_transactions == 120  # 40 gw + 40 ld + 40 bk
    assert result.execution_time_seconds >= 0.0
    assert 0.0 <= result.overall_matching.precision <= 1.0
    assert 0.0 <= result.overall_matching.recall <= 1.0
    assert 0.0 <= result.overall_matching.f1_score <= 1.0
    assert 0.0 <= result.overall_matching.false_match_rate <= 1.0

    # Verify decision distribution
    assert result.decision_distribution.total_decisions > 0
    assert result.decision_distribution.auto_match_count >= 0

    # Verify rule performance
    assert len(result.rule_performance) > 0

    # Verify scenario breakdown
    assert len(result.scenario_performance) > 0
    assert "normal" in result.scenario_performance
    assert result.scenario_performance["normal"].precision == 1.0

    # Verify risk buckets
    assert len(result.risk_performance) > 0


def test_evaluator_reports_generation():
    config = BenchmarkConfig(num_transactions=20, seed=42)
    evaluator = ReconciliationEvaluator()
    result = evaluator.evaluate_benchmark(config)

    json_report = generate_json_report(result)
    parsed_json = json.loads(json_report)
    assert "overall" in parsed_json
    assert "decision_distribution" in parsed_json
    assert "deterministic_rules" in parsed_json
    assert "scenarios" in parsed_json
    assert "risk_buckets" in parsed_json

    md_report = generate_markdown_report(result)
    assert "# Project Sentinel" in md_report
    assert "Overall Matching Performance" in md_report
    assert "Decision Policy Distribution" in md_report
    assert "Deterministic Rules Performance" in md_report
    assert "Scenario Breakdown" in md_report

    with tempfile.TemporaryDirectory() as tmp_dir:
        json_path, md_path = save_reports(result, Path(tmp_dir))
        assert json_path.exists()
        assert md_path.exists()
        assert json_path.stat().st_size > 0
        assert md_path.stat().st_size > 0
