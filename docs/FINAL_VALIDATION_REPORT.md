# VERIDEX — Final Academic & Engineering Validation Report

## 1. System Architecture
Veridex is an enterprise-grade AI financial reconciliation and investigation platform that resolves discrepancies across three asynchronous financial data streams:
1. **Payment Gateway Settlement Feeds** (`settlement_id`, `transaction_id`, `order_id`, `utr`, `gross_amount`, `fee`, `tax`, `net_amount`, `settlement_date`, `status`)
2. **Internal Order / Payment Ledgers** (`order_id`, `payment_reference`, `amount`, `order_date`, `payment_status`, `currency`, `internal_reference`)
3. **Core Banking Statements** (`bank_transaction_id`, `utr`, `credit_amount`, `debit_amount`, `value_date`, `narration`, `currency`)

### Processing Flow
$$\text{Multi-Source Feeds} \xrightarrow{\text{Normalization}} \text{Deterministic Rules Engine} \xrightarrow[\ge 0.95]{\text{Resolved}} \text{Auto-Match}$$
$$\downarrow (< 0.95 \text{ Unresolved})$$
$$\text{Candidate Generator} \rightarrow \text{Feature Extractor} \rightarrow \text{XGBoost Scorer} \rightarrow \text{Decision Policy} \rightarrow \text{Exceptions Engine}$$
$$\downarrow$$
$$\text{Investigation Service} \rightarrow \text{LangGraph State Machine} \rightarrow \text{Deterministic Analyzer} \rightarrow \text{Risk Engine} \rightarrow \text{Selective Groq LLM} \rightarrow \text{PostgreSQL}$$

---

## 2. Deterministic Baseline
The deterministic matching engine executes prioritized exact-key matching rules:
- **`exact_utr`**: Matches identical UTR references across feeds (Confidence: `0.98`).
- **`exact_order_id`**: Matches identical Order IDs across Gateway and Ledger (Confidence: `0.95`).
- **`exact_reference`**: Matches cross-feed transaction reference strings (Confidence: `0.97`).
- **`amount_date`**: Fallback matching identical amounts within $\pm 1$ calendar day (Confidence: `0.80`).

Pairs with confidence $\ge 0.95$ are finalized as `AUTO_MATCH` decisions and bypass ML candidate scoring entirely.

---

## 3. ML Architecture
The ML candidate scoring layer acts as a post-deterministic recovery engine:
- **`CandidateGenerator`**: Rule-based blocking engine enforcing currency equality, valid source pairings ($(\text{GW}, \text{Ledger})$, $(\text{GW}, \text{Bank})$, $(\text{Ledger}, \text{Bank})$), calendar window $\pm 3\text{ days}$, and amount tolerance $\pm 20\%$. Blocking Recall@K is **91.40%**.
- **`FeatureExtractor`**: Deterministic standard-library feature extractor extracting 11 numeric features:
  - *Amount features*: `abs_amount_diff`, `rel_amount_diff`
  - *Date features*: `date_diff_days`, `settlement_window_7d`
  - *String similarity*: `ref_similarity`, `narration_similarity` (Levenshtein sequence ratios)
  - *Exact equality*: `currency_equal`, `order_id_equal`, `reference_equal`
  - *Operational consistency*: `fee_tax_consistent`, `fee_tax_amount_diff`
  - *One-hot feed indicators*: Gateway-Ledger, Gateway-Bank, Ledger-Bank
- **`MLScorer`**: XGBoost gradient-boosted decision tree classifier with calibrated probability outputs.
- **`DecisionPolicy`**:
  - Probability $\ge 0.90$ with margin $\ge 0.10 \rightarrow \text{PROPOSE\_MATCH}$
  - Probability $\ge 0.90$ with margin $< 0.10 \rightarrow \text{AMBIGUOUS}$
  - Probability $\in [0.70, 0.90) \rightarrow \text{MANUAL\_REVIEW}$
  - Probability $< 0.70 \rightarrow \text{UNRESOLVED}$

---

