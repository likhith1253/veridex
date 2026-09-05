"""Shared database utilities."""
from datetime import datetime, timezone
from typing import Optional


def utcnow() -> datetime:
    """Return current UTC time as a timezone-naive datetime for asyncpg/PostgreSQL compatibility.
    
    asyncpg requires TIMESTAMP WITHOUT TIME ZONE columns to receive naive datetimes.
    All ORM inserts must use this helper instead of datetime.now(timezone.utc).
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def ensure_run_exists(session, run_id: str) -> str:
    """Ensure a ReconciliationRun record exists for foreign key references,
    and return the row's real primary key (`id`) — the value every FK that
    references `reconciliation_runs.id` actually needs.

    Real runs are addressable by either their UUID primary key (`id`) or
    their separate human-readable domain identifier (`run_id`), and callers
    pass either one interchangeably (frontend links, Copilot, API clients).
    Those are two different columns: an existing run's `id` is NOT the same
    string as its `run_id`. So this must look up by both, and — critically —
    return the matched row's actual `id`, not just echo back whatever string
    the caller passed in. Returning the caller's raw string here would let a
    real run's human-readable run_id silently masquerade as an id, which
    then fails the FK constraint on whatever table inserts next (or, before
    this function checked both columns, could crash trying to insert a
    duplicate placeholder row).
    """
    from sqlalchemy import or_, select
    from app.database.models import ReconciliationRun as ReconciliationRunORM

    run_check = await session.execute(
        select(ReconciliationRunORM).where(
            or_(ReconciliationRunORM.id == run_id, ReconciliationRunORM.run_id == run_id)
        )
    )
    existing = run_check.scalars().first()
    if existing:
        return existing.id

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
    return run_id
