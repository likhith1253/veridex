# VERIDEX — Frontend Handoff Specification

**Product Name:** VERIDEX — AI Financial Control & Reconciliation Engine  
**Tagline:** "Find the discrepancy. Prove the cause. Control the action."  
**Target Architecture:** Next.js (App Router), TypeScript, Tailwind CSS, shadcn/ui, TanStack Query  
**Backend API:** FastAPI (`http://127.0.0.1:8000`), PostgreSQL 17  
**Document Version:** 1.0.0  

---

## 1. Product Purpose & Workflow

### Core Mission
Veridex is an autonomous, auditable AI financial reconciliation and control system. It closes the operational finance loop across three asynchronous, fragmented data sources:
1. **Payment Gateway Settlement Data** (Razorpay feeds & webhooks: gross volume, fees, taxes, deductions, UTR references)
2. **Internal Order / Payment Ledger** (Merchant ERP/database transactions, expected revenues, order statuses)
3. **Bank Statement Data** (Core banking credits, wire transfers, NEFT/RTGS UTR records)

### The Core Closed-Loop Flow
Veridex enforces an uncompromising operational sequence:
$$\text{Detect} \longrightarrow \text{Explain} \longrightarrow \text{Decide} \longrightarrow \text{Approve} \longrightarrow \text{Execute} \longrightarrow \text{Audit}$$

```
[Razorpay Feed / Webhook] ──┐
[Internal Ledger ERP]     ──┼─► [Reconciliation Engine] ──► [Exception Detected]
[Bank Statement Statement] ──┘                                      │
                                                                   ▼
[Immutable Audit Trail] ◄── [Bounded Execution] ◄── [Human Approval] ◄── [AI Evidence Dossier]
```

### Critical Business & Safety Invariants
1. **Zero Fabrication**: Veridex never invents IDs, financial amounts, root causes, or expected tax values. If evidence is missing, the system strictly reports `INSUFFICIENT_EVIDENCE`.
2. **Policy-Gated Human-in-the-Loop (HITL)**: AI can investigate, explain, and *recommend* bounded financial actions. AI is **strictly forbidden** from approving or executing money movement or ledger adjustments. Explicit human operator authorization is mandatory.
3. **Monetary Bounded Execution**: Ledger adjustments are strictly capped at INR 5,000.00; write-offs are capped at INR 100.00; total system transaction ceilings are capped at INR 500,000.00. Unbounded transactions are rejected by policy.
4. **Honest Test Mode Reporting**: If Razorpay Test Mode returns zero records, the UI must display zero records honestly—never mock or pretend data exists.

---

## 2. Backend Architecture Overview

- **REST API Framework**: FastAPI with Pydantic v2 schemas and strict CORS / security headers.
- **Database**: PostgreSQL with `asyncpg` connection pooling and SQLAlchemy ORM models.
- **Reconciliation Engine**: 3-stage pipeline combining Deterministic Rule Engine, ML XGBoost Candidate Scoring, and LangGraph LLM Arbitration.
- **Settlement Intelligence**: Automated 3-way financial decomposition:
  $$\text{Expected Net} = \text{Gross Amount} - \text{Gateway Fees} - \text{Gateway Taxes} \pm \text{Adjustments}$$
  $$\text{Variance} = \text{Bank Received Amount} - \text{Expected Net}$$
- **Tax Line Auditor**: Deterministic audit verifying gateway-deducted GST/taxes against authoritative internal ledger data.
- **Audit Trails**: Every webhook ingestion, reconciliation pass, AI recommendation, human decision, and bounded execution generates an immutable audit record in PostgreSQL.

---

## 3. Frontend Information Architecture (Navigation)

The frontend application navigation is structured into dedicated operational command surfaces:

```
Veridex Console
│
├── 1. Command Center (Executive Overview & Funnel)
├── 2. Reconciliation Engine (Run Batches, Ingestion & Matching Matrix)
├── 3. Exception Queue & Workspace (Investigation, Root Cause & Evidence)
├── 4. Settlements & Payouts (Razorpay Breakdown & 3-Way Bank Parity)
├── 5. Tax Line Auditor (GST / Fee Deduction Discrepancy Matrix)
├── 6. Investigation Dossiers (Comprehensive Multi-Source Forensic View)
├── 7. Actions & Approvals (Policy-Gated HITL Approval Center)
├── 8. Audit Trail (Immutable Cryptographic & State Event Log)
├── 9. Razorpay Connector (Live Sync, Webhook Telemetry & Status)
├── 10. Benchmark & Evaluation (Canonical Track 4 Accuracy & Metrics)
└── 11. System Health & Settings (API Keys, Database & Service Status)
```

---

## 4. Complete Frontend-Consumable API Specification

