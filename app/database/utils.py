"""Shared database utilities."""
from datetime import datetime, timezone
from typing import Optional


def utcnow() -> datetime:
    """Return current UTC time as a timezone-naive datetime for asyncpg/PostgreSQL compatibility.
    
    asyncpg requires TIMESTAMP WITHOUT TIME ZONE columns to receive naive datetimes.
    All ORM inserts must use this helper instead of datetime.now(timezone.utc).
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def ensure_run_exists(session, run_id: str) -> None:
    """Ensure a ReconciliationRun record exists for foreign key references."""
    from sqlalchemy import select
    from app.database.models import ReconciliationRun as ReconciliationRunORM

    run_check = await session.execute(select(ReconciliationRunORM).where(ReconciliationRunORM.id == run_id))
    if not run_check.scalars().first():
        now_dt = utcnow()
        new_run = ReconciliationRunORM(
            id=run_id,
            run_id=run_id,
            status="RUNNING",
            started_at=now_dt,
            completed_at=None,
            gateway_count=0,
            ledger_count=0,
            bank_count=0,
            match_count=0,
            exception_count=0,
            created_at=now_dt,
        )
        session.add(new_run)
        await session.flush()
