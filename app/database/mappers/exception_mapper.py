from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.database.models import Exception as ExceptionORM, ExceptionCategory
from app.models.exception_record import ExceptionRecord as ExceptionDomain, ExceptionCategory as DomainExceptionCategory


def domain_to_orm_exception(
    domain: ExceptionDomain, id: str, run_id: str, transaction_id: Optional[str], created_at: datetime
) -> ExceptionORM:
    """Convert domain ExceptionRecord to ORM Exception."""
    return ExceptionORM(
        id=id,
        run_id=run_id,
        transaction_id=transaction_id,
        exception_category=ExceptionCategory(domain.category.value),
        status="open",
        confidence=domain.confidence,
        financial_exposure=domain.financial_exposure,
        expected_cost=domain.expected_cost,
        explanation=domain.explanation,
        evidence=domain.evidence,
        recommended_action=domain.recommended_action,
        resolved=domain.resolved,
        resolved_at=None,
        created_at=created_at,
    )


def orm_to_domain_exception(orm: ExceptionORM) -> ExceptionDomain:
    """Convert ORM Exception to domain ExceptionRecord."""
    from app.models.exception_record import ExceptionCategory as DomainExceptionCategory

    return ExceptionDomain(
        transaction_id=orm.transaction_id or "",
        category=DomainExceptionCategory(orm.exception_category.value),
        confidence=Decimal(orm.confidence),
        financial_exposure=Decimal(orm.financial_exposure),
        expected_cost=Decimal(orm.expected_cost),
        explanation=orm.explanation,
        evidence=orm.evidence,
        recommended_action=orm.recommended_action,
        resolved=orm.resolved,
    )