All endpoints reside under `http://127.0.0.1:8000`. Authenticated endpoints accept header `X-API-Key: <key>` (empty string or dev key accepted in local development).

---

### A. Command Center & Overview
#### 1. Executive Overview
- **Method & Path**: `GET /api/v1/controller/overview`
- **Query Parameters**: `run_id` (optional, string)
- **Response JSON**:
```json
{
  "total_records": 150,
  "matched_records": 100,
  "unmatched_records": 50,
  "match_rate": 66.67,
  "total_exceptions": 10,
  "open_exceptions": 8,
  "resolved_exceptions": 2,
  "financial_exposure": "93958.00",
  "expected_cost": "4697.90",
  "total_financial_volume": "1000000.00",
  "unreconciled_exposure_pct": 9.40,
  "run_id": "run_prod_001",
  "currency": "INR"
}
```
- **UI States**: Loading skeleton on cards; empty state when `total_records == 0`; error alert on 500.

#### 2. Reconciliation Funnel
- **Method & Path**: `GET /api/v1/controller/funnel`
- **Query Parameters**: `run_id` (optional, string)
- **Response JSON**:
```json
{
  "total_volume_inr": "500000.00",
  "reconciled_volume_inr": "420000.00",
  "pending_volume_inr": "80000.00",
  "deterministic_matches": 9,
  "ml_matches": 41,
  "unmatched_exceptions": 40
}
```

---

### B. Reconciliation & Ingestion
#### 1. Execute Reconciliation Run
- **Method & Path**: `POST /api/v1/reconciliation/run`
- **Request Body**:
```json
{
  "run_id": "run_manual_001",
  "dataset_path": "data/raw/synthetic_batch.csv"
}
```
- **Response JSON (HTTP 200)**:
```json
{
  "run_id": "run_manual_001",
  "status": "COMPLETED",
  "total_processed": 150,
  "matches_found": 50,
  "exceptions_detected": 10,
  "duration_seconds": 0.082
}
```
- **Refetch Required**: Invalidates `/api/v1/controller/overview`, `/api/v1/controller/funnel`, `/api/v1/runs`.

#### 2. List Transactions
- **Method & Path**: `GET /api/v1/controller/transactions`
- **Query Parameters**: `source` (`gateway` | `ledger` | `bank`), `limit` (default 50), `offset` (default 0)
- **Response JSON**: Array of transactions with IDs, sources, amounts, currencies, fees, taxes, timestamps, and metadata.

---

### C. Exceptions & Investigation
#### 1. Exception Queue
- **Method & Path**: `GET /api/v1/controller/exceptions`
- **Query Parameters**: `status` (`open` | `resolved`), `category`, `limit` (default 50), `offset` (default 0)
- **Response JSON**:
```json
[
  {
    "id": "exc_0c2fffdcf5e0",
    "run_id": "run_001",
    "transaction_id": "tx_setl_123",
    "exception_category": "MISSING_SOURCE",
    "status": "open",
    "confidence": 0.85,
    "financial_exposure": "24410.00",
    "expected_cost": "1220.50",
    "explanation": "Settlement processed by Razorpay (expected net: INR 24410.00), but bank statement credit not yet confirmed (UTR: UTR_LIVE_NOBK_1788432463).",
    "recommended_action": "Monitor bank statement feed for matching UTR credit or file inquiry with bank",
    "resolved": false,
    "created_at": "2026-09-03T16:17:44Z"
  }
]
```

#### 2. Investigation Evidence Dossier
- **Method & Path**: `GET /api/v1/investigations/{id}`
- **Path Parameter**: `id` (Exception ID, Settlement ID, or Transaction ID)
- **Response JSON (HTTP 200)**:
```json
{
  "investigation_id": "inv_exc_0c2fffdcf5e0",
  "entity_id": "exc_0c2fffdcf5e0",
  "entity_type": "exception",
  "status": "open",
  "financial_exposure": 24410.00,
  "currency": "INR",
  "root_cause_candidates": [
    {
      "cause": "UNCONFIRMED_BANK_SETTLEMENT",
      "confidence": 0.85,
      "evidence_summary": "Gateway settlement confirmed by Razorpay payout engine, but counterpart bank credit missing from statement."
    }
  ],
  "claims": [
    {
      "statement": "Gateway settlement reported net payout of INR 24,410.00",
      "grounded": true,
      "source_reference": "tx_setl_123"
    }
  ],
  "recommended_action": "Monitor bank statement feed for matching UTR credit or file inquiry with bank",
  "human_review_required": true,
  "insufficient_evidence": false
}
```
- **Error Response**: HTTP 404 with `{"detail": "Investigation entity not found for ID '...'"`}.

---

