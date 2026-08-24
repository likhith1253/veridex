import os
from contextlib import asynccontextmanager
from typing import Any, Dict, Tuple

from dotenv import load_dotenv
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

load_dotenv()

from app.database.models import Base


DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost/sentinel")


def get_engine_args(url_str: str) -> Tuple[URL, Dict[str, Any]]:
    """Parse and adapt database URL for asyncpg / SQLAlchemy compatibility.

    Translates libpq-style query parameters (like `sslmode=require`, `channel_binding=...`)
    into asyncpg-compatible connect_args, ensuring SSL works with cloud providers like Neon
    while preserving compatibility with local PostgreSQL.
    """
    url = make_url(url_str)

    # Ensure asyncpg driver for postgres URLs
    drivername = url.drivername
    if drivername in ("postgresql", "postgres"):
        drivername = "postgresql+asyncpg"

    query = dict(url.query)
    connect_args: Dict[str, Any] = {}

    # Handle sslmode parameter for asyncpg
    sslmode = query.pop("sslmode", None)
    if sslmode:
        if sslmode.lower() in ("require", "verify-ca", "verify-full"):
            connect_args["ssl"] = "require"
        elif sslmode.lower() == "prefer":
            connect_args["ssl"] = "prefer"
        elif sslmode.lower() == "disable":
            connect_args["ssl"] = False

    # Remove unsupported libpq query parameters that asyncpg rejects as kwargs
    query.pop("channel_binding", None)

    # Handle ssl parameter if provided
    if "ssl" in query:
        ssl_val = query.pop("ssl")
        if isinstance(ssl_val, str):
            if ssl_val.lower() in ("true", "1", "require"):
                connect_args["ssl"] = "require"
            elif ssl_val.lower() in ("false", "0", "disable"):
                connect_args["ssl"] = False
            else:
                connect_args["ssl"] = ssl_val
        else:
            connect_args["ssl"] = ssl_val

    clean_url = url.set(drivername=drivername, query=query)
    return clean_url, connect_args


def create_app_engine(url_str: str = DATABASE_URL, echo: bool = False) -> AsyncEngine:
    """Create an AsyncEngine with sanitized connection parameters."""
    clean_url, connect_args = get_engine_args(url_str)
    return create_async_engine(clean_url, connect_args=connect_args, echo=echo)


engine = create_app_engine(DATABASE_URL, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db_session() -> AsyncSession:
    """Get a database session."""
    async with async_session_maker() as session:
        yield session


@asynccontextmanager
async def get_db_session_context():
    """Context manager for database sessions."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database schema (for development/testing only)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db():
    """Close database connections."""
    await engine.dispose()
