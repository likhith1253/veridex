from datetime import datetime
from typing import Optional

from app.database.models import AuditEvent as AuditEventORM
from app.models.audit_event import AuditEvent as AuditDomain


def domain_to_orm_audit(domain: AuditDomain, id: str, created_at: datetime) -> AuditEventORM:
    """Convert domain AuditEvent to ORM AuditEvent."""
    return AuditEventORM(
        id=id,
        run_id=domain.run_id,
        transaction_id=domain.transaction_id,
        event_type=domain.event,
        stage=domain.stage,
        action=domain.event,
        timestamp=domain.timestamp,
        metadata=domain.evidence,
        decision=domain.decision,
        created_at=created_at,
    )


def orm_to_domain_audit(orm: AuditEventORM) -> AuditDomain:
    """Convert ORM AuditEvent to domain AuditEvent."""
    return AuditDomain(
        run_id=orm.run_id,
        transaction_id=orm.transaction_id,
        stage=orm.stage,
        event=orm.event_type,
        timestamp=orm.timestamp,
        evidence=orm.metadata,
        decision=orm.decision,
    )
