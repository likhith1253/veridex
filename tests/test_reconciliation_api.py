import inspect
import os
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.dependencies import (
    get_db_session,
    get_investigation_service,
    get_reconciliation_service,
)
from app.api.main import app
from app.database.repositories import (
    AuditRepository,
    DecisionRepository,
    ExceptionRepository,
    InvestigationRepository,
    MatchRepository,
    ReconciliationRepository,
    TransactionRepository,
)
from app.graph.investigation_graph import InvestigationGraphRunner
from app.investigation.llm_client import FakeLLMClient
from app.investigation.service import InvestigationService
from app.models.reconciliation_summary import ReconciliationSummary
from app.models.transaction import Transaction, TransactionSource, TransactionStatus
from app.services.reconciliation import ReconciliationService


def _sample_gateway_payload() -> dict:
    return {
        "txn_id": "GW_001",
        "source": "gateway",
        "reference_number": "UTR_1001",
        "amount": "1000.00",
        "currency": "INR",
        "timestamp": "2026-08-24T10:00:00Z",
        "narration": "Payment for ORD_1001",
        "fee": "20.00",
        "tax": "3.60",
        "status": "completed",
        "order_id": "ORD_1001",
        "metadata": {"terminal": "T1"},
    }


def _sample_ledger_payload() -> dict:
    return {
        "txn_id": "LD_001",
        "source": "ledger",
        "reference_number": "UTR_1001",
        "amount": "1000.00",
        "currency": "INR",
        "timestamp": "2026-08-24T10:00:00Z",
        "narration": "Order ORD_1001",
        "fee": None,
        "tax": None,
        "status": "completed",
        "order_id": None,
        "metadata": {"customer_id": "CUST_1"},
    }


def _sample_bank_payload() -> dict:
    return {
        "txn_id": "BK_001",
        "source": "bank",
        "reference_number": "UTR_1001",
        "amount": "1000.00",
        "currency": "INR",
        "timestamp": "2026-08-24T10:00:00Z",
        "narration": "NEFT Cr UTR_1001",
        "fee": None,
        "tax": None,
        "status": "completed",
        "order_id": None,
        "metadata": {},
    }


def _sample_summary(run_id: str = "run_test_api_001") -> ReconciliationSummary:
    return ReconciliationSummary(
        run_id=run_id,
        total_transactions=3,
        deterministic_matches=1,
        ml_proposals=0,
        manual_reviews=0,
        ambiguous=0,
        unresolved=0,
        rejected=0,
        exceptions_created=0,
        completed_successfully=True,
        started_at=datetime(2026, 8, 24, 10, 0, 0, tzinfo=timezone.utc),
        completed_at=datetime(2026, 8, 24, 10, 0, 1, tzinfo=timezone.utc),
    )


