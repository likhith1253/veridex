from datetime import datetime
from typing import Optional

from app.database.models import AuditEvent as AuditEventORM
from app.models.audit_event import AuditEvent as AuditDomain


def _sanitize_for_json(obj):
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    elif isinstance(obj, float) and (obj == float("inf") or obj == float("-inf") or obj != obj):
        return None
    return obj


def domain_to_orm_audit(domain: AuditDomain, id: str, created_at: datetime) -> AuditEventORM:
    """Convert domain AuditEvent to ORM AuditEvent."""
    ts = domain.timestamp
    if ts and ts.tzinfo is not None:
        ts = ts.replace(tzinfo=None)
    elif not ts:
        ts = datetime.utcnow()
    return AuditEventORM(
        id=id,
        run_id=domain.run_id,
        transaction_id=domain.transaction_id,
        event_type=domain.event,
        stage=domain.stage,
        action=domain.event,
        timestamp=ts,
        meta_data=_sanitize_for_json(domain.evidence),
        decision=_sanitize_for_json(domain.decision),
    )


def orm_to_domain_audit(orm: AuditEventORM) -> AuditDomain:
    """Convert ORM AuditEvent to domain AuditEvent."""
    return AuditDomain(
        run_id=orm.run_id,
        transaction_id=orm.transaction_id,
        stage=orm.stage,
        event=orm.event_type,
        timestamp=orm.timestamp,
        evidence=orm.meta_data,
        decision=orm.decision,
    )