### D. Settlement Intelligence & Tax Audit
#### 1. Settlement Financial Breakdown
- **Method & Path**: `GET /api/v1/settlements/{settlement_id}/financial-breakdown`
- **Response JSON**:
```json
{
  "settlement_id": "setl_match_1788432262",
  "gross_amount": "50000.00",
  "fee_amount": "1000.00",
  "tax_amount": "180.00",
  "adjustment_amount": "0.00",
  "expected_net_amount": "48820.00",
  "bank_received_amount": "48820.00",
  "variance": "0.00",
  "currency": "INR",
  "variance_type": "NO_VARIANCE"
}
```

#### 2. Settlement Tax-Line Audit
- **Method & Path**: `GET /api/v1/settlements/{settlement_id}/tax-audit`
- **Response JSON (MATCHED Example)**:
```json
{
  "settlement_id": "setl_live_mat_1788432692",
  "gross_amount": "120000.00",
  "reported_tax": "432.00",
  "expected_tax": "432.00",
  "tax_variance": "0.00",
  "status": "MATCHED",
  "explanation": "Razorpay reported tax INR 432.00 exactly matches expected tax INR 432.00.",
  "evidence_ids": ["tx_mat_1788432692"],
  "currency": "INR"
}
```
- **Response JSON (VARIANCE Example)**:
```json
{
  "settlement_id": "setl_live_var_1788432692",
  "gross_amount": "80000.00",
  "reported_tax": "350.00",
  "expected_tax": "288.00",
  "tax_variance": "62.00",
  "status": "VARIANCE",
  "explanation": "Tax discrepancy detected: Razorpay reported tax INR 350.00 deviates from expected tax INR 288.00 by INR 62.00.",
  "evidence_ids": ["tx_var_1788432692"],
  "currency": "INR"
}
```
- **Response JSON (INSUFFICIENT_EVIDENCE Example)**:
```json
{
  "settlement_id": "setl_no_contract_001",
  "gross_amount": "25000.00",
  "reported_tax": "90.00",
  "expected_tax": null,
  "tax_variance": null,
  "status": "INSUFFICIENT_EVIDENCE",
  "explanation": "Authoritative expected tax cannot be established from existing ledger records, matches, or settlement metadata.",
  "evidence_ids": ["tx_001"],
  "currency": "INR"
}
```

---

### E. Policy-Gated Finance Actions (HITL)
#### 1. Recommend an Action
- **Method & Path**: `POST /api/v1/actions/recommend`
- **Request Body**:
```json
{
  "entity_type": "exception",
  "entity_id": "exc_0c2fffdcf5e0",
  "action_type": "POST_ADJUSTMENT",
  "amount": "150.00",
  "currency": "INR",
  "recommended_by": "ai_investigation_copilot",
  "recommendation_reason": "Verified fee delta on gateway batch; recommend posting ledger adjustment",
  "evidence": {"variance": "150.00", "fee_type": "gateway_mdr"}
}
```
- **Response JSON (HTTP 201 Created)**:
```json
{
  "id": "act_107abc27641d4897",
  "entity_type": "exception",
  "entity_id": "exc_0c2fffdcf5e0",
  "action_type": "POST_ADJUSTMENT",
  "state": "PENDING_APPROVAL",
  "amount": 150.00,
  "currency": "INR",
  "recommended_by": "ai_investigation_copilot",
  "approved_by": null,
  "rejected_by": null,
  "execution_result": null,
  "created_at": "2026-09-03T16:18:29Z"
}
```

#### 2. Human Approval
- **Method & Path**: `POST /api/v1/actions/{action_id}/approve`
- **Request Body**:
```json
{
  "actor": "senior_controller_raj",
  "reason": "Verified against fee schedule agreement"
}
```
- **Important**: Actor name cannot contain `ai` or `agent`. Automated approval attempts return HTTP 403: *"AI cannot independently approve financial actions; explicit human authorization is required."*
- **Response JSON (HTTP 200)**: `state: "APPROVED"`, `approved_by: "senior_controller_raj"`.

#### 3. Human Rejection
- **Method & Path**: `POST /api/v1/actions/{action_id}/reject`
- **Request Body**:
```json
{
  "actor": "controller_priya",
  "reason": "Requires formal merchant dispute; reject adjustment"
}
```
- **Response JSON (HTTP 200)**: `state: "REJECTED"`, `rejected_by: "controller_priya"`.

#### 4. Execute Approved Action
- **Method & Path**: `POST /api/v1/actions/{action_id}/execute`
- **Request Body**: `{"actor": "operator_vikram"}`
- **Constraint**: Action must be in state `APPROVED`. If state is `PENDING_APPROVAL` or `REJECTED`, returns HTTP 403.
- **Response JSON (HTTP 200)**:
```json
{
  "id": "act_107abc27641d4897",
  "state": "EXECUTED",
  "execution_result": {
    "posted_adjustment_amount": "150.00",
    "ledger_note": "Bounded variance adjustment of INR 150.00 posted by operator_vikram",
    "executed_at": "2026-09-03T16:18:31Z"
  }
}
```

