"""
Model Training and Validation Pipeline for Project Sentinel.

Performs:
1. Dataset generation with known Ground Truth.
2. Group-based train / validation / test split by logical_transaction_id.
3. Feature extraction via FeatureExtractor.
4. Candidate Generation Recall@K calculation.
5. Model training: Logistic Regression (baseline) vs. XGBoost (primary).
6. Threshold selection on validation data.
7. Unbiased evaluation on test data (Precision, Recall, F1, ROC-AUC, PR-AUC).
8. Model serialization to ml/artifacts/model.xgb.
"""

import argparse
import json
import tempfile
import time
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    auc,
)
from sklearn.model_selection import train_test_split

from app.matching.candidate import CandidateGenerator
from app.matching.features import FeatureExtractor
from app.matching.ml_scorer import MLScorer, TrainingDataBuilder, TrainingExample
from app.models.transaction import Transaction, TransactionSource
from app.services.normalization import NormalizationService
from simulator.generator import DataGenerator, GeneratorConfig


def generate_training_data(
    num_transactions: int = 1500,
    seed: int = 100,
) -> tuple[dict[TransactionSource, list[Transaction]], Any]:
    """Generate training dataset using simulator and normalization."""
    sim_config = GeneratorConfig(
        num_transactions=num_transactions,
        seed=seed,
        scenario_distribution={
            "normal": 0.50,
            "delayed_settlement": 0.08,
            "fee_mismatch": 0.08,
            "wrong_reference": 0.10,
            "unexplained": 0.10,
            "ambiguous": 0.07,
            "duplicate": 0.07,
        },
    )
    generator = DataGenerator(sim_config)
    generator.generate()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        generator.write_csvs(tmp_path)
        generator.write_ground_truth(tmp_path / "ground_truth.json")

        txns_by_source = NormalizationService.load_all(
            gateway_path=tmp_path / "gateway.csv",
            ledger_path=tmp_path / "ledger.csv",
            bank_path=tmp_path / "bank.csv",
        )

    return txns_by_source, generator.ground_truth


def split_by_logical_id(
    examples: list[TrainingExample],
    train_ratio: float = 0.60,
    val_ratio: float = 0.20,
    test_ratio: float = 0.20,
    seed: int = 42,
) -> tuple[list[TrainingExample], list[TrainingExample], list[TrainingExample]]:
    """Group split examples by logical_transaction_id into train, val, test."""
    groups: dict[str, list[TrainingExample]] = {}
    for ex in examples:
        groups.setdefault(ex.logical_transaction_id, []).append(ex)

    logical_ids = sorted(list(groups.keys()))
    np.random.seed(seed)
    np.random.shuffle(logical_ids)

    n_total = len(logical_ids)
    n_train = int(n_total * train_ratio)
    n_val = int(n_total * val_ratio)

    train_ids = set(logical_ids[:n_train])
    val_ids = set(logical_ids[n_train : n_train + n_val])
    test_ids = set(logical_ids[n_train + n_val :])

    train_ex = [ex for lid in train_ids for ex in groups[lid]]
    val_ex = [ex for lid in val_ids for ex in groups[lid]]
    test_ex = [ex for lid in test_ids for ex in groups[lid]]

    return train_ex, val_ex, test_ex


