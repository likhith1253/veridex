import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.mappers.exception_mapper import domain_to_orm_exception, orm_to_domain_exception
from app.database.models import Exception as ExceptionORM, ExceptionTransaction as ExceptionTransactionORM
from app.database.utils import utcnow
from app.models.exception_record import ExceptionRecord as ExceptionDomain


class ExceptionRepository:
    """Repository for Exception persistence operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self, domain: ExceptionDomain, run_id: str, transaction_id: Optional[str] = None
    ) -> str:
        """Create a new exception and return its ID."""
        id = str(uuid.uuid4())
        orm = domain_to_orm_exception(domain, id, run_id, transaction_id, utcnow())
        self.session.add(orm)
        await self.session.flush()

        # Add exception transaction if provided
        if transaction_id:
            exc_txn = ExceptionTransactionORM(exception_id=id, transaction_id=transaction_id)
            self.session.add(exc_txn)

        await self.session.flush()
        return id

    async def get_by_id(self, id: str) -> Optional[ExceptionDomain]:
        """Get an exception by ID."""
        result = await self.session.execute(select(ExceptionORM).where(ExceptionORM.id == id))
        orm = result.scalar_one_or_none()
        return orm_to_domain_exception(orm) if orm else None

    async def get_by_run_id(self, run_id: str) -> list[ExceptionDomain]:
        """Get all exceptions for a run."""
        result = await self.session.execute(select(ExceptionORM).where(ExceptionORM.run_id == run_id))
        orms = result.scalars().all()
        return [orm_to_domain_exception(orm) for orm in orms]

    async def get_by_transaction_id(self, transaction_id: str) -> list[ExceptionDomain]:
        """Get all exceptions for a transaction."""
        result = await self.session.execute(
            select(ExceptionORM).where(ExceptionORM.transaction_id == transaction_id)
        )
        orms = result.scalars().all()
        return [orm_to_domain_exception(orm) for orm in orms]

    async def add_transaction_to_exception(self, exception_id: str, transaction_id: str) -> None:
        """Add a transaction to an exception (N:M relationship)."""
        exc_txn = ExceptionTransactionORM(exception_id=exception_id, transaction_id=transaction_id)
        self.session.add(exc_txn)
        await self.session.flush()

    async def get_exception_transactions(self, exception_id: str) -> list[str]:
        """Get all transaction IDs for an exception."""
        result = await self.session.execute(
            select(ExceptionTransactionORM.transaction_id).where(
                ExceptionTransactionORM.exception_id == exception_id
            )
        )
        return list(result.scalars().all())
