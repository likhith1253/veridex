import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.mappers.audit_mapper import domain_to_orm_audit, orm_to_domain_audit
from app.database.models import AuditEvent as AuditEventORM
from app.database.utils import utcnow
from app.models.audit_event import AuditEvent as AuditDomain


class AuditRepository:
    """Repository for AuditEvent persistence operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, domain: AuditDomain) -> str:
        """Create a new audit event and return its ID."""
        id = str(uuid.uuid4())
        orm = domain_to_orm_audit(domain, id, utcnow())
        self.session.add(orm)
        await self.session.flush()
        return id

    async def get_by_id(self, id: str) -> Optional[AuditDomain]:
        """Get an audit event by ID."""
        result = await self.session.execute(select(AuditEventORM).where(AuditEventORM.id == id))
        orm = result.scalar_one_or_none()
        return orm_to_domain_audit(orm) if orm else None

    async def get_by_run_id(self, run_id: str) -> list[AuditDomain]:
        """Get all audit events for a run."""
        result = await self.session.execute(
            select(AuditEventORM).where(AuditEventORM.run_id == run_id).order_by(AuditEventORM.timestamp)
        )
        orms = result.scalars().all()
        return [orm_to_domain_audit(orm) for orm in orms]

    async def get_by_transaction_id(self, transaction_id: str) -> list[AuditDomain]:
        """Get all audit events for a transaction."""
        result = await self.session.execute(
            select(AuditEventORM)
            .where(AuditEventORM.transaction_id == transaction_id)
            .order_by(AuditEventORM.timestamp)
        )
        orms = result.scalars().all()
        return [orm_to_domain_audit(orm) for orm in orms]
