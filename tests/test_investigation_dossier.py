import os
import pytest
import pytest_asyncio
from decimal import Decimal
from datetime import datetime, timezone
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.dependencies import get_db_session
from app.api.main import app
from app.database.session import DATABASE_URL, create_app_engine
from app.database.models import (
    Exception as ExceptionORM,
    ExceptionCategory,
    ExceptionTransaction as ExceptionTransactionORM,
    Match as MatchORM,
    MatchTransaction as MatchTransactionORM,
    ReconciliationRun as ReconciliationRunORM,
    Transaction as TransactionORM,
    TransactionSource,
    TransactionStatus,
)


@pytest.fixture
def auth_headers():
    api_key = (os.environ.get("SENTINEL_API_KEY") or os.environ.get("API_KEY") or "").strip()
    return {"X-API-Key": api_key} if api_key else {}


async def _ensure_seed_records(session: AsyncSession):
    """Ensure baseline test records exist even if earlier test suites truncated tables."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # 1. Run record
    run_stmt = select(ReconciliationRunORM).limit(1)
    run_obj = (await session.execute(run_stmt)).scalar_one_or_none()
    if not run_obj:
        run_obj = ReconciliationRunORM(
            id="run_qa_batch_001",
            run_id="run_qa_batch_001",
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
        await session.flush()

    # 2. Reconciled settlement & bank match
    setl_stmt = select(TransactionORM).where(TransactionORM.domain_transaction_id == "setl_live_qa_001")
    setl_tx = (await session.execute(setl_stmt)).scalar_one_or_none()
    if not setl_tx:
        setl_tx = TransactionORM(
            id="tx_setl_qa_001",
            domain_transaction_id="setl_live_qa_001",
            source=TransactionSource.GATEWAY,
            reference_number="UTR_QA_9999",
            order_id=None,
            amount=Decimal("50000.0000"),
            currency="INR",
            timestamp=now,
            fee=Decimal("1000.0000"),
            tax=Decimal("180.0000"),
            status=TransactionStatus.PROCESSED,
            meta_data={"type": "settlement", "gateway": "razorpay"},
            created_at=now,
        )
        bank_tx = TransactionORM(
            id="tx_bank_qa_001",
            domain_transaction_id="bk_setl_qa_001",
            source=TransactionSource.BANK,
            reference_number="UTR_QA_9999",
            order_id=None,
            amount=Decimal("48820.0000"),
            currency="INR",
            timestamp=now,
            fee=None,
            tax=None,
            status=TransactionStatus.PROCESSED,
            meta_data={"type": "credit"},
            created_at=now,
        )
        session.add(setl_tx)
        session.add(bank_tx)
        await session.flush()

    # 3. Open exception with linked transactions
    exc_stmt = select(ExceptionORM).where(ExceptionORM.resolved == False).limit(1)
    exc_obj = (await session.execute(exc_stmt)).scalar_one_or_none()
    if not exc_obj:
        t_gw = TransactionORM(
            id="tx_exc_seed_gw",
            domain_transaction_id="GW_EXC_001",
            source=TransactionSource.GATEWAY,
            reference_number="REF_EXC_001",
            order_id="ORD_EXC_001",
            amount=Decimal("25000.0000"),
            currency="INR",
            timestamp=now,
            fee=Decimal("500.00"),
            tax=Decimal("90.00"),
            status=TransactionStatus.PROCESSED,
            meta_data={},
            created_at=now,
        )
        t_ld = TransactionORM(
            id="tx_exc_seed_ld",
            domain_transaction_id="LD_EXC_001",
            source=TransactionSource.LEDGER,
            reference_number="REF_EXC_001",
            order_id="ORD_EXC_001",
            amount=Decimal("25000.0000"),
            currency="INR",
            timestamp=now,
            fee=None,
            tax=None,
            status=TransactionStatus.PROCESSED,
            meta_data={},
            created_at=now,
        )
        exc_obj = ExceptionORM(
            id="exc_seed_live_001",
            run_id=run_obj.id,
            exception_category=ExceptionCategory.TIMING_MISMATCH,
            status="open",
            confidence=Decimal("0.90"),
            financial_exposure=Decimal("25000.00"),
            expected_cost=Decimal("1250.00"),
            explanation="Settlement timing mismatch between gateway and ledger",
            recommended_action="Monitor for bank settlement clearing",
            resolved=False,
            created_at=now,
        )
        et1 = ExceptionTransactionORM(exception_id=exc_obj.id, transaction_id=t_gw.id)
        et2 = ExceptionTransactionORM(exception_id=exc_obj.id, transaction_id=t_ld.id)
        session.add(t_gw)
        session.add(t_ld)
        session.add(exc_obj)
        session.add(et1)
        session.add(et2)
        await session.flush()

    # 4. Matched record
    match_stmt = select(MatchORM).limit(1)
    match_obj = (await session.execute(match_stmt)).scalars().first()
    if not match_obj:
        t_m1 = TransactionORM(
            id="tx_match_seed_1",
            domain_transaction_id="TXN_M_001",
            source=TransactionSource.GATEWAY,
            reference_number="REF_M_001",
            order_id="ORD_M_001",
            amount=Decimal("12000.0000"),
            currency="INR",
            timestamp=now,
            status=TransactionStatus.PROCESSED,
            created_at=now,
        )
        t_m2 = TransactionORM(
            id="tx_match_seed_2",
            domain_transaction_id="TXN_M_002",
            source=TransactionSource.LEDGER,
            reference_number="REF_M_001",
            order_id="ORD_M_001",
            amount=Decimal("12000.0000"),
            currency="INR",
            timestamp=now,
            status=TransactionStatus.PROCESSED,
            created_at=now,
        )
        match_obj = MatchORM(
            id="match_seed_live_001",
            run_id=run_obj.id,
            match_type="exact",
            confidence=Decimal("0.99"),
            reason="Deterministic exact match on order_id and amount",
            evidence={},
            created_at=now,
        )
        mt1 = MatchTransactionORM(match_id=match_obj.id, transaction_id=t_m1.id)
        mt2 = MatchTransactionORM(match_id=match_obj.id, transaction_id=t_m2.id)
        session.add(t_m1)
        session.add(t_m2)
        session.add(match_obj)
        session.add(mt1)
        session.add(mt2)
        await session.flush()

    await session.commit()


@pytest_asyncio.fixture
async def test_ctx():
    """Isolated client and session fixture per test with engine disposal."""
    engine = create_app_engine(DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_factory() as session:
        await _ensure_seed_records(session)

        async def _override_db():
            yield session

        app.dependency_overrides[get_db_session] = _override_db
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client, session
        app.dependency_overrides.pop(get_db_session, None)

    await engine.dispose()


@pytest.mark.asyncio
async def test_dossier_real_existing_exception(test_ctx, auth_headers):
    """Test AI Investigation dossier for an existing exception in the database."""
    client, session = test_ctx
    stmt = select(ExceptionORM).where(ExceptionORM.resolved == False).limit(1)
    exc = (await session.execute(stmt)).scalar_one_or_none()

    assert exc is not None, "Open exception must exist"

    response = await client.get(f"/api/v1/investigations/{exc.id}", headers=auth_headers)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    data = response.json()

    assert data["entity_type"] == "exception"
    assert data["entity_id"] == exc.id
    assert Decimal(data["financial_exposure"]) == Decimal(str(exc.financial_exposure))
    assert len(data["root_cause_candidates"]) >= 1
    for candidate in data["root_cause_candidates"]:
        assert "cause" in candidate and len(candidate["cause"]) > 0
        assert 0.0 <= float(candidate["confidence"]) <= 1.0
        assert "evidence" in candidate and len(candidate["evidence"]) > 0

    assert data["recommended_action"] is not None
    assert isinstance(data["requires_human_review"], bool)
    assert data["insufficient_evidence"] is False
    assert "reconciliation_evidence" in data


@pytest.mark.asyncio
async def test_dossier_settlement_reconciled_case(test_ctx, auth_headers):
    """Test AI Investigation dossier for a reconciled Razorpay settlement (setl_live_qa_001)."""
    client, session = test_ctx
    response = await client.get("/api/v1/investigations/setl_live_qa_001", headers=auth_headers)

    assert response.status_code == 200
    data = response.json()

    assert data["entity_type"] == "settlement"
    assert data["entity_id"] == "setl_live_qa_001"
    assert data["status"] == "BANK_CREDIT_CONFIRMED"
    assert Decimal(data["financial_exposure"]) == Decimal("0.00")
    assert Decimal(data["variance"]) == Decimal("0.00")
    assert data["variance_type"] == "NO_VARIANCE"
    assert data["requires_human_review"] is False
    assert data["insufficient_evidence"] is False
    assert "UTR_QA_9999" in data["related_ids"]["reference_number"]
    assert "settlement reconciled" in data["recommended_action"].lower()


@pytest.mark.asyncio
async def test_dossier_settlement_variance_case(test_ctx, auth_headers):
    """Test AI Investigation dossier for a settlement with variance / missing bank credit."""
    client, session = test_ctx
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    setl_id = f"setl_var_test_{int(now.timestamp())}"

    setl_tx = TransactionORM(
        id=f"tx_{setl_id}",
        domain_transaction_id=setl_id,
        source=TransactionSource.GATEWAY,
        reference_number="UTR_MISSING_999",
        order_id=None,
        amount=Decimal("75000.00"),
        currency="INR",
        timestamp=now,
        fee=Decimal("1500.00"),
        tax=Decimal("270.00"),
        status=TransactionStatus.PROCESSED,
        meta_data={"type": "settlement", "gateway": "razorpay"},
        created_at=now,
    )
    session.add(setl_tx)
    await session.commit()

    response = await client.get(f"/api/v1/investigations/{setl_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert data["entity_type"] == "settlement"
    assert Decimal(data["financial_exposure"]) == Decimal("73230.00")
    assert abs(Decimal(data["variance"])) == Decimal("73230.00")
    assert data["variance_type"] == "MISSING_BANK_CREDIT"
    assert data["requires_human_review"] is True
    assert len(data["root_cause_candidates"]) >= 1
    assert any("bank" in c["cause"].lower() or "delay" in c["cause"].lower() for c in data["root_cause_candidates"])


@pytest.mark.asyncio
async def test_dossier_matches_actual_database_values(test_ctx, auth_headers):
    """Confirm dossier financial amounts, statuses, and IDs strictly match PostgreSQL database ground truth."""
    client, session = test_ctx
    stmt = select(ExceptionORM).where(ExceptionORM.resolved == False).limit(1)
    db_exc = (await session.execute(stmt)).scalar_one_or_none()

    assert db_exc is not None

    response = await client.get(f"/api/v1/investigations/{db_exc.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert Decimal(data["financial_exposure"]) == Decimal(str(db_exc.financial_exposure))
    assert data["entity_id"] == db_exc.id
    assert data["status"] == (db_exc.status.upper() if db_exc.status else "OPEN")
    assert data["reconciliation_evidence"]["exception_id"] == db_exc.id
    assert data["reconciliation_evidence"]["category"] == str(db_exc.exception_category)


@pytest.mark.asyncio
async def test_dossier_resolved_case(test_ctx, auth_headers):
    """Test AI Investigation dossier for a resolved exception."""
    client, session = test_ctx
    stmt_run = select(ReconciliationRunORM).limit(1)
    run_obj = (await session.execute(stmt_run)).scalar_one_or_none()
    run_id = run_obj.id if run_obj else "run_default"

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    resolved_id = f"exc_resolved_test_{int(now.timestamp())}"

    exc = ExceptionORM(
        id=resolved_id,
        run_id=run_id,
        exception_category=ExceptionCategory.AMOUNT_MISMATCH,
        status="resolved",
        confidence=Decimal("0.99"),
        financial_exposure=Decimal("0.00"),
        expected_cost=Decimal("0.00"),
        explanation="Resolved manually during reconciliation audit",
        resolved=True,
        resolved_at=now,
        created_at=now,
    )
    session.add(exc)
    await session.commit()

    response = await client.get(f"/api/v1/investigations/{resolved_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert data["entity_type"] == "exception"
    assert data["status"] == "RESOLVED"
    assert Decimal(data["financial_exposure"]) == Decimal("0.00")
    assert Decimal(data["variance"]) == Decimal("0.00")
    assert data["variance_type"] == "RESOLVED"
    assert data["requires_human_review"] is False
    assert data["insufficient_evidence"] is False


@pytest.mark.asyncio
async def test_dossier_matched_case(test_ctx, auth_headers):
    """Test AI Investigation dossier for a matched transaction or match ID."""
    client, session = test_ctx
    stmt = select(MatchORM).limit(1)
    match_obj = (await session.execute(stmt)).scalars().first()

    assert match_obj is not None

    response = await client.get(f"/api/v1/investigations/{match_obj.id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert data["entity_type"] == "matched_transaction"
    assert data["status"] == "MATCHED"
    assert Decimal(data["financial_exposure"]) == Decimal("0.00")
    assert Decimal(data["variance"]) == Decimal("0.00")
    assert data["variance_type"] == "NO_VARIANCE"
    assert data["requires_human_review"] is False


@pytest.mark.asyncio
async def test_dossier_nonexistent_id(test_ctx, auth_headers):
    """Test AI Investigation dossier returns 404 for a truly nonexistent ID."""
    client, session = test_ctx
    response = await client.get("/api/v1/investigations/completely_nonexistent_id_404", headers=auth_headers)

    assert response.status_code == 404
    detail = response.json()["detail"]
    assert "not found" in detail.lower()


@pytest.mark.asyncio
async def test_dossier_insufficient_evidence_case(test_ctx, auth_headers):
    """Test AI Investigation dossier explicitly returns insufficient evidence when records are missing."""
    client, session = test_ctx
    stmt_run = select(ReconciliationRunORM).limit(1)
    run_obj = (await session.execute(stmt_run)).scalar_one_or_none()
    run_id = run_obj.id if run_obj else "run_default"

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    orphan_exc_id = f"exc_insuf_test_{int(now.timestamp())}"

    exc = ExceptionORM(
        id=orphan_exc_id,
        run_id=run_id,
        exception_category=ExceptionCategory.MISSING_SOURCE,
        status="open",
        confidence=Decimal("0.50"),
        financial_exposure=Decimal("15000.00"),
        expected_cost=Decimal("7500.00"),
        explanation="Unlinked exception missing feed records",
        resolved=False,
        created_at=now,
    )
    session.add(exc)
    await session.commit()

    response = await client.get(f"/api/v1/investigations/{orphan_exc_id}", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "INSUFFICIENT_EVIDENCE"
    assert data["insufficient_evidence"] is True
    assert data["requires_human_review"] is True
    assert "insufficient evidence" in data["evidence_summary"].lower()
    assert any("insufficient evidence" in c["cause"].lower() for c in data["root_cause_candidates"])


@pytest.mark.asyncio
async def test_dossier_no_sensitive_data_leaks(test_ctx, auth_headers):
    """Confirm AI claims are evidence-grounded and no sensitive credentials or PII leak."""
    client, session = test_ctx
    response = await client.get("/api/v1/investigations/setl_live_qa_001", headers=auth_headers)

    assert response.status_code == 200
    text_content = response.text.lower()

    sensitive_patterns = ["password", "bearer ", "private_key", "sk_live", "rzp_live"]
    for pattern in sensitive_patterns:
        assert pattern not in text_content, f"Potential sensitive leak detected: {pattern}"
