# Architecture Documentation

## Project Purpose

VERIDEX is an AI-assisted financial reconciliation, investigation, and control system that reconciles three fragmented data sources:
1. Payment gateway settlement data (Razorpay feeds & signed webhooks)
2. Internal order/payment ledger
3. Bank statement feed

**Design Priorities:**
- Correctness
- Financial safety
- Explainability
- Auditability
- Calibrated confidence
- Deterministic verification
- Selective ML/LLM use
- Low inference cost

**What This System Is NOT:**
- A system that relies on LLMs for core financial decisions
- A system that lets an LLM mutate financial records directly
- A generic conversational AI with no grounding — the Copilot chat interface computes real answers from the live database first and only uses an LLM to phrase the response

## System Architecture Diagram

```mermaid
graph TB
    subgraph DataSources[Data Sources]
        GW[Payment Gateway Feed]
        LD[Internal Ledger]
        BK[Bank Statement Feed]
    end

    subgraph Ingestion[Ingestion Layer]
        DI[Batch Ingestion API]
        NM[Normalization]
        WH[Razorpay Webhooks - HMAC signed]
    end

    subgraph Canonical[Canonical Models]
        CT[Canonical Transactions]
    end

    subgraph Persistence[Persistence Layer]
        PG[(PostgreSQL)]
        QD[(Qdrant - auxiliary retrieval)]
    end

    subgraph Matching[Matching Layer]
        DMG[Deterministic Matching]
        CG[Candidate Generation]
        MLS[ML Scoring]
        DP[Decision Policy]
        EC[Exception Classifier]
    end

    subgraph Investigation[Investigation Layer]
        IE[Investigation Service]
        LLM[Groq LLM Reasoning]
        EG[Evidence Graph Builder]
    end

    subgraph Controller[Finance Controller]
        FC[Single Source of Truth - get_summary_kpis]
    end

    subgraph HITL[Human-in-the-Loop Actions]
        FA[Finance Action Service]
        POL[Policy Ceilings - server-enforced]
    end

    subgraph Settle[Settlement Intelligence]
        SI[Settlement Bank-Match Service]
    end

    subgraph QAChat[Copilot / Finance QA]
        QA[Deterministic Fact Lookup]
        QALLM[LLM Rephrasing - facts only]
    end

    subgraph Audit[Audit Layer]
        AS[Immutable Audit Service]
    end

    subgraph Evaluation[Evaluation Layer]
        EF[Canonical Benchmark Harness]
        GT[Private Ground Truth]
    end

    subgraph API[API Layer]
        FAPI[FastAPI]
    end

    subgraph Frontend[Frontend]
        NEXT[Next.js App Router]
    end

    GW --> DI
    LD --> DI
    BK --> DI
    GW --> WH
    DI --> NM
    WH --> NM
    NM --> CT
    CT --> PG
    CT --> DMG
    DMG --> CG
    CG --> MLS
    MLS --> DP
    DP -->|AUTO_MATCH| PG
    DP -->|MANUAL_REVIEW| EC
    DP -->|REJECT| EC
    EC --> IE
    IE --> LLM
    IE --> EG
    EG --> PG
    LLM --> PG
    PG --> FC
    FC --> FA
    FA --> POL
    POL --> AS
    PG --> SI
    SI --> PG
    FC --> QA
    QA --> QALLM
    PG --> QA
    DP --> AS
    AS --> PG
    GT --> EF
    PG --> EF
    FC --> FAPI
    FA --> FAPI
    SI --> FAPI
    QA --> FAPI
    EF --> FAPI
    FAPI --> NEXT
    PG <--> QD
```

## Reconciliation Data Flow

```mermaid
graph LR
    A[Gateway/Ledger/Bank feeds] --> B[Ingestion + Normalization]
    B --> C[Canonical Transactions]
    C --> D[Persistence - PostgreSQL]
    C --> E[Deterministic Matching]
    E --> F[Candidate Generation]
    F --> G[ML Scoring]
    G --> H[Decision Policy]
    H -->|AUTO_MATCH| I[Match Record]
    H -->|MANUAL_REVIEW / REJECT| J[Exception Classifier]
    J --> K[Investigation Service]
    K -->|Ambiguous / High value| L[Groq LLM Reasoning]
    K --> M[Evidence Graph - real linked legs]
    L --> N[Root Cause + Recommended Action]
    M --> N
    N --> O[Finance Action Service - HITL]
    O --> P[Immutable Audit Trail]
    I --> D
    P --> D
```

