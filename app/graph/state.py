from dataclasses import dataclass, field
from decimal import Decimal
from enum import Enum
from typing import Any, Optional


class InvestigationStage(str, Enum):
    LOADED = "loaded"
    EVIDENCE_READY = "evidence_ready"
    ANALYZED = "analyzed"
    RISK_EVALUATED = "risk_evaluated"
    CLASSIFIED = "classified"
    HISTORY_RETRIEVED = "history_retrieved"
    LLM_COMPLETE = "llm_complete"
    VALIDATED = "validated"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class InvestigationState:
    """Explicit, serializable state passed between LangGraph nodes."""
    # Inputs (immutable)
    investigation_id: str
    exception_id: str
    run_id: str
    decision: Optional[dict[str, Any]] = None
    transactions: list[dict[str, Any]] = field(default_factory=list)

    # Evidence
    transaction_evidence: dict[str, Any] = field(default_factory=dict)
    historical_cases: list[dict[str, Any]] = field(default_factory=list)

    # Deterministic analysis
    amount_delta: str = "0"
    is_duplicate: bool = False
    deterministic_confidence: str = "0"
    root_cause: str = ""
    explanation: str = ""
    recommended_action: str = "investigate_further"

    # Risk evaluation
    financial_exposure: str = "0"
    expected_cost: str = "0"
    risk_bucket: str = "low"
    requires_llm: bool = False

    # Classification
    classified_category: str = "unexplained"
    classification_confidence: str = "0"
    requires_human_review: bool = False

    # LLM execution & validation
    llm_result: Optional[dict[str, Any]] = None
    llm_invoked: bool = False
    llm_error: Optional[str] = None
    method: str = "deterministic"

    # Execution control
    stage: InvestigationStage = InvestigationStage.LOADED
    error: Optional[str] = None
    final_conclusion: Optional[dict[str, Any]] = None
