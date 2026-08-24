import json
from pathlib import Path
from eval.metrics import EvaluationResult


def generate_json_report(result: EvaluationResult, indent: int = 2) -> str:
    """Serialize EvaluationResult to formatted JSON string."""
    return json.dumps(result.to_dict(), indent=indent)


def generate_markdown_report(result: EvaluationResult) -> str:
    """Generate a clean, human-readable markdown evaluation report."""
    ov = result.overall_matching
    dd = result.decision_distribution

    lines = [
        f"# Project Sentinel - Reconciliation Evaluation Baseline",
        f"",
        f"**Dataset**: `{result.dataset_name}`  ",
        f"**Total Transactions Evaluated**: {result.total_transactions}  ",
        f"**Execution Time**: {result.execution_time_seconds:.3f}s  ",
        f"",
        f"---",
        f"",
        f"## 1. Overall Matching Performance",
        f"",
        f"| Metric | Value | Description |",
        f"| :--- | :--- | :--- |",
        f"| **Precision** | **{ov.precision * 100:.2f}%** | Correct matches / Proposed matches |",
        f"| **Recall** | **{ov.recall * 100:.2f}%** | Correct matches / True matchable records |",
        f"| **F1 Score** | **{ov.f1_score * 100:.2f}%** | Harmonic mean of Precision and Recall |",
        f"| **False Match Rate** | **{ov.false_match_rate * 100:.2f}%** | Incorrect matches / Proposed matches |",
        f"| **Unresolved Rate** | **{ov.unresolved_rate * 100:.2f}%** | Unmatched records / Total true records |",
        f"| **Accuracy** | **{ov.accuracy * 100:.2f}%** | (TP + TN) / Total instances |",
        f"",
        f"- **Proposed Matches**: {ov.total_proposed_matches}",
        f"- **True Positives (TP)**: {ov.true_positives}",
        f"- **False Positives (FP)**: {ov.false_positives}",
        f"- **False Negatives (FN)**: {ov.false_negatives}",
        f"- **True Negatives (TN)**: {ov.true_negatives}",
        f"",
        f"---",
        f"",
        f"## 2. Decision Policy Distribution",
        f"",
        f"| Decision Action | Count | Share | Precision |",
        f"| :--- | :--- | :--- | :--- |",
        f"| `AUTO_MATCH` | {dd.auto_match_count} | {dd.auto_match_rate * 100:.1f}% | {dd.auto_match_precision * 100:.2f}% |",
        f"| `MANUAL_REVIEW` | {dd.manual_review_count} | {dd.manual_review_rate * 100:.1f}% | N/A |",
        f"| `AMBIGUOUS` | {dd.ambiguous_count} | {dd.ambiguous_rate * 100:.1f}% | N/A |",
        f"| `REJECT` | {dd.reject_count} | {dd.reject_rate * 100:.1f}% | N/A |",
        f"| `UNRESOLVED` | {dd.unresolved_count} | {dd.unresolved_rate * 100:.1f}% | N/A |",
        f"| **Total Decisions** | **{dd.total_decisions}** | **100.0%** | - |",
        f"",
        f"---",
        f"",
        f"## 3. Deterministic Rules Performance",
        f"",
        f"| Matching Rule | Matches Proposed | True Positives | False Positives | Rule Precision |",
        f"| :--- | :--- | :--- | :--- | :--- |",
    ]

    for rule_name, rule_metric in sorted(result.rule_performance.items()):
        lines.append(
            f"| `{rule_name}` | {rule_metric.matches_count} | {rule_metric.true_positives} | "
            f"{rule_metric.false_positives} | {rule_metric.precision * 100:.2f}% |"
        )

    lines.extend([
        f"",
        f"---",
        f"",
        f"## 4. Scenario Breakdown",
        f"",
        f"| Scenario / Corruption | Total Records | Correct (TP) | False (FP) | Unresolved (FN) | Precision | Recall | F1 |",
        f"| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ])

    for scenario_name, sm in sorted(result.scenario_performance.items()):
        lines.append(
            f"| `{scenario_name}` | {sm.total_records} | {sm.correct_matches} | {sm.false_matches} | "
            f"{sm.unresolved_records} | {sm.precision * 100:.1f}% | {sm.recall * 100:.1f}% | {sm.f1_score * 100:.1f}% |"
        )

    lines.extend([
        f"",
        f"---",
        f"",
        f"## 5. Monetary Risk Bucket Breakdown",
        f"",
        f"| Risk Bucket | Records | Total Exposure | Matches | Precision | Recall | False Match Exposure |",
        f"| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ])

    for bucket_name, bm in result.risk_performance.items():
        lines.append(
            f"| `{bucket_name}` | {bm.transaction_count} | INR {bm.total_exposure_amount:,.2f} | "
            f"{bm.matches_count} | {bm.precision * 100:.1f}% | {bm.recall * 100:.1f}% | INR {bm.false_positive_exposure:,.2f} |"
        )

    return "\n".join(lines)


def save_reports(result: EvaluationResult, output_dir: Path) -> tuple[Path, Path]:
    """Save both JSON and Markdown reports to specified directory.

    Returns:
        (json_path, markdown_path)
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "benchmark_results.json"
    md_path = output_dir / "benchmark_report.md"

    with open(json_path, "w", encoding="utf-8") as f:
        f.write(generate_json_report(result))

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(generate_markdown_report(result))

    return json_path, md_path
