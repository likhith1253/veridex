# VERIDEX
### AI Financial Control & Reconciliation Engine

> *"Find the discrepancy. Prove the cause. Control the action."*

VERIDEX is an autonomous, auditable AI financial reconciliation, investigation, and control system. It reconciles three fragmented financial data sources — payment gateway settlements, the internal ledger, and the bank statement feed — and turns every unresolved discrepancy into an evidence-backed case a human can act on with confidence.

## What it does

1. **Reconciles** Gateway, Ledger, and Bank records three ways: deterministic exact-match rules first, then an ML arbitration model for the harder ambiguous cases.
2. **Classifies every exception** by root cause (missing bank leg, missing ledger leg, timing lag, fee mismatch, tax mismatch, duplicate, amount mismatch) instead of a generic "unresolved" bucket.
3. **Investigates automatically** — a per-exception LLM-assisted investigation reads the actual linked transaction evidence and writes a grounded root-cause explanation, visualized as a real Gateway → Ledger → Bank evidence pipeline showing exactly which leg broke.
4. **Tracks settlement intelligence** — matches what the gateway says it settled against what actually landed in the bank account, accounting for fees and taxes.
5. **Keeps humans in control** — every corrective action (post an adjustment, write off a discrepancy, flag for investigation) goes through a policy-gated human approval workflow with hard ceilings enforced server-side, and a full immutable audit trail.
6. **Answers questions directly** — a Copilot assistant that computes real answers from the live database first and only uses an LLM to phrase the response, plus a separate "how does this product work" knowledge mode.
7. **Evaluates itself honestly** — a protected, seed-based benchmark harness scores the reconciliation engine against ground truth, kept fully separate from live usage numbers.

## Architecture

- Deterministic matching
- ML candidate scoring
- Selective LLM judgment (Groq)
- Investigation service with evidence-graph construction
- Root-cause classification
- Financial risk / expected-cost calculation
- Human-in-the-loop finance actions with policy ceilings
- Immutable audit trail
- Canonical evaluation harness against private ground truth

See [ARCHITECTURE.md](ARCHITECTURE.md) for the original detailed system design, and [docs/architecture-diagram.svg](docs/architecture-diagram.svg) for a visual overview of the current system.

**Tech stack:**
- Frontend: Next.js (App Router, TypeScript, Tailwind, React Query, Framer Motion)
- Backend: FastAPI (async), SQLAlchemy, Alembic
- Database: PostgreSQL
- Matching/ML: scikit-learn, XGBoost
- Investigation/reasoning: LangGraph, Groq LLM
- Vector retrieval: Qdrant

## Running locally

**Backend:**
```bash
pip install -r requirements.txt
alembic upgrade head
uvicorn app.api.main:app --reload --port 8000
```

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```

Copy `.env.example` to `.env` and fill in your database URL, Razorpay webhook secret, and Groq API key before starting the backend.

## Testing

```bash
pytest tests/ -q
```

## Evaluation

The canonical benchmark (seed-based, reproducible) lives under `eval/` and is scored against `private_ground_truth.json`. Run it via:

```bash
python -m eval.run_evaluation
```