## Decision Flow

```mermaid
graph TD
    A[Canonical Transactions] --> B[Deterministic Matching]
    B -->|Exact 3-way match| C[AUTO_MATCH]
    B -->|No exact match| D[Candidate Generation]
    D --> E[ML Scoring]
    E --> F{Decision Policy}
    F -->|Currency mismatch or financial inconsistency| R[REJECT]
    F -->|Score >= threshold| G{Confidence Check}
    G -->|High confidence| C
    G -->|Medium confidence| H[MANUAL_REVIEW]
    F -->|Score below threshold| I[Exception - Unresolved]
    H --> J[Exception Classifier]
    I --> J
    R --> J
    J --> K[Investigation Service]
    K --> L{High value or ambiguous?}
    L -->|Yes| M[Groq LLM Reasoning]
    L -->|No| N[Rule-Based Classification]
    M --> O[Root Cause + Evidence Graph]
    N --> O
    O --> P[Finance Controller - risk & exposure]
    P --> Q[Audit Logging]
```

## Investigation Flow

```mermaid
graph TD
    A[Exception Classified] --> B{Deterministic explanation found?}
    B -->|Yes| C[Rule-Based Root Cause]
    B -->|No| D[Groq LLM Investigation]
    D --> E[Structured, Validated Root Cause]
    C --> F[Evidence Graph Builder]
    E --> F
    F --> G["Real Gateway -> Ledger -> Bank pipeline<br/>built from linked transaction records,<br/>not illustrative placeholders"]
    G --> H[Investigation Dossier]
    H --> I[Finance Action Service - recommend action]
    I --> J[Human Approval / Rejection]
    J --> K[Audit Service]
```

## Persistence Architecture

```mermaid
graph TB
    subgraph PostgreSQL[PostgreSQL - System of Record]
        RR[reconciliation_runs]
        TX[transactions]
        MT[matches / match_transactions]
        DC[decisions]
        EX[exceptions / exception_transactions]
        IR[investigations]
        FAT[finance_actions]
        AE[audit_events]
    end

    subgraph Qdrant[Qdrant - Auxiliary Retrieval]
        IK[Investigation Knowledge]
        HE[Historical Exceptions]
        SE[Semantic Evidence]
    end

    TX --> RR
    RR --> MT
    MT --> DC
    DC --> EX
    EX --> IR
    IR --> FAT
    DC --> AE
    IR <--> Qdrant
```

## Component Responsibilities

### Data Ingestion
- **Responsibility**: Accept Gateway/Ledger/Bank records via batch ingestion API or signed Razorpay webhooks
- **Inputs**: Batch payloads, HMAC-signed webhook events
- **Outputs**: Raw records ready for normalization
- **Must NOT Do**: Validation logic beyond schema shape, matching, business decisions

### Normalization
- **Responsibility**: Transform raw records into canonical transaction format, handle field mapping and currency
- **Inputs**: Raw ingested records
- **Outputs**: Canonical transaction objects
- **Must NOT Do**: Matching, persistence side effects beyond normalization, business logic

### Canonical Models
- **Responsibility**: Pydantic models for canonical transactions, matches, decisions, exceptions
- **Must NOT Do**: Business logic, persistence, matching logic

### Deterministic Matcher (`app/matching/deterministic.py`)
- **Responsibility**: Exact 3-way matching by ID, amount, and date across Gateway/Ledger/Bank
- **Must NOT Do**: LLM calls, ML inference, final routing decisions

### ML Scorer (`app/matching/ml_scorer.py`)
- **Responsibility**: Score ambiguous candidate matches the deterministic matcher couldn't resolve
- **Must NOT Do**: LLM calls, database queries, final decisions

### Decision Policy (`app/matching/decision.py`)
- **Responsibility**: Apply financial-consistency and threshold rules to route each pair to AUTO_MATCH, MANUAL_REVIEW, or REJECT
- **Must NOT Do**: LLM calls, database mutations, investigation logic

### Exception Classifier (`app/matching/exception_classifier.py`)
- **Responsibility**: Categorize every unresolved record by root-cause type (missing bank/ledger leg, timing lag, fee/tax mismatch, duplicate, amount mismatch) instead of a generic "unresolved" bucket
- **Must NOT Do**: Financial record mutations

