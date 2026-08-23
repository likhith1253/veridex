import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.mappers.reconciliation_mapper import domain_to_orm_run, orm_to_domain_run
from app.database.models import ReconciliationItem as ReconciliationItemORM, ReconciliationRun as ReconciliationRunORM
from app.models.reconciliation_run import ReconciliationRun as ReconciliationRunDomain


class ReconciliationRepository:
    """Repository for ReconciliationRun persistence operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_run(self, domain: ReconciliationRunDomain) -> str:
        """Create a new reconciliation run and return its ID."""
        id = str(uuid.uuid4())
        created_at = datetime.utcnow()
        orm = domain_to_orm_run(domain, id, created_at)
        self.session.add(orm)
        await self.session.flush()
        return id

    async def get_run_by_id(self, id: str) -> Optional[ReconciliationRunDomain]:
        """Get a reconciliation run by ID."""
        result = await self.session.execute(select(ReconciliationRunORM).where(ReconciliationRunORM.id == id))
        orm = result.scalar_one_or_none()
        return orm_to_domain_run(orm) if orm else None

    async def get_run_by_run_id(self, run_id: str) -> Optional[ReconciliationRunDomain]:
        """Get a reconciliation run by run_id."""
        result = await self.session.execute(
            select(ReconciliationRunORM).where(ReconciliationRunORM.run_id == run_id)
        )
        orm = result.scalar_one_or_none()
        return orm_to_domain_run(orm) if orm else None

    async def update_run_status(self, id: str, status: str) -> None:
        """Update reconciliation run status."""
        result = await self.session.execute(select(ReconciliationRunORM).where(ReconciliationRunORM.id == id))
        orm = result.scalar_one_or_none()
        if orm:
            orm.status = status
            await self.session.flush()

    async def create_item(self, run_id: str, transaction_id: str, processing_status: str) -> str:
        """Create a reconciliation item and return its ID."""
        id = str(uuid.uuid4())
        now = datetime.utcnow()
        orm = ReconciliationItemORM(
            id=id,
            run_id=run_id,
            transaction_id=transaction_id,
            processing_status=processing_status,
            resulting_action=None,
            created_at=now,
            updated_at=now,
        )
        self.session.add(orm)
        await self.session.flush()
        return id

    async def get_items_by_run_id(self, run_id: str) -> list[ReconciliationItemORM]:
        """Get all reconciliation items for a run."""
        result = await self.session.execute(
            select(ReconciliationItemORM).where(ReconciliationItemORM.run_id == run_id)
        )
        return list(result.scalars().all())
