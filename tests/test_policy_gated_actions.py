import os
from decimal import Decimal
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.dependencies import get_db_session
from app.api.main import app
from app.database.models import (
    AuditEvent as AuditEventORM,
    Exception as ExceptionORM,
    ExceptionCategory,
    FinanceAction as FinanceActionORM,
    ReconciliationRun as ReconciliationRunORM,
)
from app.database.models.finance_action import ActionLifecycleState, FinanceActionType
from app.database.session import DATABASE_URL, create_app_engine
from app.database.utils import utcnow


@pytest.fixture
def auth_headers():
    api_key = (os.environ.get("SENTINEL_API_KEY") or os.environ.get("API_KEY") or "").strip()
    return {"X-API-Key": api_key} if api_key else {}


@pytest_asyncio.fixture
async def test_ctx():
    """Isolated client and session fixture per test with engine disposal."""
    engine = create_app_engine(DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_factory() as session:
        # Ensure a valid run_id exists
        run_stmt = select(ReconciliationRunORM).limit(1)
        run_obj = (await session.execute(run_stmt)).scalar_one_or_none()
        if not run_obj:
            now = utcnow()
            run_obj = ReconciliationRunORM(
                id="run_actions_test_001",
                run_id="run_actions_test_001",
                status="completed",
                started_at=now,
                completed_at=now,
                gateway_count=10,
                ledger_count=10,
                bank_count=10,
                match_count=5,
                exception_count=5,
                created_at=now,
            )
            session.add(run_obj)
            await session.commit()

        async def _override_db():
            yield session

        app.dependency_overrides[get_db_session] = _override_db
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client, session
        app.dependency_overrides.pop(get_db_session, None)

    await engine.dispose()


@pytest.mark.asyncio
async def test_action_full_lifecycle_approve_and_execute(test_ctx, auth_headers):
    """Test full safe action lifecycle: DETECTED -> RECOMMENDED -> PENDING_APPROVAL -> APPROVED -> EXECUTED."""
    client, session = test_ctx
    now = utcnow()

    # 1. Seed an open exception to target
    run_stmt = select(ReconciliationRunORM.id).limit(1)
    run_id = (await session.execute(run_stmt)).scalars().first()

    exc = ExceptionORM(
        id=f"exc_act_{now.timestamp()}",
        run_id=run_id,
        exception_category=ExceptionCategory.AMOUNT_MISMATCH,
        status="open",
        confidence=Decimal("0.95"),
        financial_exposure=Decimal("150.00"),
        expected_cost=Decimal("15.00"),
        explanation="Rounding fee discrepancy on gateway batch",
        resolved=False,
        created_at=now,
    )
    session.add(exc)
    await session.commit()

    # 2. Recommendation by AI / System
    rec_payload = {
        "entity_type": "exception",
        "entity_id": exc.id,
        "action_type": "POST_ADJUSTMENT",
        "amount": "150.00",
        "currency": "INR",
        "recommended_by": "ai_investigation_copilot",
        "recommendation_reason": "Variance of INR 150 is verified fee delta; recommend posting ledger adjustment",
        "evidence": {"variance": "150.00", "fee_type": "gateway_mdr"},
        "run_id": run_id,
    }
    rec_res = await client.post("/api/v1/actions/recommend", json=rec_payload, headers=auth_headers)
    assert rec_res.status_code == 201, rec_res.text
    action_data = rec_res.json()
    action_id = action_data["id"]

    assert action_data["state"] == ActionLifecycleState.PENDING_APPROVAL.value
    assert Decimal(action_data["amount"]) == Decimal("150.00")
    assert action_data["recommended_by"] == "ai_investigation_copilot"

    # 3. Verify audit record for recommendation
    stmt_audit = select(AuditEventORM).where(AuditEventORM.stage == "FINANCE_ACTION")
    audit_events = (await session.execute(stmt_audit)).scalars().all()
    assert any(a.event_type == "ACTION_RECOMMENDED" and action_id in str(a.meta_data) for a in audit_events)

    # 4. Attempt to execute without approval (must be rejected by policy)
    exec_early = await client.post(
        f"/api/v1/actions/{action_id}/execute",
        json={"actor": "finance_operator_01"},
        headers=auth_headers,
    )
    assert exec_early.status_code == 403, "Unapproved action execution must be blocked"
    assert "must be in approved state" in exec_early.json()["detail"].lower()

    # 5. Attempt AI approval (must be blocked; AI cannot approve)
    ai_approve = await client.post(
        f"/api/v1/actions/{action_id}/approve",
        json={"actor": "ai_agent", "reason": "Automated approval attempt"},
        headers=auth_headers,
    )
    assert ai_approve.status_code == 403
    assert "ai cannot independently approve" in ai_approve.json()["detail"].lower()

    # 6. Explicit Human Approval
    human_approve = await client.post(
        f"/api/v1/actions/{action_id}/approve",
        json={"actor": "senior_controller_raj", "reason": "Verified against fee schedule agreement"},
        headers=auth_headers,
    )
    assert human_approve.status_code == 200
    approved_data = human_approve.json()
    assert approved_data["state"] == ActionLifecycleState.APPROVED.value
    assert approved_data["approved_by"] == "senior_controller_raj"

    # 7. Attempt AI execution (must be blocked)
    ai_exec = await client.post(
        f"/api/v1/actions/{action_id}/execute",
        json={"actor": "ai"},
        headers=auth_headers,
    )
    assert ai_exec.status_code == 403
    assert "ai cannot independently execute" in ai_exec.json()["detail"].lower()

    # 8. Successful Bounded Human Execution
    human_exec = await client.post(
        f"/api/v1/actions/{action_id}/execute",
        json={"actor": "finance_operator_priya"},
        headers=auth_headers,
    )
    assert human_exec.status_code == 200
    exec_data = human_exec.json()
    assert exec_data["state"] == ActionLifecycleState.EXECUTED.value
    assert exec_data["execution_result"] is not None
    assert "posted_adjustment_amount" in exec_data["execution_result"]

    # 9. Verify Action Status and History Endpoint
    get_res = await client.get(f"/api/v1/actions/{action_id}", headers=auth_headers)
    assert get_res.status_code == 200
    assert get_res.json()["state"] == ActionLifecycleState.EXECUTED.value

    list_res = await client.get("/api/v1/actions?state=EXECUTED", headers=auth_headers)
    assert list_res.status_code == 200
    assert any(a["id"] == action_id for a in list_res.json())


@pytest.mark.asyncio
async def test_action_rejection_flow(test_ctx, auth_headers):
    """Test explicit human rejection flow: PENDING_APPROVAL -> REJECTED."""
    client, session = test_ctx
    run_stmt = select(ReconciliationRunORM.id).limit(1)
    run_id = (await session.execute(run_stmt)).scalars().first()

    rec_payload = {
        "entity_type": "settlement",
        "entity_id": "setl_reject_test_001",
        "action_type": "WRITE_OFF",
        "amount": "85.00",
        "currency": "INR",
        "recommended_by": "ai_agent",
        "recommendation_reason": "Write off fee discrepancy",
        "run_id": run_id,
    }
    rec_res = await client.post("/api/v1/actions/recommend", json=rec_payload, headers=auth_headers)
    assert rec_res.status_code == 201
    action_id = rec_res.json()["id"]

    # Human Rejection
    reject_res = await client.post(
        f"/api/v1/actions/{action_id}/reject",
        json={"actor": "controller_arun", "reason": "Requires formal merchant dispute, do not write off"},
        headers=auth_headers,
    )
    assert reject_res.status_code == 200
    data = reject_res.json()
    assert data["state"] == ActionLifecycleState.REJECTED.value
    assert data["rejected_by"] == "controller_arun"

    # Attempting to execute a rejected action must fail
    exec_rejected = await client.post(
        f"/api/v1/actions/{action_id}/execute",
        json={"actor": "operator_dev"},
        headers=auth_headers,
    )
    assert exec_rejected.status_code == 403


@pytest.mark.asyncio
async def test_action_bounds_policy_enforcement(test_ctx, auth_headers):
    """Test that actions exceeding monetary boundaries are blocked before creation."""
    client, session = test_ctx
    run_stmt = select(ReconciliationRunORM.id).limit(1)
    run_id = (await session.execute(run_stmt)).scalars().first()

    # Attempt unbounded adjustment (limit is INR 5,000)
    unbounded_payload = {
        "entity_type": "exception",
        "entity_id": "exc_unbounded_001",
        "action_type": "POST_ADJUSTMENT",
        "amount": "50000.00",  # Exceeds INR 5,000
        "currency": "INR",
        "recommended_by": "operator",
        "recommendation_reason": "Attempting huge manual adjustment",
        "run_id": run_id,
    }
    res = await client.post("/api/v1/actions/recommend", json=unbounded_payload, headers=auth_headers)
    assert res.status_code == 400
    assert "exceeds policy bound limit" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_action_recommendation_idempotent(test_ctx, auth_headers):
    """Test that recommending an action for an entity multiple times is idempotent."""
    client, session = test_ctx
    run_stmt = select(ReconciliationRunORM.id).limit(1)
    run_id = (await session.execute(run_stmt)).scalars().first()

    payload = {
        "entity_type": "exception",
        "entity_id": "exc_idem_test_001",
        "action_type": "POST_ADJUSTMENT",
        "amount": "250.00",
        "currency": "INR",
        "recommended_by": "ai_agent",
        "recommendation_reason": "First recommendation",
        "run_id": run_id,
    }
    res1 = await client.post("/api/v1/actions/recommend", json=payload, headers=auth_headers)
    assert res1.status_code == 201
    act_id1 = res1.json()["id"]

    # Re-recommend same entity
    payload["recommendation_reason"] = "Updated recommendation reason"
    payload["amount"] = "260.00"
    res2 = await client.post("/api/v1/actions/recommend", json=payload, headers=auth_headers)
    assert res2.status_code == 201
    act_id2 = res2.json()["id"]

    # Same action ID returned, not duplicated
    assert act_id1 == act_id2
    assert res2.json()["amount"] == "260.00"


@pytest.mark.asyncio
async def test_action_execution_resolves_exception(test_ctx, auth_headers):
    """Test that executing a POST_ADJUSTMENT action on an exception resolves the exception."""
    client, session = test_ctx
    now = utcnow()
    run_stmt = select(ReconciliationRunORM.id).limit(1)
    run_id = (await session.execute(run_stmt)).scalars().first()

    exc = ExceptionORM(
        id=f"exc_exec_resolve_{now.timestamp()}",
        run_id=run_id,
        exception_category=ExceptionCategory.AMOUNT_MISMATCH,
        status="open",
        confidence=Decimal("0.90"),
        financial_exposure=Decimal("200.00"),
        expected_cost=Decimal("20.00"),
        explanation="Fee mismatch requiring adjustment",
        resolved=False,
        created_at=now,
    )
    session.add(exc)
    await session.commit()

    # Recommend, approve, execute
    rec_res = await client.post(
        "/api/v1/actions/recommend",
        json={
            "entity_type": "exception",
            "entity_id": exc.id,
            "action_type": "POST_ADJUSTMENT",
            "amount": "200.00",
            "currency": "INR",
            "recommended_by": "ai_agent",
            "recommendation_reason": "Post adjustment",
            "run_id": run_id,
        },
        headers=auth_headers,
    )
    act_id = rec_res.json()["id"]

    await client.post(
        f"/api/v1/actions/{act_id}/approve",
        json={"actor": "Controller_Alice", "reason": "Approved adjustment"},
        headers=auth_headers,
    )

    exec_res = await client.post(
        f"/api/v1/actions/{act_id}/execute",
        json={"actor": "Controller_Alice"},
        headers=auth_headers,
    )
    assert exec_res.status_code == 200

    # Verify exception is now resolved in database
    await session.refresh(exc)
    assert exc.resolved is True
    assert exc.status == "resolved"

