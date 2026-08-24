import pytest
from app.database.session import get_engine_args


def test_neon_url_sanitization():
    """Test that Neon style database URLs are converted to asyncpg format with ssl in connect_args."""
    neon_url = "postgresql://neondb_owner:npg_secret123@ep-summer-pond-123.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
    clean_url, connect_args = get_engine_args(neon_url)

    assert clean_url.drivername == "postgresql+asyncpg"
    assert "sslmode" not in clean_url.query
    assert "channel_binding" not in clean_url.query
    assert connect_args.get("ssl") == "require"
    assert clean_url.database == "neondb"
    assert clean_url.host == "ep-summer-pond-123.us-east-2.aws.neon.tech"


def test_local_url_sanitization():
    """Test that standard local PostgreSQL URLs work without forcing SSL."""
    local_url = "postgresql+asyncpg://postgres:postgres@localhost:5432/sentinel"
    clean_url, connect_args = get_engine_args(local_url)

    assert clean_url.drivername == "postgresql+asyncpg"
    assert clean_url.host == "localhost"
    assert clean_url.port == 5432
    assert "ssl" not in connect_args


def test_sslmode_disable():
    """Test that sslmode=disable explicitly sets ssl=False."""
    url = "postgresql://user:pass@localhost:5432/db?sslmode=disable"
    clean_url, connect_args = get_engine_args(url)

    assert clean_url.drivername == "postgresql+asyncpg"
    assert "sslmode" not in clean_url.query
    assert connect_args.get("ssl") is False


def test_postgres_scheme_normalization():
    """Test postgres:// scheme normalization to postgresql+asyncpg."""
    url = "postgres://user:pass@localhost:5432/db"
    clean_url, connect_args = get_engine_args(url)

    assert clean_url.drivername == "postgresql+asyncpg"
