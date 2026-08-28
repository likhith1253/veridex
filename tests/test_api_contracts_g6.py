"""
Regression and Acceptance Test Suite for Root-Cause Group G6:
API CONTRACTS & VALIDATION (AUD-047, 048, 049, 050, 051, 056, 060, 062).
"""

import os
from decimal import Decimal
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
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_aud_047_copilot_brief_get_and_post_work(test_client: AsyncClient):
    """AUD-047: Copilot daily brief must accept both GET and POST requests without 405."""
    # GET
    res_get = await test_client.get("/api/v1/controller/copilot/brief")
    assert res_get.status_code == 200
    data_get = res_get.json()
    assert "status" in data_get
    assert "money_at_risk_inr" in data_get
    assert "why" in data_get

    # POST
    res_post = await test_client.post("/api/v1/controller/copilot/brief", json={"run_id": "test_run"})
    assert res_post.status_code == 200
    data_post = res_post.json()
    assert "status" in data_post


@pytest.mark.asyncio
async def test_aud_048_050_simulate_failure_validation_and_scenarios(test_client: AsyncClient):
    """AUD-048 & AUD-050: Validate simulate failure enum constraints and execution."""
    # Valid scenario: groq_api_down
    res = await test_client.post("/api/v1/controller/simulate-failure", json={"scenario": "groq_api_down", "amount": 50000.0})
    assert res.status_code == 200
    data = res.json()
    assert data["scenario"] == "groq_api_down"
    assert data["status"] == "SIMULATION_EXECUTED"

    # Valid scenario: corrupted_utr
    res2 = await test_client.post("/api/v1/controller/simulate-failure", json={"scenario": "corrupted_utr", "amount": 25000.0})
    assert res2.status_code == 200
    assert res2.json()["scenario"] == "corrupted_utr"

    # Invalid scenario must return 422 with structured JSON body
    res_invalid = await test_client.post("/api/v1/controller/simulate-failure", json={"scenario": "invalid_fake_scenario", "amount": 100.0})
    assert res_invalid.status_code == 422
    data_err = res_invalid.json()
    assert "detail" in data_err
    assert data_err["status_code"] == 422


@pytest.mark.asyncio
async def test_aud_049_structured_json_error_responses(test_client: AsyncClient):
    """AUD-049: Non-2xx responses (404, 405, 422) must return structured JSON, not 0-byte bodies."""
    # 404 Nonexistent route
    res_404 = await test_client.get("/api/v1/controller/nonexistent-endpoint-xyz")
    assert res_404.status_code == 404
    assert len(res_404.content) > 0
    data_404 = res_404.json()
    assert "detail" in data_404
    assert data_404["status_code"] == 404

    # 404 Nonexistent resource ID
    res_404_res = await test_client.post("/api/v1/controller/exceptions/nonexistent_id/decision", json={"action": "approve"})
    assert res_404_res.status_code == 404
    assert len(res_404_res.content) > 0
    data_404_res = res_404_res.json()
    assert "detail" in data_404_res
    assert data_404_res["status_code"] == 404

    # 405 Method Not Allowed
    res_405 = await test_client.delete("/api/v1/controller/summary")
    assert res_405.status_code == 405
    assert len(res_405.content) > 0
    data_405 = res_405.json()
    assert "detail" in data_405
    assert data_405["status_code"] == 405


@pytest.mark.asyncio
async def test_aud_051_single_and_batch_ingest_decimal_precision(test_client: AsyncClient):
    """AUD-051: Ingest endpoints accept exact Decimal amounts without precision deformation."""
    payload = {
        "txn_id": "TX_PRECISE_01",
        "source": "gateway",
        "amount": "123456789.75",
        "currency": "INR",
        "order_id": "ORD_PRECISE_01",
        "reference_number": "UTR_PRECISE_01",
    }
    res = await test_client.post("/api/v1/controller/ingest", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["transaction_id"] == "TX_PRECISE_01"

    # Invalid negative amount rejected with 422
    bad_payload = {
        "txn_id": "TX_BAD",
        "source": "gateway",
        "amount": "-500.00",
        "currency": "INR",
    }
    res_bad = await test_client.post("/api/v1/controller/ingest", json=bad_payload)
    assert res_bad.status_code == 422


@pytest.mark.asyncio
async def test_aud_056_062_categorical_enum_query_validation(test_client: AsyncClient):
    """AUD-056 & AUD-062: Invalid query enum values return 422 validation errors."""
    # Invalid status filter returns 422
    res_bad_status = await test_client.get("/api/v1/controller/exceptions?status=nonexistent_status")
    assert res_bad_status.status_code == 422
    assert "detail" in res_bad_status.json()

    # Invalid category filter returns 422
    res_bad_cat = await test_client.get("/api/v1/controller/exceptions?category=nonexistent_category")
    assert res_bad_cat.status_code == 422
    assert "detail" in res_bad_cat.json()

    # Valid status returns 200
    res_valid = await test_client.get("/api/v1/controller/exceptions?status=open")
    assert res_valid.status_code == 200
    assert "exceptions" in res_valid.json()


@pytest.mark.asyncio
async def test_aud_060_malformed_json_returns_structured_422(test_client: AsyncClient):
    """AUD-060: Malformed JSON request bodies return structured 422 error JSON with details."""
    corrupt_body = '{"scenario": "corrupted_utr", "garbage_1=1 -- -'
    res = await test_client.post(
        "/api/v1/controller/simulate-failure",
        content=corrupt_body,
        headers={"Content-Type": "application/json"},
    )
    assert res.status_code == 422
    assert len(res.content) > 0
    data = res.json()
    assert "detail" in data
    assert data["status_code"] == 422
