"""
Official Razorpay AI Buildathon 2026 — Track 04 Benchmark Runner.

Evaluates Project Sentinel across increasing transaction scales:
- 50 records (minimum Track 4 requirement)
- 500 records
- 1,000 records
- 5,000 records
- 10,000 records

Measures:
- Throughput (records/sec)
- Measured Accuracy (Precision, Recall, F1)
- Deterministic Matches vs. ML Recovered Matches
- Honest Exception List (Manual Reviews, Unresolved, Exposure)
"""

import argparse
import csv
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from eval.config import BenchmarkConfig, EvaluationConfig
from eval.evaluator import ReconciliationEvaluator


@dataclass
class ScaleBenchmarkResult:
    logical_transactions: int
    total_feed_records: int
    runtime_seconds: float
    throughput_records_per_sec: float
    deterministic_matches: int
    ml_matches: int
    manual_reviews: int
    unresolved_exceptions: int
    precision: float
    recall: float
    f1_score: float
    accuracy: float
    unresolved_exposure_inr: float


def run_track4_benchmark(
    scales: list[int] = [50, 500, 1000, 5000, 10000],
    output_dir: Path = Path("data/eval_reports"),
) -> list[ScaleBenchmarkResult]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("================================================================================")
    print(" Razorpay AI Buildathon 2026 — Track 04: AI Finance Controller Benchmark")
    print("================================================================================")
    print(f"Scales to evaluate: {scales}\n")

    results: list[ScaleBenchmarkResult] = []

    for n in scales:
        print(f"--- Running Benchmark for N={n} logical transactions ({n*3} feed records) ---")
        cfg = EvaluationConfig(
            benchmark_config=BenchmarkConfig(num_transactions=n, seed=42),
            enable_ml_scoring=True,
        )
        evaluator = ReconciliationEvaluator(cfg)

        t0 = time.perf_counter()
        eval_res = evaluator.evaluate_benchmark(cfg.benchmark_config)
        elapsed = time.perf_counter() - t0

        total_records = eval_res.total_transactions
        throughput = total_records / elapsed if elapsed > 0 else 0.0

        det_matches = sum(p.matches_count for r, p in eval_res.rule_performance.items() if r != "ml_scored")
        ml_matches = eval_res.rule_performance.get("ml_scored", type("", (), {"matches_count": 0})).matches_count
        unresolved = eval_res.decision_distribution.unresolved_count
        manual_rev = eval_res.decision_distribution.manual_review_count

        total_exp = sum(float(m.false_positive_exposure) for m in eval_res.risk_performance.values())

        res_obj = ScaleBenchmarkResult(
            logical_transactions=n,
            total_feed_records=total_records,
            runtime_seconds=round(elapsed, 4),
            throughput_records_per_sec=round(throughput, 1),
            deterministic_matches=det_matches,
            ml_matches=ml_matches,
            manual_reviews=manual_rev,
            unresolved_exceptions=unresolved,
            precision=round(eval_res.overall_matching.precision * 100, 2),
            recall=round(eval_res.overall_matching.recall * 100, 2),
            f1_score=round(eval_res.overall_matching.f1_score * 100, 2),
            accuracy=round(eval_res.overall_matching.accuracy * 100, 2),
            unresolved_exposure_inr=round(total_exp, 2),
        )
        results.append(res_obj)

        print(f"  Throughput: {res_obj.throughput_records_per_sec:,.1f} rec/s | Runtime: {res_obj.runtime_seconds:.3f}s")
        print(f"  Precision:  {res_obj.precision:.2f}% | Recall: {res_obj.recall:.2f}% | F1: {res_obj.f1_score:.2f}%")
        print(f"  Matches:    Deterministic={res_obj.deterministic_matches}, ML Recovered={res_obj.ml_matches}")
        print(f"  Exceptions: Manual Review={res_obj.manual_reviews}, Unresolved={res_obj.unresolved_exceptions}\n")

    # Save JSON & CSV
    json_path = output_dir / "track4_benchmark_report.json"
    with open(json_path, "w") as f:
        json.dump([asdict(r) for r in results], f, indent=2)

    csv_path = output_dir / "track4_benchmark_report.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(results[0]).keys()))
        writer.writeheader()
        for r in results:
            writer.writerow(asdict(r))

    print(f"Saved benchmark results to {json_path} and {csv_path}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--scales", nargs="+", type=int, default=[50, 500, 1000, 5000])
    args = parser.parse_args()
    run_track4_benchmark(args.scales)