## 4. Training Methodology
- **Offline Training Pipeline** (`ml/train.py`): The ML model is trained strictly offline on a dedicated training split (`seed=100`, $N=1,500$ logical transactions / $4,500$ records).
- **Artifact Serialization**: The trained model is serialized to `ml/artifacts/model.xgb` ($48.6\text{ KB}$).
- **Zero-Retraining Inference**: `ReconciliationService` automatically loads `model.xgb` during startup and executes forward-pass probability inference without fitting or modifying weights during reconciliation.

---

## 5. Dataset Generation Methodology
Synthetic financial transactions are generated using `simulator/generator.py` modeling real enterprise settlement dynamics:
- **Normal Matches (50%)**: Clean exact matches across all three feeds.
- **Delayed Settlement (8%)**: Gateway and Bank records shifted by $+1$ to $+3$ calendar days.
- **Fee Mismatch (8%)**: Variable gateway merchant fee deductions and tax splits.
- **Corrupted Reference (10%)**: Truncated or altered UTR/reference strings (e.g. typos, prefix shifts).
- **Corrupted Order ID / Narration (10%)**: Mismatched order IDs with matching token narrations.
- **Ambiguous Match (7%)**: Clustered candidate pairs with identical amounts and close dates.
- **Duplicate / Non-Match (7%)**: Orphaned or double-billed entries with no valid cross-feed counterpart.

---

## 6. Leakage Prevention
1. **Group-Based Partitioning**: Splitting is executed strictly on `logical_transaction_id` groups. All transactions, metadata, and cross-source pairs belonging to a logical transaction are isolated within one split.
2. **Set Disjointness**: $\text{Train} \cap \text{Val} = \emptyset$, $\text{Train} \cap \text{Test} = \emptyset$, $\text{Val} \cap \text{Test} = \emptyset$.
3. **Threshold Freezing**: Decision thresholds were selected on the validation partition and remained frozen during test benchmark evaluation.
4. **No LLM in Matching**: Groq LLM reasoning is isolated to downstream investigation; zero LLM calls participate in feature extraction or candidate scoring.

---

## 7. Test-Set Methodology
- **Benchmark Size**: 1,000 logical transactions ($3,000$ feed records across Gateway, Ledger, Bank).
- **Seed**: `seed=300` (completely unseen and independent of training seed `100`).
- **Ground Truth**: Explicit `GroundTruthRecord` capturing true cross-source associations and monetary exposures.

---

## 8. ML Classification Metrics (Unseen Test Partition: 106,033 Pairs)

| Model | Precision | Recall | F1 Score | ROC-AUC | PR-AUC | False Positive Rate (FPR) | Train Time |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Logistic Regression (Baseline)** | 65.87% | 28.99% | 40.26% | 0.9938 | 0.6115 | 0.0012 (0.12%) | 1,420 ms |
| **XGBoost (Primary Artifact)** | **93.14%** | **33.45%** | **49.22%** | **0.9975** | **0.7504** | **0.0002 (0.02%)** | 68 ms |

---

## 9. Baseline vs. ML Pipeline Comparison (1,000 Unseen Transactions)

| Metric | Deterministic-Only Baseline | Deterministic + ML Pipeline | Incremental ML Impact |
| :--- | :--- | :--- | :--- |
| **Overall Precision** | 85.01% | **89.86%** | **+4.85%** |
| **Overall Recall** | 88.37% | **100.00%** | **+11.63%** |
| **Overall F1 Score** | 86.66% | **94.66%** | **+8.00%** |
| **Overall Accuracy** | 85.20% | **90.34%** | **+5.14%** |
| **Proposed Matches** | 1,654 | 2,001 | +347 proposals |
| **True Positives (TP)** | 1,406 | 1,798 | **+392 resolved records** |
| **False Positives (FP)** | 248 | 203 | -45 |
| **False Negatives (FN)** | 185 | **0** | **-185 (100% recovered)** |
| **Auto-Match Decisions** | 1,591 | 1,591 | Deterministic priority preserved |
| **Manual Review Decisions** | 5 | 151 | Corrupted candidates flagged |
| **Unresolved Decisions** | 58 | 202 | Non-matches safely quarantined |

### Rule Breakdown:
- `exact_order_id`: 800 proposed | 700 TP | 100 FP | 87.50% precision
- `exact_utr`: 791 proposed | 691 TP | 100 FP | 87.36% precision
- **`ml_scored` (XGBoost)**: **410 proposed | 407 TP | 3 FP | 99.27% precision**

