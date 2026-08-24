# Project Sentinel - Reconciliation Evaluation Baseline

**Dataset**: `benchmark_seed_42_n_500`  
**Total Transactions Evaluated**: 1500  
**Execution Time**: 0.103s  

---

## 1. Overall Matching Performance

| Metric | Value | Description |
| :--- | :--- | :--- |
| **Precision** | **96.00%** | Correct matches / Proposed matches |
| **Recall** | **100.00%** | Correct matches / True matchable records |
| **F1 Score** | **97.96%** | Harmonic mean of Precision and Recall |
| **False Match Rate** | **4.00%** | Incorrect matches / Proposed matches |
| **Unresolved Rate** | **4.00%** | Unmatched records / Total true records |
| **Accuracy** | **96.08%** | (TP + TN) / Total instances |

- **Proposed Matches**: 1000
- **True Positives (TP)**: 960
- **False Positives (FP)**: 40
- **False Negatives (FN)**: 0
- **True Negatives (TN)**: 20

---

## 2. Decision Policy Distribution

| Decision Action | Count | Share | Precision |
| :--- | :--- | :--- | :--- |
| `AUTO_MATCH` | 1000 | 100.0% | 96.00% |
| `MANUAL_REVIEW` | 0 | 0.0% | N/A |
| `AMBIGUOUS` | 0 | 0.0% | N/A |
| `REJECT` | 0 | 0.0% | N/A |
| `UNRESOLVED` | 0 | 0.0% | N/A |
| **Total Decisions** | **1000** | **100.0%** | — |

---

## 3. Deterministic Rules Performance

| Matching Rule | Matches Proposed | True Positives | False Positives | Rule Precision |
| :--- | :--- | :--- | :--- | :--- |
| `exact_order_id` | 500 | 480 | 20 | 96.00% |
| `exact_utr` | 500 | 480 | 20 | 96.00% |

---

## 4. Scenario Breakdown

| Scenario / Corruption | Total Records | Correct (TP) | False (FP) | Unresolved (FN) | Precision | Recall | F1 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `ambiguous` | 10 | 20 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| `delayed_settlement` | 30 | 60 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| `duplicate` | 20 | 0 | 40 | 20 | 0.0% | 0.0% | 0.0% |
| `fee_mismatch` | 25 | 50 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| `normal` | 350 | 700 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| `partial_refund` | 25 | 50 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| `rounding` | 15 | 30 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| `unexplained` | 10 | 20 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| `wrong_reference` | 15 | 30 | 0 | 0 | 100.0% | 100.0% | 100.0% |

---

## 5. Monetary Risk Bucket Breakdown

| Risk Bucket | Records | Total Exposure | Matches | Precision | Recall | False Match Exposure |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `Low (<10k)` | 9 | INR 41,491.00 | 18 | 88.9% | 100.0% | INR 1,424.00 |
| `Medium (10k-50k)` | 33 | INR 1,012,126.00 | 66 | 93.9% | 100.0% | INR 50,600.00 |
| `High (50k-200k)` | 145 | INR 19,155,535.00 | 290 | 96.6% | 100.0% | INR 1,465,164.00 |
| `Critical (>200k)` | 313 | INR 109,537,091.00 | 626 | 96.2% | 100.0% | INR 8,249,908.00 |