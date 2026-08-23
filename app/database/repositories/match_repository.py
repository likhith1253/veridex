import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.mappers.match_mapper import domain_to_orm_match, orm_to_domain_match
from app.database.models import Match as MatchORM, MatchTransaction as MatchTransactionORM
from app.models.match_result import MatchResult as MatchDomain


class MatchRepository:
    """Repository for Match persistence operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, domain: MatchDomain, run_id: str) -> str:
        """Create a new match and return its ID."""
        id = str(uuid.uuid4())
        created_at = datetime.utcnow()
        orm = domain_to_orm_match(domain, id, run_id, created_at)
        self.session.add(orm)
        await self.session.flush()

        # Add match transactions
        for txn_id in domain.transaction_ids:
            match_txn = MatchTransactionORM(match_id=id, transaction_id=txn_id)
            self.session.add(match_txn)

        await self.session.flush()
        return id

    async def get_by_id(self, id: str) -> Optional[MatchDomain]:
        """Get a match by ID."""
        result = await self.session.execute(select(MatchORM).where(MatchORM.id == id))
        orm = result.scalar_one_or_none()
        if not orm:
            return None

        # Get transaction IDs
        txn_result = await self.session.execute(
            select(MatchTransactionORM.transaction_id).where(MatchTransactionORM.match_id == id)
        )
        transaction_ids = list(txn_result.scalars().all())

        return orm_to_domain_match(orm, transaction_ids)

    async def get_by_run_id(self, run_id: str) -> list[MatchDomain]:
        """Get all matches for a run."""
        result = await self.session.execute(select(MatchORM).where(MatchORM.run_id == run_id))
        orms = result.scalars().all()

        matches = []
        for orm in orms:
            txn_result = await self.session.execute(
                select(MatchTransactionORM.transaction_id).where(MatchTransactionORM.match_id == orm.id)
            )
            transaction_ids = list(txn_result.scalars().all())
            matches.append(orm_to_domain_match(orm, transaction_ids))

        return matches
