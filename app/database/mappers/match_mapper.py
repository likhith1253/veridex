from datetime import datetime
from decimal import Decimal

from app.database.models import Match as MatchORM, MatchTransaction as MatchTransactionORM, MatchType
from app.models.match_result import MatchResult as MatchDomain, MatchType as DomainMatchType


def domain_to_orm_match(
    domain: MatchDomain, id: str, run_id: str, created_at: datetime
) -> MatchORM:
    """Convert domain MatchResult to ORM Match."""
    return MatchORM(
        id=id,
        run_id=run_id,
        match_type=MatchType(domain.match_type.value),
        confidence=domain.confidence,
        reason=domain.reason,
        evidence=domain.evidence or {},
        created_at=created_at,
    )


def orm_to_domain_match(orm: MatchORM, transaction_ids: list[str]) -> MatchDomain:
    """Convert ORM Match to domain MatchResult."""
    from app.models.match_result import MatchType as DomainMatchType

    return MatchDomain(
        transaction_ids=transaction_ids,
        confidence=Decimal(orm.confidence),
        reason=orm.reason,
        match_type=DomainMatchType(orm.match_type.value),
        evidence=orm.evidence,
        recommended_action=None,
    )
