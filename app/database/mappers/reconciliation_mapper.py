from datetime import datetime

from app.database.models import (
    ReconciliationItem as ReconciliationItemORM,
    ReconciliationRun as ReconciliationRunORM,
    ReconciliationRunStatus,
)
from app.models.reconciliation_run import ReconciliationRun as ReconciliationRunDomain, RunStatus


def domain_to_orm_run(domain: ReconciliationRunDomain, id: str, created_at: datetime) -> ReconciliationRunORM:
    """Convert domain ReconciliationRun to ORM ReconciliationRun."""
    return ReconciliationRunORM(
        id=id,
        run_id=domain.run_id,
        status=ReconciliationRunStatus(domain.status.value),
        started_at=domain.started_at,
        completed_at=domain.ended_at,
        gateway_count=domain.gateway_count,
        ledger_count=domain.ledger_count,
        bank_count=domain.bank_count,
        match_count=domain.match_count,
        exception_count=domain.exception_count,
        summary=domain.summary,
        created_at=created_at,
    )


def orm_to_domain_run(orm: ReconciliationRunORM) -> ReconciliationRunDomain:
    """Convert ORM ReconciliationRun to domain ReconciliationRun."""
    from app.models.reconciliation_run import RunStatus as DomainStatus

    return ReconciliationRunDomain(
        run_id=orm.run_id,
        created_at=orm.created_at,
        started_at=orm.started_at,
        ended_at=orm.completed_at,
        status=DomainStatus(orm.status.value),
        gateway_count=orm.gateway_count,
        ledger_count=orm.ledger_count,
        bank_count=orm.bank_count,
        match_count=orm.match_count,
        exception_count=orm.exception_count,
        summary=orm.summary,
    )