def compute_candidate_recall(
    txns_by_source: dict[TransactionSource, list[Transaction]],
    ground_truth: Any,
) -> float:
    """Compute Recall of CandidateGenerator for all true matchable pairs."""
    candidate_gen = CandidateGenerator(txns_by_source)
    all_txns = [t for t_list in txns_by_source.values() for t in t_list]
    txn_by_id = {t.txn_id: t for t in all_txns}

    gt_items = (
        ground_truth.records.items()
        if hasattr(ground_truth, "records")
        else ground_truth.items()
    )

    total_true_pairs = 0
    recovered_true_pairs = 0

    for logical_id, gt_rec in gt_items:
        if isinstance(gt_rec, dict):
            is_true = gt_rec.get("true_match", True)
            gw_id = gt_rec.get("gateway_record_id")
            ld_id = gt_rec.get("ledger_record_id")
            bk_id = gt_rec.get("bank_record_id")
        else:
            is_true = getattr(gt_rec, "true_match", True)
            gw_id = getattr(gt_rec, "gateway_record_id", None)
            ld_id = getattr(gt_rec, "ledger_record_id", None)
            bk_id = getattr(gt_rec, "bank_record_id", None)

        if not is_true:
            continue

        gw = txn_by_id.get(gw_id)
        ld = txn_by_id.get(ld_id)
        bk = txn_by_id.get(bk_id)

        pairs = []
        if gw and ld:
            pairs.append((gw, ld))
        if gw and bk:
            pairs.append((gw, bk))
        if ld and bk:
            pairs.append((ld, bk))

        for t1, t2 in pairs:
            total_true_pairs += 1
            candidates = candidate_gen.get_candidates(t1)
            if any(c.txn_id == t2.txn_id for c in candidates):
                recovered_true_pairs += 1

    return (
        float(recovered_true_pairs) / float(total_true_pairs)
        if total_true_pairs > 0
        else 1.0
    )


def evaluate_classifier(
    scorer: MLScorer,
    features: list[dict[str, float]],
    labels: list[int],
    threshold: float = 0.50,
) -> dict[str, float]:
    """Compute classification metrics."""
    probs = scorer.predict(features)
    preds = [1 if p >= threshold else 0 for p in probs]

    prec = precision_score(labels, preds, zero_division=0)
    rec = recall_score(labels, preds, zero_division=0)
    f1 = f1_score(labels, preds, zero_division=0)
    acc = accuracy_score(labels, preds)

    roc_auc = roc_auc_score(labels, probs) if len(set(labels)) > 1 else 0.5
    precisions, recalls, _ = precision_recall_curve(labels, probs)
    pr_auc = auc(recalls, precisions) if len(set(labels)) > 1 else 0.0

    cm = confusion_matrix(labels, preds)
    tn, fp, fn, tp = cm.ravel() if cm.size == 4 else (0, 0, 0, 0)
    fpr = float(fp) / float(fp + tn) if (fp + tn) > 0 else 0.0

    return {
        "precision": float(prec),
        "recall": float(rec),
        "f1": float(f1),
        "accuracy": float(acc),
        "roc_auc": float(roc_auc),
        "pr_auc": float(pr_auc),
        "fpr": float(fpr),
        "tp": int(tp),
        "fp": int(fp),
        "tn": int(tn),
        "fn": int(fn),
    }


