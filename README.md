# Project Sentinel

Project Sentinel is an AI financial reconciliation and investigation system.

## Goal

The system reconciles three financial data sources:
1. Payment gateway settlement data
2. Internal order/payment ledger
3. Bank statement

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

Phase 1: Repository foundation setup.
