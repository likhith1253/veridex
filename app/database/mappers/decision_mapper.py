from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.database.models import Decision as DecisionORM, DecisionAction
from app.models.decision_result import DecisionResult as DecisionDomain, DecisionAction as DomainDecisionAction


def _sanitize_for_json(obj):
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    elif isinstance(obj, float) and (obj == float("inf") or obj == float("-inf") or obj != obj):
        return None
    elif isinstance(obj, Decimal) and (obj.is_infinite() or obj.is_nan()):
        return None
    return obj


def domain_to_orm_decision(
    domain: DecisionDomain, id: str, run_id: str, match_id: Optional[str], created_at: datetime
) -> DecisionORM:
    """Convert domain DecisionResult to ORM Decision."""
    # Extract ML probability and candidate margin from evidence if present
    ml_probability = domain.evidence.get("ml_probability")
    raw_margin = domain.evidence.get("candidate_margin")
    
    candidate_margin = None
    if raw_margin is not None:
        try:
            val = Decimal(str(raw_margin))
            if not val.is_infinite() and not val.is_nan():
                candidate_margin = val
        except Exception:
            candidate_margin = None
            
    clean_evidence = _sanitize_for_json(domain.evidence)
    
    return DecisionORM(
        id=id,
        run_id=run_id,
        match_id=match_id,
        decision_action=DecisionAction(domain.action.value),
        deterministic_confidence=domain.confidence,
        ml_probability=Decimal(str(ml_probability)) if ml_probability is not None else None,
        candidate_margin=candidate_margin,
        evidence=clean_evidence,
        reason=domain.reason,
        created_at=created_at,
    )


def orm_to_domain_decision(orm: DecisionORM) -> DecisionDomain:
    """Convert ORM Decision to domain DecisionResult."""
    from app.models.decision_result import DecisionAction as DomainDecisionAction

    return DecisionDomain(
        transaction_ids=[],  # Populated from match transactions
        action=DomainDecisionAction(orm.decision_action.value),
        confidence=Decimal(orm.deterministic_confidence) if orm.deterministic_confidence else Decimal("0"),
        evidence=orm.evidence,
        reason=orm.reason,
    )
