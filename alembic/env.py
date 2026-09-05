import asyncio
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection

load_dotenv()

from app.database.models import Base
from app.database.session import DATABASE_URL, create_app_engine

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Convert postgresql+asyncpg:// or postgresql:// to standard postgresql:// for Alembic migrations
    sync_url = DATABASE_URL
    if sync_url.startswith("postgresql+asyncpg://"):
        sync_url = sync_url.replace("postgresql+asyncpg://", "postgresql://", 1)
    
    # Strip parameters not supported by sync psycopg2 if present
    from sqlalchemy.engine import make_url
    url_obj = make_url(sync_url)
    query = dict(url_obj.query)
    query.pop("channel_binding", None)
    clean_sync_url = url_obj.set(query=query)

    from sqlalchemy import create_engine
    connectable = create_engine(clean_sync_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