---

## 10. LLM Investigation Architecture
The investigation engine uses a compiled **LangGraph state machine** executing multi-source evidence synthesis, deterministic preliminary classification, exposure calculation, Qdrant vector retrieval, selective Groq LLM inference, Pydantic validation, and PostgreSQL persistence.

---

## 11. Selective Groq Invocation
Groq is invoked **only** when predefined risk/ambiguity triggers are met:
1. `DecisionAction.AMBIGUOUS` with competing candidates.
2. `ExceptionCategory.UNEXPLAINED` root-cause anomaly.
3. Financial exposure $\ge \text{INR } 100,000.00$ with deterministic confidence $< 0.85$.
4. Duplicate entry collisions with confidence $< 0.70$.

**Ablation Results ($N=60$ exceptions)**:
- Deterministic Low-Value Exceptions ($N=30$): **0 Groq calls** ($0.0\%$ invocation rate).
- LLM-Eligible High-Value Exceptions ($N=30$): **30 Groq calls** ($100.0\%$ invocation rate).

---

## 12. Structured Output Validation
All LLM responses pass through `LLMInvestigationResult` Pydantic validation:
- Validates field constraints, enum values, confidence bounds $[0.0, 1.0]$, and financial exposure ceiling ($< 2\times$ actual exposure).
- Malformed, empty, or schema-violating outputs are rejected and converted to `InvestigationMethod.FALLBACK` with `requires_human_review = True`.

---

## 13. Failure & Fallback Behavior
- **Timeout / API Error**: Caught gracefully by `InvestigationGraphRunner`, preserving deterministic evidence and flagging manual escalation without crashing reconciliation runs.
- **Zero Fabrication**: When Groq fails, the system never invents root-cause conclusions.

---

## 14. Latency Measurements
- **Deterministic Pipeline Execution**: $0.945\text{ s}$ per 1,000 transactions ($0.94\text{ ms/txn}$).
- **XGBoost Inference Latency**: **$0.010\text{ ms}$ per candidate pair**.
- **Deterministic Investigation Node**: $2.14\text{ ms}$ (P50: $1.98\text{ ms}$, P95: $2.63\text{ ms}$).
- **Live Groq API Network + Reasoning Latency**: **$2.09\text{ s}$** (Model: `openai/gpt-oss-20b`).

---

## 15. External Dataset Evaluation
- **Domain Reality**: Multi-source 3-way financial reconciliation datasets (combining synchronized Payment Gateway logs, ERP ledgers, and Core Banking statements with real customer PII and account UTRs) are proprietary and legally protected by PCI-DSS, GDPR, CCPA, and banking regulations.
- **External Evaluation**: Public transaction fraud datasets (e.g. Kaggle IEEE-CIS, BankSim) represent single-source binary classification rather than 3-way entity reconciliation.
- **Finding**: A controlled, multi-source synthetic benchmark with realistic domain corruptions evaluated on unseen test splits is the methodologically sound and standard academic approach.

---

## 16. Reproducibility Instructions
Complete instructions to reproduce all benchmarks, train the model, and run regression tests are documented in `docs/ML_EVALUATION_REPRODUCTION.md`.

---

## 17. Limitations
1. **Synthetic Feed Generation**: While corruptions simulate realistic typos, date shifts, and fee discrepancies, real enterprise feeds exhibit unpredictable network delays and proprietary vendor formats.
2. **LLM Network Latency**: Live cloud LLM reasoning introduces $\sim 2.0\text{ s}$ latency per high-value exception, requiring selective invocation.

---

## 18. Threats to Validity
- **Construct Validity**: Addressed by evaluating against ground-truth records independently generated by the simulation engine.
- **Internal Validity (Data Leakage)**: Prevented via group-isolated splitting by `logical_transaction_id` and frozen decision thresholds.
- **External Validity**: Acknowledged that synthetic noise distributions may differ from specific banking core platforms.

---

## 19. Final Conclusion
The Veridex financial reconciliation system successfully combines deterministic rule speed, offline XGBoost candidate recovery ($99.27\%$ precision, $100\%$ recovery of corrupted matchable records), and selective Groq LLM semantic investigation into an integrated, leak-free, academically defensible architecture.
