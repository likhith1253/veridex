import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.mappers.decision_mapper import domain_to_orm_decision, orm_to_domain_decision
from app.database.models import Decision as DecisionORM
from app.database.utils import utcnow
from app.models.decision_result import DecisionResult as DecisionDomain


class DecisionRepository:
    """Repository for Decision persistence operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self, domain: DecisionDomain, run_id: str, match_id: Optional[str] = None
    ) -> str:
        """Create a new decision and return its ID."""
        id = str(uuid.uuid4())
        orm = domain_to_orm_decision(domain, id, run_id, match_id, utcnow())
        self.session.add(orm)
        await self.session.flush()
        return id

    async def get_by_id(self, id: str) -> Optional[DecisionDomain]:
        """Get a decision by ID."""
        result = await self.session.execute(select(DecisionORM).where(DecisionORM.id == id))
        orm = result.scalar_one_or_none()
        return orm_to_domain_decision(orm) if orm else None

    async def get_by_run_id(self, run_id: str) -> list[DecisionDomain]:
        """Get all decisions for a run."""
        result = await self.session.execute(select(DecisionORM).where(DecisionORM.run_id == run_id))
        orms = result.scalars().all()
        return [orm_to_domain_decision(orm) for orm in orms]

    async def get_by_match_id(self, match_id: str) -> Optional[DecisionDomain]:
        """Get a decision by match ID."""
        result = await self.session.execute(select(DecisionORM).where(DecisionORM.match_id == match_id))
        orm = result.scalar_one_or_none()
        return orm_to_domain_decision(orm) if orm else None
