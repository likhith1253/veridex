import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.mappers.transaction_mapper import domain_to_orm, orm_to_domain
from app.database.models import Transaction as TransactionORM
from app.models.transaction import Transaction as TransactionDomain


class TransactionRepository:
    """Repository for Transaction persistence operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, domain: TransactionDomain) -> str:
        """Create a new transaction and return its ID."""
        id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc)
        orm = domain_to_orm(domain, id, created_at)
        self.session.add(orm)
        await self.session.flush()
        return id

    async def get_by_id(self, id: str) -> Optional[TransactionDomain]:
        """Get a transaction by ID."""
        result = await self.session.execute(select(TransactionORM).where(TransactionORM.id == id))
        orm = result.scalar_one_or_none()
        return orm_to_domain(orm) if orm else None

    async def get_by_source_and_domain_id(
        self, source: str, domain_transaction_id: str
    ) -> Optional[TransactionDomain]:
        """Get a transaction by source and domain transaction ID."""
        result = await self.session.execute(
            select(TransactionORM).where(
                TransactionORM.source == source,
                TransactionORM.domain_transaction_id == domain_transaction_id,
            )
        )
        orm = result.scalar_one_or_none()
        return orm_to_domain(orm) if orm else None

    async def get_by_reference_number(self, reference_number: str) -> list[TransactionDomain]:
        """Get transactions by reference number."""
        result = await self.session.execute(
            select(TransactionORM).where(TransactionORM.reference_number == reference_number)
        )
        orms = result.scalars().all()
        return [orm_to_domain(orm) for orm in orms]

    async def get_by_order_id(self, order_id: str) -> list[TransactionDomain]:
        """Get transactions by order ID."""
        result = await self.session.execute(
            select(TransactionORM).where(TransactionORM.order_id == order_id)
        )
        orms = result.scalars().all()
        return [orm_to_domain(orm) for orm in orms]

    async def list_all(self) -> list[TransactionDomain]:
        """List all transactions."""
        result = await self.session.execute(select(TransactionORM))
        orms = result.scalars().all()
        return [orm_to_domain(orm) for orm in orms]
