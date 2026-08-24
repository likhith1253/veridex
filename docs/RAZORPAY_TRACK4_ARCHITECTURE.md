# Project Sentinel — AI Finance Controller Architecture (Razorpay Track 04)

## 1. Problem Context & Finance Operations Need
Modern payment aggregators, merchants, and corporate treasuries process millions of transactions daily across asynchronous data streams:
- **Payment Gateway Settlements** (e.g. Razorpay, Stripe, PayU)
- **Internal ERP / Order Ledgers** (e.g. NetSuite, SAP, Custom SQL)
- **Core Banking Statements** (e.g. ICICI, HDFC, SBI MT940 / CAMT.053)

Finance controllers face three critical bottlenecks:
1. **Multi-Source Discrepancies**: Gateway fees, bank tax deductions, date shifts, and corrupted UTRs prevent naive exact matching.
2. **Delayed Exception Resolution**: Finding why an entry failed to reconcile takes hours of manual spreadsheet investigation.
3. **Unclear Cash Visibility & At-Risk Exposure**: Determining actual settled vs. pending vs. at-risk cash in real time is opaque.

Project Sentinel closes this complete finance operations loop in real time.

---

## 2. Real-Time Architecture Overview

$$\begin{matrix}
\text{Razorpay Webhook / Feeds} & \text{ERP Order Ledger} & \text{Bank Statements (MT940)} \\
\downarrow & \downarrow & \downarrow \\
\hline
\multicolumn{3}{|c|}{\textbf{Real-Time Normalization \& Idempotent Ingestion Layer}} \\
\hline
& \downarrow & \\
\multicolumn{3}{|c|}{\textbf{Stage 1: Deterministic Matching Rules Engine} \; (\ge 0.95 \rightarrow \text{AUTO\_MATCH})} \\
& \downarrow (< 0.95 \text{ Unresolved Scope}) & \\
\multicolumn{3}{|c|}{\textbf{Stage 2: Candidate Blocking} \; (\text{Recall@K} = 91.40\%)} \\
& \downarrow & \\
\multicolumn{3}{|c|}{\textbf{Stage 3: 11-Feature Extractor} \; (\text{Amount, Date, Levenshtein, Fees})} \\
& \downarrow & \\
\multicolumn{3}{|c|}{\textbf{Stage 4: Offline XGBoost Scorer} \; (\text{Precision} = 99.27\%)} \\
& \downarrow & \\
\multicolumn{3}{|c|}{\textbf{Stage 5: Decision Policy} \; (\text{PROPOSE\_MATCH, MANUAL\_REVIEW, UNRESOLVED})} \\
& \downarrow & \\
\multicolumn{3}{|c|}{\textbf{Stage 6: Exception Aggregation \& Financial Exposure Engine}} \\
& \downarrow & \\
\multicolumn{3}{|c|}{\textbf{Stage 7: LangGraph + Selective Groq LLM Investigation} \; (\text{High Exposure / Ambiguous})} \\
& \downarrow & \\
\multicolumn{3}{|c|}{\textbf{Stage 8: PostgreSQL Persistence, Audit Trail \& Fact-Grounded Q\&A Engine}}
\end{matrix}$$

---

## 3. The 3-Tier AI / ML Architecture

### Tier 1: Deterministic Engine
High-throughput exact-key matching rules (`exact_utr`, `exact_order_id`, `exact_reference`, `amount_date`) running at $> 4,500\text{ records/sec}$. Clean transactions match with zero latency overhead.

### Tier 2: Offline XGBoost Candidate Scorer (No LLM in Matching)
When reference strings are corrupted or timestamps shifted:
- Computes 11 domain features in microseconds.
- Forward-pass inference on frozen model artifact (`ml/artifacts/model.xgb`).
- Recovers **100% of matchable corrupted records** at **99.27% ML precision** and $0.010\text{ ms/pair}$ latency.

### Tier 3: Selective LLM Investigation (LangGraph + Groq)
LLM is never used for matching. It is used strictly downstream to explain complex anomalies:
- Evaluates only ambiguous decisions or exceptions with financial exposure $> \text{INR } 100,000$.
- Bypasses 100% of deterministic and auto-match cases.
- Enforces strict Pydantic schema firewall and graceful fallback to human review on API timeout.

---

## 4. Fact-Grounded Finance Q&A Architecture
Queries like *"How much money is unreconciled?"* or *"What caused most failures?"*:
1. Query PostgreSQL tables directly for exact numerical sums.
2. Formulate factual evidence records with transaction IDs.
3. Groq synthesizes the executive explanation grounded strictly in the verified SQL facts. Zero hallucinated metrics.

---

## 5. Auditability & Productionization Status
- **Architecture**: Production-oriented prototype designed for enterprise deployment.
- **Persistence**: Async PostgreSQL with SQLAlchemy & Alembic migrations.
- **Audit Logging**: Immutable state transition logging in `audit_events`.
- **Security & Secrets**: Zero API key leakage; HMAC-SHA256 signature verification for Razorpay webhooks.
