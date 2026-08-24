import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.mappers.investigation_mapper import (
    domain_to_orm_investigation,
    orm_to_domain_investigation,
)
from app.database.models.investigation import Investigation as InvestigationORM
from app.models.investigation_result import InvestigationConclusion


class InvestigationRepository:
    """Repository for Investigation persistence operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, domain: InvestigationConclusion) -> str:
        """Create or persist a new investigation record and return its internal DB ID."""
        # Check if already exists by investigation_id (idempotency check)
        existing = await self.get_by_investigation_id(domain.investigation_id)
        if existing:
            return existing.investigation_id

        db_id = str(uuid.uuid4())
        created_at = domain.created_at
        if created_at and created_at.tzinfo is not None:
            created_at = created_at.replace(tzinfo=None)
        elif not created_at:
            created_at = datetime.utcnow()
        orm = domain_to_orm_investigation(domain, db_id, created_at)
        self.session.add(orm)
        await self.session.flush()
        return db_id

    async def get_by_id(self, db_id: str) -> Optional[InvestigationConclusion]:
        """Get an investigation by internal database UUID."""
        result = await self.session.execute(
            select(InvestigationORM).where(InvestigationORM.id == db_id)
        )
        orm = result.scalar_one_or_none()
        return orm_to_domain_investigation(orm) if orm else None

    async def get_by_investigation_id(self, investigation_id: str) -> Optional[InvestigationConclusion]:
        """Get an investigation by domain investigation_id / idempotency key."""
        result = await self.session.execute(
            select(InvestigationORM).where(InvestigationORM.investigation_id == investigation_id)
        )
        orm = result.scalar_one_or_none()
        return orm_to_domain_investigation(orm) if orm else None

    async def get_by_exception_id(self, exception_id: str) -> list[InvestigationConclusion]:
        """Get all investigations for a given exception."""
        result = await self.session.execute(
            select(InvestigationORM).where(InvestigationORM.exception_id == exception_id)
        )
        orms = result.scalars().all()
        return [orm_to_domain_investigation(orm) for orm in orms]

    async def get_by_run_id(self, run_id: str) -> list[InvestigationConclusion]:
        """Get all investigations for a given reconciliation run."""
        result = await self.session.execute(
            select(InvestigationORM).where(InvestigationORM.run_id == run_id)
        )
        orms = result.scalars().all()
        return [orm_to_domain_investigation(orm) for orm in orms]
