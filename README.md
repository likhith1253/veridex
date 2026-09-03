# VERIDEX
### AI Financial Control & Reconciliation Engine

> *"Find the discrepancy. Prove the cause. Control the action."*

Veridex is an autonomous, auditable AI financial reconciliation, investigation, and control system.

## Goal

The system reconciles three fragmented financial data sources:
1. Payment gateway settlement data (Razorpay feeds & webhooks)
2. Internal order/payment ledger
3. Bank statement feeds

## Architecture

The system uses:
- Deterministic matching
- ML candidate scoring
- Selective LLM judgment
- Investigation tools/agents
- Root-cause classification
- Financial risk / expected-cost calculation
- Audit trails
- Evaluation against ground truth

**Tech Stack:**
- Streamlit frontend
- FastAPI backend
- PostgreSQL database
- Qdrant vector database
- LangGraph
- Pydantic

## Development Status

### Currently Implemented
- Repository foundation
- Canonical Pydantic models
- Synthetic financial data simulator
- Ground truth generation
- Normalization
- Deterministic candidate generation
- Deterministic matching
- ML feature engineering
- Logistic Regression baseline
- XGBoost candidate scoring
- Decision policy
- Financial consistency utility
- Tests for the above

### Planned Next Components
- PostgreSQL persistence
- Reconciliation orchestrator
- Evaluation engine
- Investigation engine
- LLM reasoning
- Root-cause agent
- Risk engine
- Audit service integration
- FastAPI
- Streamlit

## Documentation

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed system architecture, component responsibilities, and design principles.
