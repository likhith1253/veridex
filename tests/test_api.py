from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.dependencies import (
    get_investigation_service,
    get_reconciliation_repository,
)
from app.api.main import app
from app.models.exception_record import ExceptionCategory
from app.models.investigation_result import (
    InvestigationConclusion,
    InvestigationMethod,
    InvestigationStatus,
)
from app.models.reconciliation_run import ReconciliationRun, RunStatus


@pytest.fixture
def mock_conclusion() -> InvestigationConclusion:
    return InvestigationConclusion(
        investigation_id="inv_test_123",
        exception_id="exc_456",
        run_id="run_789",
        method=InvestigationMethod.DETERMINISTIC,
        root_cause="Duplicate transaction detected across gateway entries",
        classification=ExceptionCategory.DUPLICATE_ENTRY,
        confidence=Decimal("0.95"),
        financial_exposure=Decimal("1500.00"),
        expected_cost=Decimal("1425.00"),
        recommended_action="flag_duplicate",
        requires_human_review=False,
        evidence={"matched_rule": "duplicate_entry"},
        llm_invoked=False,
        llm_error=None,
        historical_cases_used=0,
        status=InvestigationStatus.COMPLETED,
        created_at=datetime(2026, 8, 24, 12, 0, 0, tzinfo=timezone.utc),
    )


@pytest.fixture
def mock_run_domain() -> ReconciliationRun:
    return ReconciliationRun(
        run_id="run_test_001",
        status=RunStatus.COMPLETED,
        started_at=datetime(2026, 8, 24, 12, 0, 0, tzinfo=timezone.utc),
        ended_at=datetime(2026, 8, 24, 12, 0, 5, tzinfo=timezone.utc),
        gateway_count=100,
        ledger_count=100,
        bank_count=100,
        match_count=98,
        exception_count=2,
        summary="Reconciliation completed successfully with 2 exceptions.",
        created_at=datetime(2026, 8, 24, 12, 0, 0, tzinfo=timezone.utc),
    )


@pytest.mark.asyncio
async def test_health_endpoint():
    """Verify GET /health returns 200 and {'status': 'ok'}."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_get_investigation_by_exception_found(mock_conclusion):
    """Verify GET /investigations/{exception_id} returns 200 and expected investigation."""
    mock_service = MagicMock()
    mock_service.get_by_exception = AsyncMock(return_value=[mock_conclusion])

    app.dependency_overrides[get_investigation_service] = lambda: mock_service
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/investigations/exc_456")
            assert response.status_code == 200
            data = response.json()
            assert data["investigation_id"] == "inv_test_123"
            assert data["exception_id"] == "exc_456"
            assert data["run_id"] == "run_789"
            assert data["classification"] == "duplicate_entry"
            assert data["method"] == "deterministic"
            assert data["confidence"] == "0.95"
            assert data["financial_exposure"] == "1500.00"
            assert data["expected_cost"] == "1425.00"
            assert data["recommended_action"] == "flag_duplicate"
            assert data["requires_human_review"] is False
            assert data["llm_invoked"] is False

            mock_service.get_by_exception.assert_awaited_once_with("exc_456")
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_investigation_by_exception_not_found():
    """Verify GET /investigations/{exception_id} returns 404 when absent."""
    mock_service = MagicMock()
    mock_service.get_by_exception = AsyncMock(return_value=[])

    app.dependency_overrides[get_investigation_service] = lambda: mock_service
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/investigations/non_existent_exc")
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
            mock_service.get_by_exception.assert_awaited_once_with("non_existent_exc")
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_investigation_is_read_only_and_does_not_invoke_graph_or_llm(mock_conclusion):
    """Verify GET /investigations/{exception_id} does NOT invoke investigate() or graph runner."""
    mock_service = MagicMock()
    mock_service.get_by_exception = AsyncMock(return_value=[mock_conclusion])
    mock_service.investigate = AsyncMock()

    app.dependency_overrides[get_investigation_service] = lambda: mock_service
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/investigations/exc_456")
            assert response.status_code == 200
            mock_service.investigate.assert_not_called()
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_run_summary_found(mock_run_domain):
    """Verify GET /runs/{run_id}/summary returns 200 and expected summary."""
    mock_repo = MagicMock()
    mock_repo.get_run_by_run_id = AsyncMock(return_value=mock_run_domain)

    app.dependency_overrides[get_reconciliation_repository] = lambda: mock_repo
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/runs/run_test_001/summary")
            assert response.status_code == 200
            data = response.json()
            assert data["run_id"] == "run_test_001"
            assert data["status"] == "completed"
            assert data["total_transactions"] == 300
            assert data["gateway_count"] == 100
            assert data["ledger_count"] == 100
            assert data["bank_count"] == 100
            assert data["match_count"] == 98
            assert data["exception_count"] == 2
            assert data["summary"] == "Reconciliation completed successfully with 2 exceptions."

            mock_repo.get_run_by_run_id.assert_awaited_once_with("run_test_001")
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_run_summary_not_found():
    """Verify GET /runs/{run_id}/summary returns 404 when absent."""
    mock_repo = MagicMock()
    mock_repo.get_run_by_run_id = AsyncMock(return_value=None)
    mock_repo.get_run_by_id = AsyncMock(return_value=None)

    app.dependency_overrides[get_reconciliation_repository] = lambda: mock_repo
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/runs/unknown_run/summary")
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
            mock_repo.get_run_by_run_id.assert_awaited_once_with("unknown_run")
            mock_repo.get_run_by_id.assert_awaited_once_with("unknown_run")
    finally:
        app.dependency_overrides.clear()