#### 5. List Actions
- **Method & Path**: `GET /api/v1/actions`
- **Query Parameters**: `state` (`PENDING_APPROVAL`, `APPROVED`, `REJECTED`, `EXECUTED`), `limit` (default 50)

---

### F. Razorpay Integration & Webhook Telemetry
#### 1. Connector Status
- **Method & Path**: `GET /api/v1/integrations/razorpay/status`
- **Response JSON**:
```json
{
  "configured": true,
  "key_id_masked": "rzp_test_...c2B3",
  "connected": true,
  "mode": "test",
  "base_url": "https://api.razorpay.com/v1",
  "error": null
}
```

#### 2. Razorpay Live Data Sync
- **Method & Path**: `POST /api/v1/integrations/razorpay/sync`
- **Request Body**: `{"count": 50}`
- **Response JSON**:
```json
{
  "success": true,
  "payments_fetched": 0,
  "orders_fetched": 0,
  "settlements_fetched": 0,
  "message": "Fetched 0 payments, 0 orders, 0 settlements from Razorpay. Note: Test Mode account contains zero live records."
}
```

---

### G. AI Copilot & Grounded Q&A
#### 1. Query AI Copilot
- **Method & Path**: `POST /api/v1/controller/copilot/query`
- **Request Body**: `{"question": "What is the current unreconciled exception exposure?", "run_id": null}`
- **Response JSON**:
```json
{
  "answer": "Based on verified database records, the current unreconciled exposure is INR 93,958.00 across 10 open exceptions.",
  "confidence": 0.95,
  "sources": ["PostgreSQL: exceptions table"],
  "evidence": {"unreconciled_exposure": "93958.00", "open_exceptions_count": 10}
}
```
- **Security Guarantee**: Refuses to hallucinate on missing data; strictly blocks prompt-injection attempts to extract API secrets or credentials.

---

## 5. Visual Direction for v0 Frontend

1. **Design Persona**: High-density financial operations console (inspired by Bloomberg Terminal meets Linear / Stripe Dashboard).
2. **Color Palette**:
   - Backgrounds: Neutral slate / zinc (`bg-zinc-950` / `bg-zinc-900` card surfaces)
   - Accents: Emerald (`#10b981` for verified matches / positive delta), Rose (`#f43f5e` for unhedged exposure / variances), Amber (`#f59e0b` for pending approval / unverified bank credit), Indigo (`#6366f1` for AI insight cards).
   - Strict avoidance of generic vibrant SaaS rainbows or cartoonish AI badges.
3. **Typography**: High legibility tabular mono for currency and timestamps (`font-mono`), Inter / Geist Sans for operational labels and tables.
4. **Information Density**: Tight table row padding, compact badges, collapsible evidence drawers, and sticky filter bars.

---

## 6. Primary Interactive Demo Walkthrough for Evaluators

1. **Connect & Verify**: Operator navigates to **Razorpay Connector**, verifies live Test Mode connectivity (masked credentials). Clicks **Sync Now**—observes honest message indicating zero test mode records.
2. **Run Batch Reconciliation**: Navigates to **Reconciliation Engine**, clicks **Run Canonical Batch (N=50)**. Observes 150 feed records processed with 1,700+ rec/s throughput, 9 deterministic matches, 41 ML recovered matches, and 40 unresolved items.
3. **Inspect Funnel & Overview**: Returns to **Command Center**. Charts reflect INR 500k volume, 90.00% precision, 94.74% F1-score, and active exposure.
4. **Forensic Investigation**: Navigates to **Exception Queue**, selects an open exception (e.g. UTR timing mismatch). Opens **Evidence Dossier** to view multi-source side-by-side reconciliation evidence, AI root cause analysis, and grounded facts.
5. **Auditing Tax Lines**: Navigates to **Settlements & Tax Audit**. Inspects settlement payout. Runs **Tax Audit**: sees green `MATCHED` badge for INR 432.00 GST match and red `VARIANCE` badge for INR 62.00 GST discrepancy.
6. **Policy-Gated Human Decision**: In **Actions & Approvals**, observes action recommended by AI (`POST_ADJUSTMENT` INR 150.00, state `PENDING_APPROVAL`).
   - Clicks **Reject** or **Approve**.
   - With approval confirmed by `senior_controller`, clicks **Execute**. System posts bounded ledger adjustment.
7. **Immutable Audit Trail**: Navigates to **Audit Trail** to see the chronological event trace with actors, timestamps, hashes, and evidence IDs.
