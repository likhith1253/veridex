import argparse
from pathlib import Path

from eval.config import BenchmarkConfig, EvaluationConfig
from eval.evaluator import ReconciliationEvaluator
from eval.reporting import generate_markdown_report, save_reports


def run_benchmark(
    num_transactions: int = 500,
    seed: int = 42,
    output_dir: Path = Path("data/eval_reports"),
) -> None:
    """Run benchmark evaluation and print/save reports."""
    print(f"==================================================")
    print(f"  Project Sentinel - Baseline Evaluation Runner   ")
    print(f"==================================================")
    print(f"Transactions: {num_transactions} | Seed: {seed}")
    print(f"Generating benchmark dataset and running pipeline...")

    bench_config = BenchmarkConfig(
        num_transactions=num_transactions,
        seed=seed,
    )
    eval_config = EvaluationConfig(
        benchmark_config=bench_config,
        report_output_dir=output_dir,
    )

    evaluator = ReconciliationEvaluator(eval_config)
    result = evaluator.evaluate_benchmark(bench_config)

    json_path, md_path = save_reports(result, output_dir)

    print("\n" + generate_markdown_report(result))
    print(f"\nSaved machine-readable JSON to: {json_path}")
    print(f"Saved human-readable Markdown to: {md_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Project Sentinel Baseline Evaluation Runner")
    parser.add_argument("--num-transactions", type=int, default=500, help="Number of benchmark transactions (default: 500)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility (default: 42)")
    parser.add_argument("--output-dir", type=str, default="data/eval_reports", help="Output directory for reports")

    args = parser.parse_args()
    run_benchmark(
        num_transactions=args.num_transactions,
        seed=args.seed,
        output_dir=Path(args.output_dir),
    )
