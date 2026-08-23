# Project Sentinel - Coding Agent Instructions

## Project Goal
Project Sentinel is an AI financial reconciliation and investigation system that reconciles:
1. Payment gateway settlement data
2. Internal order/payment ledger
3. Bank statement

## Architecture Overview
The system uses:
- Deterministic matching
- ML candidate scoring
- Selective LLM judgment
- Investigation tools/agents
- Root-cause classification
- Financial risk / expected-cost calculation
- Audit trails
- Evaluation against ground truth
- Streamlit frontend
- FastAPI backend
- PostgreSQL
- Qdrant
- LangGraph
- Pydantic

## Development Rules

### Phase Control
Development is strictly phase-controlled. The agent must:
- Work only on the current phase
- Not implement future-phase components prematurely
- Not jump ahead to implement reconciliation logic, agents, ML models, API endpoints, database logic, or LLM integration until those phases are active

### Mandatory Pre-Task Reading
Before making ANY change, the agent must read:
1. AGENTS.md (this file)
2. mistakes.txt (if it exists)

### Mistake Logging
- mistakes.txt is mandatory historical context
- If an actual mistake occurs (incorrect assumption, failed command, undo/rework), record it in mistakes.txt before finishing
- Keep mistakes.txt concise and factual
- Do not invent mistakes

### Communication
- Do not explain work to the user
- Do not provide tutorials, summaries, or suggestions
- Directly modify code and files
- Commit completed changes with short natural human-style commit messages

### Commit Messages
- At the END of the task, inspect git diff and git status
- Commit all changes belonging to the task
- Use short, natural, human-written commit messages (e.g., "set up project structure")
- Never use verbose AI-style commit messages
- Never mention AI, coding agent, prompts, phases, or generated files in commit messages

### Code Quality
- Do not introduce unnecessary dependencies, abstractions, frameworks, or files
- Preserve the project's intended architecture and goals
- Do not fabricate project requirements
- If something is genuinely ambiguous, inspect the existing repository and project files first
- Do not modify files unrelated to the current phase
