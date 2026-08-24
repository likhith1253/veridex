from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.database.models import Exception as ExceptionORM, ExceptionCategory
from app.models.exception_record import ExceptionRecord as ExceptionDomain, ExceptionCategory as DomainExceptionCategory


# Bidirectional translation between domain ExceptionCategory (investigation taxonomy)
# and ORM ExceptionCategory (database schema categories).
_DOMAIN_TO_ORM_CATEGORY: dict[DomainExceptionCategory, ExceptionCategory] = {
    DomainExceptionCategory.DUPLICATE_ENTRY: ExceptionCategory.DUPLICATE_RECORD,
    DomainExceptionCategory.FEE_MISMATCH: ExceptionCategory.AMOUNT_MISMATCH,
    DomainExceptionCategory.CURRENCY_ROUNDING: ExceptionCategory.AMOUNT_MISMATCH,
    DomainExceptionCategory.PARTIAL_REFUND: ExceptionCategory.AMOUNT_MISMATCH,
    DomainExceptionCategory.DELAYED_SETTLEMENT: ExceptionCategory.TIMING_MISMATCH,
    DomainExceptionCategory.WRONG_REFERENCE: ExceptionCategory.DATA_QUALITY,
    DomainExceptionCategory.AMBIGUOUS_MATCH: ExceptionCategory.MISSING_RECORD,
    DomainExceptionCategory.UNEXPLAINED: ExceptionCategory.UNKNOWN,
}

_ORM_TO_DOMAIN_CATEGORY: dict[ExceptionCategory, DomainExceptionCategory] = {
    ExceptionCategory.DUPLICATE_RECORD: DomainExceptionCategory.DUPLICATE_ENTRY,
    ExceptionCategory.AMOUNT_MISMATCH: DomainExceptionCategory.FEE_MISMATCH,
    ExceptionCategory.TIMING_MISMATCH: DomainExceptionCategory.DELAYED_SETTLEMENT,
    ExceptionCategory.DATA_QUALITY: DomainExceptionCategory.WRONG_REFERENCE,
    ExceptionCategory.MISSING_RECORD: DomainExceptionCategory.AMBIGUOUS_MATCH,
    ExceptionCategory.UNKNOWN: DomainExceptionCategory.UNEXPLAINED,
}


def _domain_category_to_orm(cat: DomainExceptionCategory) -> ExceptionCategory:
    if cat in _DOMAIN_TO_ORM_CATEGORY:
        return _DOMAIN_TO_ORM_CATEGORY[cat]
    # Check by string value
    val = cat.value if hasattr(cat, "value") else str(cat)
    for d_cat, o_cat in _DOMAIN_TO_ORM_CATEGORY.items():
        if d_cat.value == val:
            return o_cat
    return ExceptionCategory.UNKNOWN


def _orm_category_to_domain(cat: ExceptionCategory) -> DomainExceptionCategory:
    if cat in _ORM_TO_DOMAIN_CATEGORY:
        return _ORM_TO_DOMAIN_CATEGORY[cat]
    val = cat.value if hasattr(cat, "value") else str(cat)
    for o_cat, d_cat in _ORM_TO_DOMAIN_CATEGORY.items():
        if o_cat.value == val:
            return d_cat
    return DomainExceptionCategory.UNEXPLAINED


def domain_to_orm_exception(
    domain: ExceptionDomain, id: str, run_id: str, transaction_id: Optional[str], created_at: datetime
) -> ExceptionORM:
    """Convert domain ExceptionRecord to ORM Exception."""
    return ExceptionORM(
        id=id,
        run_id=run_id,
        transaction_id=transaction_id,
        exception_category=_domain_category_to_orm(domain.category),
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
    return ExceptionDomain(
        transaction_id=orm.transaction_id or "",
        category=_orm_category_to_domain(orm.exception_category),
        confidence=Decimal(orm.confidence),
        financial_exposure=Decimal(orm.financial_exposure),
        expected_cost=Decimal(orm.expected_cost),
        explanation=orm.explanation,
        evidence=orm.evidence,
        recommended_action=orm.recommended_action,
        resolved=orm.resolved,
    )

