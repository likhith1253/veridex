"""Shared database utilities."""
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Return current UTC time as a timezone-naive datetime for asyncpg/PostgreSQL compatibility.
    
    asyncpg requires TIMESTAMP WITHOUT TIME ZONE columns to receive naive datetimes.
    All ORM inserts must use this helper instead of datetime.now(timezone.utc).
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)
