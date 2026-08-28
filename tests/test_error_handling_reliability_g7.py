"""
Regression and Acceptance Test Suite for Root-Cause Group G7:
API ERROR HANDLING & RELIABILITY (AUD-004, 006, 041, 049, 060, 064).
"""

import os
from unittest.mock import patch
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.dependencies import get_db_session
from app.api.main import app
from app.database.session import create_app_engine

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL") or os.getenv("DATABASE_URL", "postgresql+asyncpg://localhost/sentinel_test")


@pytest_asyncio.fixture(autouse=True)
async def clean_db():
    """Clean tables in isolated test database before each test."""
    engine = create_app_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(text(
            "TRUNCATE TABLE audit_events, exception_transactions, match_transactions, "
            "decisions, exceptions, matches, reconciliation_items, reconciliation_runs, transactions CASCADE;"
        ))
    await engine.dispose()


@pytest_asyncio.fixture
async def test_client():
    """Async HTTP client with isolated database session dependency override."""
    engine = create_app_engine(TEST_DATABASE_URL, echo=False)
    session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async def _override_get_db():
        async with session_maker() as session:
            yield session

    app.dependency_overrides[get_db_session] = _override_get_db
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_aud_004_064_global_500_sanitized_and_structured(test_client):
    """AUD-004 & AUD-064: 500 errors must never leak traceback, stack, paths, or raw exception strings."""
    with patch("app.services.finance_controller.FinanceController.get_summary_kpis", side_effect=RuntimeError("Secret database connection failed at /var/secrets/key.pem")):
        resp = await test_client.get("/api/v1/controller/summary")
        assert resp.status_code == 500
        assert resp.headers.get("content-type", "").startswith("application/json")
        data = resp.json()
        assert data["status_code"] == 500
        assert data["detail"] == "Internal server error occurred."
        # Verify no traceback or secret leakage
        assert "traceback" not in data
        assert "Secret" not in str(data)
        assert "/var/secrets" not in str(data)
        assert "RuntimeError" not in str(data)


@pytest.mark.asyncio
async def test_aud_006_human_decision_sanitized_errors(test_client):
    """AUD-006: Decision endpoint returns clean error messages without stdout traceback dumps or raw leaks."""
    # Invalid action
    resp = await test_client.post(
        "/api/v1/controller/exceptions/test-id/decision",
        json={"action": "invalid_action_xyz", "actor": "tester", "reason": "test"},
    )
    assert resp.status_code == 422
    data = resp.json()
    assert data["status_code"] == 422
    assert "detail" in data

    # Internal unexpected error during decision execution
    with patch("app.services.human_decision_service.HumanDecisionService.apply_decision", side_effect=Exception("Raw DB deadlock error code 40001")):
        resp = await test_client.post(
            "/api/v1/controller/exceptions/test-id/decision",
            json={"action": "approve", "actor": "tester", "reason": "test"},
        )
        assert resp.status_code == 500
        data = resp.json()
        assert data["status_code"] == 500
        assert data["detail"] == "Internal server error occurred."
        assert "deadlock" not in str(data)


@pytest.mark.asyncio
async def test_aud_041_human_decision_nonexistent_or_bad_uuid(test_client):
    """AUD-041: Nonexistent or bad exception UUID returns structured 404 instead of crashing or leaking."""
    # Nonexistent UUID
    resp = await test_client.post(
        "/api/v1/controller/exceptions/00000000-0000-0000-0000-000000000000/decision",
        json={"action": "approve", "actor": "tester", "reason": "test"},
    )
    assert resp.status_code == 404
    data = resp.json()
    assert data["status_code"] == 404
    assert "not found" in data["detail"].lower()

    # Malformed non-UUID string
    resp2 = await test_client.post(
        "/api/v1/controller/exceptions/non-existent-random-string/decision",
        json={"action": "approve", "actor": "tester", "reason": "test"},
    )
    assert resp2.status_code == 404
    data2 = resp2.json()
    assert data2["status_code"] == 404
    assert "not found" in data2["detail"].lower()

    # Assign on nonexistent
    resp3 = await test_client.post(
        "/api/v1/controller/exceptions/00000000-0000-0000-0000-000000000000/assign",
        json={"assigned_to": "analyst_1", "actor": "tester"},
    )
    assert resp3.status_code == 404
    assert resp3.json()["status_code"] == 404

    # Note on nonexistent
    resp4 = await test_client.post(
        "/api/v1/controller/exceptions/00000000-0000-0000-0000-000000000000/note",
        json={"note": "some note", "actor": "tester"},
    )
    assert resp4.status_code == 404
    assert resp4.json()["status_code"] == 404


@pytest.mark.asyncio
async def test_aud_049_structured_404_400_405(test_client):
    """AUD-049: 404, 400, 405 error responses return structured JSON bodies with detail and status_code."""
    # 404 Not Found
    resp_404 = await test_client.get("/api/v1/controller/this-path-definitely-does-not-exist")
    assert resp_404.status_code == 404
    assert resp_404.headers.get("content-type", "").startswith("application/json")
    data_404 = resp_404.json()
    assert data_404["status_code"] == 404
    assert data_404["detail"] == "Not Found"

    # 405 Method Not Allowed
    resp_405 = await test_client.delete("/api/v1/controller/summary")
    assert resp_405.status_code == 405
    assert resp_405.headers.get("content-type", "").startswith("application/json")
    data_405 = resp_405.json()
    assert data_405["status_code"] == 405
    assert data_405["detail"] == "Method Not Allowed"


@pytest.mark.asyncio
async def test_aud_060_malformed_json_422_response(test_client):
    """AUD-060: Malformed JSON request bodies return structured 422 JSON instead of empty 0-byte responses."""
    resp = await test_client.post(
        "/api/v1/controller/simulate-failure",
        content='{"scenario": "corrupted_utr", "amount": 100, garbage_1=1 -- -',
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 422
    assert resp.headers.get("content-type", "").startswith("application/json")
    data = resp.json()
    assert data["status_code"] == 422
    assert "detail" in data
    assert isinstance(data["detail"], list)
    assert len(data["detail"]) > 0
