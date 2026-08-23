from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.database.models import Decision as DecisionORM, DecisionAction
from app.models.decision_result import DecisionResult as DecisionDomain, DecisionAction as DomainDecisionAction


def domain_to_orm_decision(
    domain: DecisionDomain, id: str, run_id: str, match_id: Optional[str], created_at: datetime
) -> DecisionORM:
    """Convert domain DecisionResult to ORM Decision."""
    return DecisionORM(
        id=id,
        run_id=run_id,
        match_id=match_id,
        decision_action=DecisionAction(domain.action.value),
        deterministic_confidence=domain.confidence,
        ml_probability=None,
        candidate_margin=None,
        evidence=domain.evidence,
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