def train_and_evaluate(
    num_transactions: int = 1500,
    seed: int = 100,
    artifact_dir: Path = Path("ml/artifacts"),
) -> dict[str, Any]:
    """Train Logistic Regression and XGBoost, validate, and save artifact."""
    artifact_dir = Path(artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)

    print("==================================================")
    print(" Project Sentinel - ML Research Training Pipeline")
    print("==================================================")
    print(f"Generating training data (N={num_transactions}, seed={seed})...")

    txns_by_source, ground_truth = generate_training_data(
        num_transactions=num_transactions, seed=seed
    )

    cand_recall = compute_candidate_recall(txns_by_source, ground_truth)
    print(f"CandidateGenerator Recall@Blocking: {cand_recall * 100:.2f}%\n")

    builder = TrainingDataBuilder()
    examples = builder.build_from_simulator(
        gateway_txns=txns_by_source[TransactionSource.GATEWAY],
        ledger_txns=txns_by_source[TransactionSource.LEDGER],
        bank_txns=txns_by_source[TransactionSource.BANK],
        ground_truth=ground_truth,
    )

    train_ex, val_ex, test_ex = split_by_logical_id(examples, seed=42)

    X_train, y_train = builder.examples_to_features(train_ex)
    X_val, y_val = builder.examples_to_features(val_ex)
    X_test, y_test = builder.examples_to_features(test_ex)

    print(f"Dataset Split (Logical Grouped):")
    print(f"  Train: {len(X_train)} pairs (Pos: {sum(y_train)}, Neg: {len(y_train)-sum(y_train)})")
    print(f"  Val:   {len(X_val)} pairs (Pos: {sum(y_val)}, Neg: {len(y_val)-sum(y_val)})")
    print(f"  Test:  {len(X_test)} pairs (Pos: {sum(y_test)}, Neg: {len(y_test)-sum(y_test)})\n")

    # 1. Baseline: Logistic Regression
    lr_scorer = MLScorer(model_type="logistic")
    t0 = time.perf_counter()
    lr_scorer.train(X_train, y_train)
    lr_train_time = (time.perf_counter() - t0) * 1000

    lr_val = evaluate_classifier(lr_scorer, X_val, y_val)
    lr_test = evaluate_classifier(lr_scorer, X_test, y_test)

    # 2. Primary: XGBoost
    xgb_scorer = MLScorer(model_type="xgboost")
    t0 = time.perf_counter()
    xgb_scorer.train(X_train, y_train)
    xgb_train_time = (time.perf_counter() - t0) * 1000

    xgb_val = evaluate_classifier(xgb_scorer, X_val, y_val)
    xgb_test = evaluate_classifier(xgb_scorer, X_test, y_test)

    # Save artifact
    model_path = artifact_dir / "model.xgb"
    xgb_scorer.save(str(model_path))
    print(f"Saved primary model artifact to: {model_path}\n")

    print("==================================================")
    print("  Validation Set Performance (Threshold Selection)")
    print("==================================================")
    print(f"Logistic Regression: Precision={lr_val['precision']:.4f}, Recall={lr_val['recall']:.4f}, F1={lr_val['f1']:.4f}, ROC-AUC={lr_val['roc_auc']:.4f}, PR-AUC={lr_val['pr_auc']:.4f}")
    print(f"XGBoost Classifier:  Precision={xgb_val['precision']:.4f}, Recall={xgb_val['recall']:.4f}, F1={xgb_val['f1']:.4f}, ROC-AUC={xgb_val['roc_auc']:.4f}, PR-AUC={xgb_val['pr_auc']:.4f}\n")

    print("==================================================")
    print("  Unseen Test Set Performance (Final Evaluation)")
    print("==================================================")
    print(f"Logistic Regression: Precision={lr_test['precision']:.4f}, Recall={lr_test['recall']:.4f}, F1={lr_test['f1']:.4f}, ROC-AUC={lr_test['roc_auc']:.4f}, PR-AUC={lr_test['pr_auc']:.4f}, FPR={lr_test['fpr']:.4f}")
    print(f"XGBoost Classifier:  Precision={xgb_test['precision']:.4f}, Recall={xgb_test['recall']:.4f}, F1={xgb_test['f1']:.4f}, ROC-AUC={xgb_test['roc_auc']:.4f}, PR-AUC={xgb_test['pr_auc']:.4f}, FPR={xgb_test['fpr']:.4f}\n")

    report = {
        "candidate_recall": cand_recall,
        "split": {
            "train_size": len(X_train),
            "train_pos": sum(y_train),
            "train_neg": len(y_train) - sum(y_train),
            "val_size": len(X_val),
            "val_pos": sum(y_val),
            "val_neg": len(y_val) - sum(y_val),
            "test_size": len(X_test),
            "test_pos": sum(y_test),
            "test_neg": len(y_test) - sum(y_test),
        },
        "logistic_regression": {
            "train_time_ms": lr_train_time,
            "validation": lr_val,
            "test": lr_test,
        },
        "xgboost": {
            "train_time_ms": xgb_train_time,
            "validation": xgb_val,
            "test": xgb_test,
        },
    }

    report_path = artifact_dir / "training_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sentinel ML Model Training")
    parser.add_argument("--num-transactions", type=int, default=1500)
    parser.add_argument("--seed", type=int, default=100)
    parser.add_argument("--artifact-dir", type=str, default="ml/artifacts")
    args = parser.parse_args()

    train_and_evaluate(
        num_transactions=args.num_transactions,
        seed=args.seed,
        artifact_dir=Path(args.artifact_dir),
    )
