# Project Sentinel - Reconciliation Evaluation Baseline

**Dataset**: `benchmark_seed_42_n_500`  
**Total Transactions Evaluated**: 1500  
**Execution Time**: 1.613s  

---

## 1. Overall Matching Performance

| Metric | Value | Description |
| :--- | :--- | :--- |
| **Precision** | **84.76%** | Correct matches / Proposed matches |
| **Recall** | **89.00%** | Correct matches / True matchable records |
| **F1 Score** | **86.83%** | Harmonic mean of Precision and Recall |
| **False Match Rate** | **15.24%** | Incorrect matches / Proposed matches |
| **Unresolved Rate** | **27.60%** | Unmatched records / Total true records |
| **Accuracy** | **77.91%** | (TP + TN) / Total instances |

- **Proposed Matches**: 840
- **True Positives (TP)**: 712
- **False Positives (FP)**: 128
- **False Negatives (FN)**: 88
- **True Negatives (TN)**: 50

---

## 2. Decision Policy Distribution

| Decision Action | Count | Share | Precision |
| :--- | :--- | :--- | :--- |
| `AUTO_MATCH` | 800 | 95.2% | 87.50% |
| `MANUAL_REVIEW` | 4 | 0.5% | N/A |
| `AMBIGUOUS` | 0 | 0.0% | N/A |
| `REJECT` | 0 | 0.0% | N/A |
| `UNRESOLVED` | 36 | 4.3% | N/A |
| **Total Decisions** | **840** | **100.0%** | - |

---

## 3. Deterministic Rules Performance

| Matching Rule | Matches Proposed | True Positives | False Positives | Rule Precision |
| :--- | :--- | :--- | :--- | :--- |
| `amount_date` | 4 | 2 | 2 | 50.00% |
| `exact_order_id` | 400 | 350 | 50 | 87.50% |
| `exact_utr` | 397 | 347 | 50 | 87.41% |
| `ml_scored` | 39 | 13 | 26 | 33.33% |

---

## 4. Scenario Breakdown

| Scenario / Corruption | Total Records | Correct (TP) | False (FP) | Unresolved (FN) | Precision | Recall | F1 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `ambiguous` | 50 | 5 | 14 | 45 | 26.3% | 10.0% | 14.5% |
| `delayed_settlement` | 25 | 50 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| `duplicate` | 50 | 0 | 100 | 50 | 0.0% | 0.0% | 0.0% |
| `fee_mismatch` | 25 | 50 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| `normal` | 300 | 600 | 0 | 0 | 100.0% | 100.0% | 100.0% |
| `unexplained` | 25 | 4 | 6 | 21 | 40.0% | 16.0% | 22.9% |
| `wrong_reference` | 25 | 3 | 8 | 22 | 27.3% | 12.0% | 16.7% |

---

## 5. Monetary Risk Bucket Breakdown

| Risk Bucket | Records | Total Exposure | Matches | Precision | Recall | False Match Exposure |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `Low (<10k)` | 9 | INR 41,491.00 | 15 | 86.7% | 100.0% | INR 7,182.00 |
| `Medium (10k-50k)` | 33 | INR 1,012,126.00 | 59 | 100.0% | 98.3% | INR 0.00 |
| `High (50k-200k)` | 145 | INR 19,155,535.00 | 252 | 86.1% | 90.4% | INR 5,222,824.00 |
| `Critical (>200k)` | 313 | INR 109,537,091.00 | 514 | 82.3% | 86.9% | INR 32,594,008.00 |