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
    Transaction as TransactionORM,
    TransactionSource,
    TransactionStatus,
)
from app.database.session import DATABASE_URL, create_app_engine
from app.database.utils import utcnow
from app.services.tax_auditor_service import TaxAuditorService, TaxAuditStatus


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
        async def _override_db():
            yield session

        app.dependency_overrides[get_db_session] = _override_db
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client, session
        app.dependency_overrides.pop(get_db_session, None)

    await engine.dispose()


@pytest.mark.asyncio
async def test_tax_audit_exact_match(test_ctx, auth_headers):
    """Confirm exact tax match results in MATCHED status with zero variance."""
    client, session = test_ctx
    now = utcnow()
    setl_id = f"setl_tax_match_{int(now.timestamp())}"

    # Gross: 100,000, Fee: 2,000, Tax: 360.00, Expected tax recorded in metadata: 360.00
    tx = TransactionORM(
        id=f"tx_{setl_id}",
        domain_transaction_id=setl_id,
        source=TransactionSource.GATEWAY,
        reference_number=f"UTR_{setl_id}",
        order_id=None,
        amount=Decimal("100000.00"),
        currency="INR",
        timestamp=now,
        fee=Decimal("2000.00"),
        tax=Decimal("360.00"),
        status=TransactionStatus.PROCESSED,
        meta_data={
            "type": "settlement",
            "expected_tax": "360.00",
        },
        narration=f"Settlement {setl_id}",
        created_at=now,
    )
    session.add(tx)
    await session.commit()

    # Service-level test
    service = TaxAuditorService(session)
    result = await service.audit_settlement_tax(setl_id)
    assert result.status == TaxAuditStatus.MATCHED
    assert result.reported_tax == Decimal("360.00")
    assert result.expected_tax == Decimal("360.00")
    assert result.tax_variance == Decimal("0.00")
    assert "exactly matches" in result.explanation.lower()

    # API-level test
    res = await client.get(f"/api/v1/settlements/{setl_id}/tax-audit", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "MATCHED"
    assert Decimal(data["gross_amount"]) == Decimal("100000.00")
    assert Decimal(data["reported_tax"]) == Decimal("360.00")
    assert Decimal(data["expected_tax"]) == Decimal("360.00")
    assert Decimal(data["tax_variance"]) == Decimal("0.00")


@pytest.mark.asyncio
async def test_tax_audit_variance_detected(test_ctx, auth_headers):
    """Confirm tax discrepancy results in VARIANCE status with exact Decimal difference."""
    client, session = test_ctx
    now = utcnow()
    setl_id = f"setl_tax_var_{int(now.timestamp())}"

    # Gross: 50,000, Fee: 1,000, Reported Tax: 250.00, Expected Tax: 180.00 -> Variance: +70.00
    tx = TransactionORM(
        id=f"tx_{setl_id}",
        domain_transaction_id=setl_id,
        source=TransactionSource.GATEWAY,
        reference_number=f"UTR_{setl_id}",
        order_id=None,
        amount=Decimal("50000.00"),
        currency="INR",
        timestamp=now,
        fee=Decimal("1000.00"),
        tax=Decimal("250.00"),
        status=TransactionStatus.PROCESSED,
        meta_data={
            "type": "settlement",
            "expected_tax": "180.00",
        },
        narration=f"Settlement {setl_id}",
        created_at=now,
    )
    session.add(tx)
    await session.commit()

    res = await client.get(f"/api/v1/settlements/{setl_id}/tax-audit", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "VARIANCE"
    assert Decimal(data["reported_tax"]) == Decimal("250.00")
    assert Decimal(data["expected_tax"]) == Decimal("180.00")
    assert Decimal(data["tax_variance"]) == Decimal("70.00")
    assert "tax discrepancy detected" in data["explanation"].lower()


@pytest.mark.asyncio
async def test_tax_audit_missing_expected_tax_insufficient_evidence(test_ctx, auth_headers):
    """Confirm missing expected tax does not invent values, returns INSUFFICIENT_EVIDENCE."""
    client, session = test_ctx
    now = utcnow()
    setl_id = f"setl_tax_no_exp_{int(now.timestamp())}"

    # Settlement with reported tax, but NO authoritative expected tax recorded
    tx = TransactionORM(
        id=f"tx_{setl_id}",
        domain_transaction_id=setl_id,
        source=TransactionSource.GATEWAY,
        reference_number=f"UTR_{setl_id}",
        order_id=None,
        amount=Decimal("25000.00"),
        currency="INR",
        timestamp=now,
        fee=Decimal("500.00"),
        tax=Decimal("90.00"),
        status=TransactionStatus.PROCESSED,
        meta_data={
            "type": "settlement",
            # No expected_tax or agreed_tax_rate
        },
        narration=f"Settlement {setl_id}",
        created_at=now,
    )
    session.add(tx)
    await session.commit()

    res = await client.get(f"/api/v1/settlements/{setl_id}/tax-audit", headers=auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "INSUFFICIENT_EVIDENCE"
    assert data["expected_tax"] is None
    assert data["tax_variance"] is None
    assert "authoritative expected tax cannot be established" in data["explanation"].lower()


@pytest.mark.asyncio
async def test_tax_audit_zero_negative_invalid_values(test_ctx, auth_headers):
    """Confirm zero, negative, or invalid gross and tax values are caught safely."""
    client, session = test_ctx
    now = utcnow()

    # 1. Zero gross amount
    setl_zero = f"setl_tax_zero_{int(now.timestamp())}"
    tx_zero = TransactionORM(
        id=f"tx_{setl_zero}",
        domain_transaction_id=setl_zero,
        source=TransactionSource.GATEWAY,
        reference_number="UTR_0",
        amount=Decimal("0.00"),
        currency="INR",
        timestamp=now,
        tax=Decimal("10.00"),
        status=TransactionStatus.PROCESSED,
        meta_data={"type": "settlement"},
        created_at=now,
    )
    session.add(tx_zero)

    # 2. Negative reported tax
    setl_neg_tax = f"setl_tax_neg_{int(now.timestamp())}"
    tx_neg_tax = TransactionORM(
        id=f"tx_{setl_neg_tax}",
        domain_transaction_id=setl_neg_tax,
        source=TransactionSource.GATEWAY,
        reference_number="UTR_NEG",
        amount=Decimal("1000.00"),
        currency="INR",
        timestamp=now,
        tax=Decimal("-50.00"),
        status=TransactionStatus.PROCESSED,
        meta_data={"type": "settlement", "expected_tax": "18.00"},
        created_at=now,
    )
    session.add(tx_neg_tax)
    await session.commit()

    res1 = await client.get(f"/api/v1/settlements/{setl_zero}/tax-audit", headers=auth_headers)
    assert res1.status_code == 200
    assert res1.json()["status"] == "INSUFFICIENT_EVIDENCE"
    assert "invalid gross amount" in res1.json()["explanation"].lower()

    res2 = await client.get(f"/api/v1/settlements/{setl_neg_tax}/tax-audit", headers=auth_headers)
    assert res2.status_code == 200
    assert res2.json()["status"] == "INSUFFICIENT_EVIDENCE"
    assert "negative reported tax" in res2.json()["explanation"].lower()


@pytest.mark.asyncio
async def test_tax_audit_nonexistent_settlement_returns_404(test_ctx, auth_headers):
    """Confirm nonexistent settlement returns 404."""
    client, session = test_ctx
    res = await client.get("/api/v1/settlements/completely_fake_settlement_id/tax-audit", headers=auth_headers)
    assert res.status_code == 404
    assert "settlement not found" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_tax_audit_no_secrets_exposed(test_ctx, auth_headers):
    """Confirm no secrets, keys, or sensitive internal credentials appear in response."""
    client, session = test_ctx
    now = utcnow()
    setl_id = f"setl_tax_sec_{int(now.timestamp())}"

    tx = TransactionORM(
        id=f"tx_{setl_id}",
        domain_transaction_id=setl_id,
        source=TransactionSource.GATEWAY,
        reference_number=f"UTR_{setl_id}",
        amount=Decimal("1000.00"),
        currency="INR",
        timestamp=now,
        tax=Decimal("18.00"),
        status=TransactionStatus.PROCESSED,
        meta_data={"type": "settlement", "expected_tax": "18.00", "key_secret": "SHOULD_NOT_LEAK"},
        created_at=now,
    )
    session.add(tx)
    await session.commit()

    res = await client.get(f"/api/v1/settlements/{setl_id}/tax-audit", headers=auth_headers)
    assert res.status_code == 200
    raw_text = res.text
    for leak in ["test123", "rzp_test", "SHOULD_NOT_LEAK", "webhook_secret", "key_secret"]:
        assert leak not in raw_text
