from datetime import datetime, timezone
from decimal import Decimal

from app.database.models.investigation import Investigation as InvestigationORM
from app.models.exception_record import ExceptionCategory
from app.models.investigation_result import (
    InvestigationConclusion,
    InvestigationMethod,
    InvestigationStatus,
)


def domain_to_orm_investigation(
    domain: InvestigationConclusion,
    id: str,
    created_at: datetime,
) -> InvestigationORM:
    """Convert domain InvestigationConclusion to ORM Investigation."""
    return InvestigationORM(
        id=id,
        investigation_id=domain.investigation_id,
        exception_id=domain.exception_id,
        run_id=domain.run_id,
        method=domain.method.value,
        root_cause=domain.root_cause,
        classification=domain.classification.value,
        confidence=Decimal(str(domain.confidence)),
        financial_exposure=Decimal(str(domain.financial_exposure)),
        expected_cost=Decimal(str(domain.expected_cost)),
        recommended_action=domain.recommended_action,
        requires_human_review=domain.requires_human_review,
        llm_invoked=domain.llm_invoked,
        llm_error=domain.llm_error,
        historical_cases_used=domain.historical_cases_used,
        evidence=domain.evidence,
        llm_raw_output=None,
        status=domain.status.value if hasattr(domain, "status") else "completed",
        created_at=created_at,
    )


def orm_to_domain_investigation(orm: InvestigationORM) -> InvestigationConclusion:
    """Convert ORM Investigation to domain InvestigationConclusion."""
    return InvestigationConclusion(
        investigation_id=orm.investigation_id,
        exception_id=orm.exception_id,
        run_id=orm.run_id,
        method=InvestigationMethod(orm.method),
        root_cause=orm.root_cause,
        classification=ExceptionCategory(orm.classification),
        confidence=Decimal(str(orm.confidence)),
        financial_exposure=Decimal(str(orm.financial_exposure)),
        expected_cost=Decimal(str(orm.expected_cost)),
        recommended_action=orm.recommended_action,
        requires_human_review=orm.requires_human_review,
        evidence=orm.evidence,
        llm_invoked=orm.llm_invoked,
        llm_error=orm.llm_error,
        historical_cases_used=orm.historical_cases_used,
        status=InvestigationStatus(orm.status),
        created_at=orm.created_at,
    )