### Reconciliation Service (`app/services/reconciliation.py`)
- **Responsibility**: Coordinate the end-to-end reconciliation pipeline with persistence, pairing the correct transaction legs (gateway/bank preferred pairing) before invoking the decision policy
- **Must NOT Do**: CSV/payload parsing, ML training, API logic

### Investigation Service (`app/investigation/service.py`)
- **Responsibility**: Run LLM-assisted root-cause investigation per exception, and build the real evidence-graph pipeline (Gateway → Ledger → Bank) from the transactions actually linked to that exception via the `exception_transactions` join table — never illustrative placeholder data
- **Must NOT Do**: Direct financial record mutations, unstructured/unvalidated LLM output

### Finance Controller (`app/services/finance_controller.py`)
- **Responsibility**: Single source of truth for every KPI shown anywhere in the system (`get_summary_kpis`) — match rate, exceptions, exposure, aging. Every dashboard, the benchmark panel, and Copilot answers all read from this one computation, never from independently-derived per-page numbers
- **Must NOT Do**: Presentation logic, direct HTTP handling

### Finance Action Service (`app/services/finance_action_service.py`)
- **Responsibility**: Human-in-the-loop action lifecycle — Pending Approval → Approved → Executed, or → Rejected — with policy ceilings enforced server-side (max single adjustment, max write-off limit)
- **Must NOT Do**: Execute an action without human approval; bypass policy ceilings

### Settlement Intelligence Service (`app/services/razorpay_settlement_intelligence_service.py`)
- **Responsibility**: Match what the gateway reports as settled (gross, fee, tax, expected net) against the real bank credit, by UTR/reference-number lookup — the same live lookup powers both the settlement list and detail views
- **Must NOT Do**: Report a bank match that hasn't been verified against an actual bank transaction record

### Copilot / Finance QA Service (`app/services/copilot_service.py`, `app/services/finance_qa.py`)
- **Responsibility**: Answer natural-language questions two ways — (1) live-data questions, computed deterministically from the database first, LLM only rephrases the verified fact; (2) "how does this product work" questions, answered from a fixed knowledge base, LLM only rephrases
- **Must NOT Do**: Invent a number not backed by a deterministic query

### Audit Service
- **Responsibility**: Log every match, decision, action, and investigation event — immutable, append-only
- **Must NOT Do**: Business logic, decision making

### FastAPI (API Layer)
- **Responsibility**: Expose REST endpoints for reconciliation, exceptions, investigations, actions, settlements, webhooks, and copilot
- **Must NOT Do**: Business logic, direct database access (use services)

### Frontend (Next.js App Router)
- **Responsibility**: Present the Control Center, Reconciliation dashboard, Exception dossiers, Settlements, Review Actions, Benchmark, and Copilot chat — all reading from the same API layer, none computing its own numbers independently
- **Must NOT Do**: Business logic, direct database access

### Evaluation Harness (`eval/`)
- **Responsibility**: Score reconciliation quality against a private, seed-based ground truth — kept fully separate from live usage so its numbers stay reproducible and untouched by demo data
- **Must NOT Do**: Read or write production data; be modified to make a demo look better

## Database Architecture

### PostgreSQL as System of Record

**PostgreSQL is the authoritative source of truth for all structured financial state.**

### Relational Schema (Implemented)