# -------------------------------------------------------------------------
# Unit Tests (Mocked Service)
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_reconciliation_runs_success():
    """Verify POST /reconciliation/runs calls service with valid input and returns 200."""
    mock_service = MagicMock()
    mock_service.run_reconciliation = AsyncMock(return_value=_sample_summary("custom_run_123"))

    app.dependency_overrides[get_reconciliation_service] = lambda: mock_service
    try:
        payload = {
            "run_id": "custom_run_123",
            "gateway": [_sample_gateway_payload()],
            "ledger": [_sample_ledger_payload()],
            "bank": [_sample_bank_payload()],
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/reconciliation/runs", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["run_id"] == "custom_run_123"
            assert data["total_transactions"] == 3
            assert data["deterministic_matches"] == 1
            assert data["completed_successfully"] is True

            # Verify service was invoked with correct parameters
            mock_service.run_reconciliation.assert_awaited_once()
            call_kwargs = mock_service.run_reconciliation.call_args.kwargs
            assert call_kwargs["run_id"] == "custom_run_123"
            txns_by_source = call_kwargs["transactions_by_source"]
            assert len(txns_by_source[TransactionSource.GATEWAY]) == 1
            assert len(txns_by_source[TransactionSource.LEDGER]) == 1
            assert len(txns_by_source[TransactionSource.BANK]) == 1
            assert txns_by_source[TransactionSource.GATEWAY][0].txn_id == "GW_001"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_reconciliation_runs_generates_run_id_when_omitted():
    """Verify run_id is generated when not provided in request."""
    mock_service = MagicMock()
    mock_service.run_reconciliation = AsyncMock(
        side_effect=lambda transactions_by_source, run_id: _sample_summary(run_id)
    )

    app.dependency_overrides[get_reconciliation_service] = lambda: mock_service
    try:
        payload = {
            "gateway": [_sample_gateway_payload()],
            "ledger": [],
            "bank": [],
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/reconciliation/runs", json=payload)
            assert response.status_code == 200
            data = response.json()
            assert data["run_id"].startswith("run_")
            assert data["completed_successfully"] is True
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_post_reconciliation_runs_invalid_payload_422():
    """Verify invalid payloads (e.g. invalid status or non-positive amount) return 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Invalid status
        bad_payload = {
            "gateway": [
                {
                    "txn_id": "GW_BAD",
                    "source": "gateway",
                    "amount": "100.00",
                    "currency": "INR",
                    "timestamp": "2026-08-24T10:00:00Z",
                    "status": "NON_EXISTENT_STATUS",
                }
            ]
        }
        response = await client.post("/reconciliation/runs", json=bad_payload)
        assert response.status_code == 422

        # Invalid amount (amount must be > 0)
        bad_amount_payload = {
            "gateway": [
                {
                    "txn_id": "GW_BAD_AMT",
                    "source": "gateway",
                    "amount": "-50.00",
                    "currency": "INR",
                    "timestamp": "2026-08-24T10:00:00Z",
                    "status": "completed",
                }
            ]
        }
        response2 = await client.post("/reconciliation/runs", json=bad_amount_payload)
        assert response2.status_code == 422


@pytest.mark.asyncio
async def test_post_reconciliation_runs_service_failure_returns_500():
    """Verify service exceptions result in HTTP 500 without crashing the app."""
    mock_service = MagicMock()
    mock_service.run_reconciliation = AsyncMock(side_effect=RuntimeError("Database deadlock simulated"))

    app.dependency_overrides[get_reconciliation_service] = lambda: mock_service
    try:
        payload = {
            "run_id": "failed_run_001",
            "gateway": [_sample_gateway_payload()],
        }

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/reconciliation/runs", json=payload)
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
            assert "Database deadlock simulated" in data["detail"]
    finally:
        app.dependency_overrides.clear()


def test_api_route_does_not_duplicate_business_logic():
    """Verify the API route delegates all reconciliation logic to the service."""
    import app.api.routes.reconciliation as route_module

    source = inspect.getsource(route_module)
    assert "DeterministicMatcher" not in source
    assert "DecisionPolicy" not in source
    assert "CandidateGenerator" not in source
    assert "MLScorer" not in source
    assert "InvestigationGraphRunner" not in source


def test_endpoint_uses_dependency_injection():
    """Verify trigger_reconciliation_run uses FastAPI Depends."""
    from app.api.routes.reconciliation import trigger_reconciliation_run

    sig = inspect.signature(trigger_reconciliation_run)
    assert "service" in sig.parameters
    default = sig.parameters["service"].default
    assert hasattr(default, "dependency")
    assert default.dependency == get_reconciliation_service


# -------------------------------------------------------------------------
# Integration Test (Real PostgreSQL + FakeLLM)
# -------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_post_reconciliation_runs_end_to_end_with_database():
    """End-to-end integration test with real database session and FakeLLMClient."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        pytest.skip("PostgreSQL DATABASE_URL not set")

    from app.database.session import create_app_engine
    engine = create_app_engine(database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # Clean DB before test
    async with engine.begin() as conn:
        await conn.execute(text(
            "TRUNCATE TABLE audit_events, exception_transactions, match_transactions, "
            "decisions, exceptions, matches, reconciliation_items, reconciliation_runs, transactions CASCADE;"
        ))

    async with session_factory() as session:
        # Build real service with FakeLLM investigation runner
        investigation_repo = InvestigationRepository(session)
        audit_repo = AuditRepository(session)
        graph_runner = InvestigationGraphRunner(llm_client=FakeLLMClient())
        investigation_service = InvestigationService(
            session=session,
            investigation_repo=investigation_repo,
            audit_repo=audit_repo,
            graph_runner=graph_runner,
        )

        real_service = ReconciliationService(
            session=session,
            transaction_repo=TransactionRepository(session),
            reconciliation_repo=ReconciliationRepository(session),
            match_repo=MatchRepository(session),
            decision_repo=DecisionRepository(session),
            exception_repo=ExceptionRepository(session),
            audit_repo=audit_repo,
            investigation_service=investigation_service,
        )

        app.dependency_overrides[get_reconciliation_service] = lambda: real_service
        try:
            payload = {
                "run_id": "e2e_api_run_001",
                "gateway": [_sample_gateway_payload()],
                "ledger": [_sample_ledger_payload()],
                "bank": [_sample_bank_payload()],
            }

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                response = await client.post("/reconciliation/runs", json=payload)
                assert response.status_code == 200
                data = response.json()
                assert data["run_id"] == "e2e_api_run_001"
                assert data["total_transactions"] == 3
                assert data["deterministic_matches"] == 1
                assert data["completed_successfully"] is True

            # Verify persisted run can be read back via GET /runs/e2e_api_run_001/summary
            app.dependency_overrides[get_db_session] = lambda: session
            from app.api.dependencies import get_reconciliation_repository
            app.dependency_overrides[get_reconciliation_repository] = lambda: ReconciliationRepository(session)

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                summary_resp = await client.get("/runs/e2e_api_run_001/summary")
                assert summary_resp.status_code == 200
                summary_data = summary_resp.json()
                assert summary_data["run_id"] == "e2e_api_run_001"
                assert summary_data["total_transactions"] == 3
                assert summary_data["match_count"] == 1

        finally:
            app.dependency_overrides.clear()
            await engine.dispose()
