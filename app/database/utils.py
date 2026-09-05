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
    """Ensure a ReconciliationRun record exists for foreign key references.

    Real runs are addressable by either their UUID primary key (`id`) or their
    human-readable domain identifier (`run_id`), and callers pass either one
    interchangeably (frontend links, Copilot, API clients). Checking only
    `id` meant a real run passed by its `run_id` string was never found,
    so this tried to insert a new placeholder row reusing that same string
    as both `id` and `run_id` — colliding with the real row's `run_id`
    unique constraint and crashing with an IntegrityError.
    """
    from sqlalchemy import or_, select
    from app.database.models import ReconciliationRun as ReconciliationRunORM

    run_check = await session.execute(
        select(ReconciliationRunORM).where(
            or_(ReconciliationRunORM.id == run_id, ReconciliationRunORM.run_id == run_id)
        )
    )
    if not run_check.scalars().first():
        now_dt = utcnow()
        new_run = ReconciliationRunORM(
            id=run_id,
            run_id=run_id,
            status="completed",
            started_at=now_dt,
            completed_at=now_dt,
            gateway_count=0,
            ledger_count=0,
            bank_count=0,
            match_count=0,
            exception_count=0,
            summary="System reference run for transactional integrity.",
            created_at=now_dt,
        )
        session.add(new_run)
        await session.flush()