```mermaid
erDiagram
    transactions ||--o{ reconciliation_items : "references"
    transactions ||--o{ match_transactions : "references"
    transactions ||--o{ exception_transactions : "references"
    transactions ||--o{ audit_events : "references"

    reconciliation_runs ||--o{ reconciliation_items : "contains"
    reconciliation_runs ||--o{ matches : "contains"
    reconciliation_runs ||--o{ decisions : "contains"
    reconciliation_runs ||--o{ exceptions : "contains"
    reconciliation_runs ||--o{ audit_events : "logs"

    matches ||--o{ match_transactions : "contains"
    matches ||--o{ decisions : "references"

    exceptions ||--o{ exception_transactions : "contains"
    exceptions ||--o{ investigations : "produces"
    exceptions ||--o{ finance_actions : "recommends"

    transactions {
        uuid id PK
        string domain_transaction_id
        string source
        string reference_number
        string order_id
        decimal amount
        string currency
        datetime timestamp
        string narration
        decimal fee
        decimal tax
        string status
        jsonb metadata
        datetime created_at
    }

    reconciliation_runs {
        uuid id PK
        string run_id UK
        string status
        datetime started_at
        datetime completed_at
        int gateway_count
        int ledger_count
        int bank_count
        int match_count
        int exception_count
        string summary
        datetime created_at
    }

    reconciliation_items {
        uuid id PK
        uuid run_id FK "RESTRICT"
        uuid transaction_id FK "RESTRICT"
        string processing_status
        string resulting_action
        datetime created_at
        datetime updated_at
    }

    matches {
        uuid id PK
        uuid run_id FK "RESTRICT"
        string match_type
        decimal confidence
        string reason
        jsonb evidence
        datetime created_at
    }

    match_transactions {
        uuid match_id FK, PK "RESTRICT"
        uuid transaction_id FK, PK "RESTRICT"
    }

    decisions {
        uuid id PK
        uuid run_id FK "RESTRICT"
        uuid match_id FK "RESTRICT"
        string decision_action
        decimal deterministic_confidence
        decimal ml_probability
        decimal candidate_margin
        jsonb evidence
        string reason
        datetime created_at
    }

    exceptions {
        uuid id PK
        uuid run_id FK "RESTRICT"
        uuid transaction_id FK "RESTRICT"
        string exception_category
        string status
        decimal confidence
        decimal financial_exposure
        decimal expected_cost
        string explanation
        jsonb evidence
        string recommended_action
        boolean resolved
        datetime resolved_at
        datetime created_at
    }

    exception_transactions {
        uuid exception_id FK, PK "RESTRICT"
        uuid transaction_id FK, PK "RESTRICT"
    }

    investigations {
        string investigation_id PK
        uuid exception_id FK "RESTRICT"
        string root_cause
        decimal confidence
        string method
        boolean llm_invoked
        boolean requires_human_review
        datetime created_at
    }

    finance_actions {
        string action_id PK
        string entity_type
        string entity_id
        string action_type
        decimal amount
        string status
        string recommended_by
        string authorized_by
        datetime executed_at
        datetime created_at
    }

    audit_events {
        uuid id PK
        uuid run_id FK "RESTRICT"
        uuid transaction_id FK "RESTRICT"
        string event_type
        string stage
        string action
        datetime timestamp
        jsonb metadata
        jsonb decision
    }
```

**Key Design Decisions:**
- Unique constraint on (source, domain_transaction_id) for transactions to prevent duplicates
- N:M junction tables (match_transactions, exception_transactions) for proper many-to-many relationships
- RESTRICT for all foreign keys (no cascade delete) to prevent accidental data loss
- Decimal type for all financial values to ensure precision
- JSONB for flexible fields (evidence, metadata) that may vary per record
- Indexes on frequently queried fields (run_id, transaction_id, timestamps, etc.)

### Qdrant Boundary

**Qdrant is NOT a source of truth for financial data.**

**Use Cases:**
- Investigation knowledge base (historical case retrieval)
- Semantic retrieval of evidence for investigations
- Exception pattern similarity search

**Explicit Boundaries:**
- NOT required for core reconciliation path
- NOT used for deterministic matching
- NOT used for financial state storage
- Results from Qdrant are advisory only, not authoritative

## LLM Boundary

**Prominent Rule: LLM MUST NOT be used for every transaction.**

**Target Flow:**
```
Deterministic → ML → Decision → Only unresolved/high-value/ambiguous → Investigation → LLM
```

**LLM Usage Constraints:**
- LLM must not directly mutate financial records
- LLM outputs must be structured and validated against Pydantic schemas
- LLM calls are gated by decision policy (only for REVIEW/UNRESOLVED cases) and by the Copilot's deterministic-fact-first design
- LLM is used for explanation, investigation, and rephrasing verified facts — never for matching
- LLM reasoning is not authoritative financial truth

**When LLM IS Used:**
- Per-exception root-cause investigation
- Copilot answer phrasing (after the real fact is computed)
- "How does this product work" knowledge answers (phrasing only, over a fixed knowledge base)

**When LLM is NOT Used:**
- Deterministic matching
- Candidate generation
- ML scoring
- Threshold-based decisions
- Evidence-graph construction (built directly from linked transaction records)

