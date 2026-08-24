# Project Sentinel — ML & Investigation Evaluation Reproduction Guide

This document details the exact, reproducible steps to generate benchmark datasets, train the offline ML candidate scorer, evaluate deterministic vs. ML matching performance on unseen test splits, and verify selective LLM reasoning.

---

## 1. Prerequisites & Environment Setup

### Environment Variables
Ensure `.env` exists in the repository root with the following configuration:
```bash
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DB=sentinel_db
GROQ_API_KEY=gsk_...
GROQ_MODEL=openai/gpt-oss-20b
```

### Python Dependencies
Python 3.12+ is required. Dependencies include:
```bash
pip install -r requirements.txt
```
Key packages: `xgboost`, `scikit-learn`, `pydantic`, `fastapi`, `langgraph`, `groq`, `sqlalchemy`, `asyncpg`, `pytest`.

---

## 2. Offline ML Model Training & Artifact Generation

To train both Logistic Regression (baseline) and XGBoost (primary) on grouped, leak-free splits and serialize the trained model artifact to `ml/artifacts/model.xgb`:

```powershell
python -m ml.train --num-transactions 1500 --seed 100 --artifact-dir ml/artifacts
```

### What this command does:
1. Generates 1,500 logical transactions ($4,500$ cross-source feed records) with known ground truth across 7 operational scenarios.
2. Performs group partitioning by `logical_transaction_id`:
   - **Train (60%)**: 322,400 candidate pairs ($2,487$ positives, $319,913$ negatives)
   - **Validation (20%)**: 111,974 candidate pairs ($846$ positives, $111,128$ negatives)
   - **Unseen Test (20%)**: 106,033 candidate pairs ($852$ positives, $105,181$ negatives)
3. Computes Candidate Generator Blocking Recall@K ($91.40\%$).
4. Trains Logistic Regression and XGBoost classifiers.
5. Calibrates decision thresholds on validation data.
6. Evaluates test metrics and saves `ml/artifacts/model.xgb`.

---

## 3. Canonical 1,000-Transaction Unseen Test Benchmark

To evaluate the full production `ReconciliationService` on a completely unseen independent test set ($1,000$ transactions, $3,000$ records, `seed=300`):

### A. Deterministic-Only Baseline
```powershell
python -c "
from eval.config import BenchmarkConfig, EvaluationConfig
from eval.evaluator import ReconciliationEvaluator

cfg = EvaluationConfig(
    benchmark_config=BenchmarkConfig(num_transactions=1000, seed=300),
    enable_ml_scoring=False
)
evaluator = ReconciliationEvaluator(cfg)
res = evaluator.evaluate_benchmark(cfg.benchmark_config)
print(f'Deterministic Baseline: Precision={res.overall_matching.precision*100:.2f}%, Recall={res.overall_matching.recall*100:.2f}%, F1={res.overall_matching.f1_score*100:.2f}%')
"
```

### B. Production Deterministic + ML Pipeline
```powershell
python -c "
from eval.config import BenchmarkConfig, EvaluationConfig
from eval.evaluator import ReconciliationEvaluator

cfg = EvaluationConfig(
    benchmark_config=BenchmarkConfig(num_transactions=1000, seed=300),
    enable_ml_scoring=True
)
evaluator = ReconciliationEvaluator(cfg)
res = evaluator.evaluate_benchmark(cfg.benchmark_config)
print(f'Deterministic + ML: Precision={res.overall_matching.precision*100:.2f}%, Recall={res.overall_matching.recall*100:.2f}%, F1={res.overall_matching.f1_score*100:.2f}%')
for r, p in res.rule_performance.items():
    print(f'  Rule {r}: count={p.matches_count}, TP={p.true_positives}, FP={p.false_positives}, Prec={p.precision*100:.2f}%')
"
```

---

## 4. Live Groq LLM End-to-End Investigation Test

To run a real-time live LLM investigation on a high-value anomaly with PostgreSQL persistence and audit logging:

```powershell
python tests/test_live_groq_e2e.py
```

---

## 5. Full Test Suite Execution

To run all 283 unit, integration, and research validation tests:

```powershell
python -m pytest tests/ -v
```