## Financial Safety Principles

1. **Decimal for monetary calculations**: Never use floating point for financial state
2. **Never force ambiguous match**: When uncertain, escalate rather than guess
3. **ML probability is not certainty**: High ML score ≠ guaranteed match
4. **LLM reasoning is not authoritative**: LLM outputs require validation
5. **Deterministic evidence has priority**: Exact matches override ML/LLM suggestions
6. **Every automated decision must have evidence**: Audit trail required
7. **Every important state change must be auditable**: No silent mutations
8. **Uncertain cases must be escalated**: Better to leave unresolved than to incorrectly match
9. **Every financial action requires human authorization**: No autonomous execution, ever
10. **Single source of truth**: Every displayed number is derived from one computation layer (`get_summary_kpis`), never independently recomputed per page

**False Positive Prevention:**
- False positive financial matches are more dangerous than unresolved cases
- Decision thresholds should be conservative
- High-value transactions require higher confidence

## Data Flow

**Complete Flow:**

```
Gateway/Ledger/Bank feeds (batch ingest or signed webhooks)
  → Normalization
  → Canonical Transactions
  → Persistence (PostgreSQL)
  → Deterministic Matching
  → Candidate Generation
  → ML Scoring
  → Decision Policy
  → AUTO_MATCH / MANUAL_REVIEW / REJECT
  → Exception Classifier (if not AUTO_MATCH)
  → Investigation Service (LLM-assisted root cause + evidence graph)
  → Finance Controller (risk, exposure, single-source KPIs)
  → Finance Action Service (human-authorized corrective action)
  → Immutable Audit Trail
  → Final Result, surfaced identically across every frontend page
```

## Evaluation Architecture

**Ground Truth Usage:**
- Private, seed-based ground truth used ONLY for the canonical benchmark harness under `eval/`
- Ground truth must NOT be treated as runtime truth
- Live reconciliation runs do not depend on the evaluation harness, and the harness is never modified to make a demo look better

**Evaluation Dimensions:**
- Precision (correct matches / total matches)
- Recall (correct matches / total true matches)
- False match rate (incorrect matches / total matches)
- Unresolved rate (unresolved / total transactions)
- Calibration (predicted confidence vs actual correctness)
- Exception classification accuracy
- Financial exposure incorrectly matched
- Investigation accuracy
- Cost-weighted error
- Latency
- LLM invocation rate (should be low)

**Emphasis:**
- False positive financial matches are more dangerous than unresolved cases
- Evaluation metrics should reflect this risk asymmetry

## Architecture Invariants

**Rules:**

1. Do not bypass canonical models
2. Do not put database code into matching algorithms
3. Do not put API logic into business logic
4. Do not put frontend presentation logic into backend services
5. Do not make LLM calls from deterministic matching
6. Do not make LLM calls for every transaction
7. Do not replace deterministic rules with an LLM
8. Do not use Qdrant as a financial system of record
9. Do not silently change decision thresholds
10. Do not introduce new architecture without updating this document
11. Do not introduce dependencies without justification
12. Preserve existing working components unless a real defect requires change
13. Never let a page compute its own KPI independently of the Finance Controller
14. Never modify the canonical evaluation harness (`eval/`) to inflate a benchmark score

## Current Implementation Status

### Implemented

- Canonical Pydantic models and repository layer
- Synthetic financial data simulator and ground truth generation
- Normalization, deterministic candidate generation, deterministic 3-way matching
- ML feature engineering, Logistic Regression baseline, XGBoost candidate scoring
- Decision policy with financial-consistency checks
- PostgreSQL persistence layer (async SQLAlchemy + Alembic migrations)
- Reconciliation orchestrator service
- Exception classification by root-cause category
- LLM-assisted investigation service with real evidence-graph construction
- Finance Controller as single source of truth for all KPIs
- Human-in-the-loop Finance Action Service with policy ceilings and audit trail
- Razorpay signed-webhook ingestion and Settlement Intelligence Service
- Copilot / Finance QA service (live-data + product-knowledge modes)
- FastAPI backend exposing all of the above
- Next.js frontend (Control Center, Reconciliation, Exceptions, Settlements, Actions, Benchmark, Copilot)
- Canonical benchmark evaluation harness against private ground truth
- Full test suite covering the above
