import hashlib
import hmac
import json
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
    Exception as ExceptionORM,
    Match as MatchORM,
    ReconciliationRun as ReconciliationRunORM,
    Transaction as TransactionORM,
    TransactionSource,
    TransactionStatus,
    WebhookEvent as WebhookEventORM,
)
from app.database.session import DATABASE_URL, create_app_engine
from app.database.utils import utcnow
from app.integrations.razorpay.config import razorpay_config


@pytest.fixture
def webhook_secret():
    return razorpay_config.webhook_secret or "rzp_test_secret_sentinel"


def compute_signature(secret: str, raw_body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


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
                id="run_wh_test_001",
                run_id="run_wh_test_001",
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
async def test_webhook_invalid_signature_rejected(test_ctx):
    """Confirm webhook with bad signature is rejected with HTTP 400."""
    client, session = test_ctx
    raw_body = b'{"event":"settlement.processed","id":"evt_bad_sig"}'
    headers = {"X-Razorpay-Signature": "invalid_signature_hash", "Content-Type": "application/json"}

    response = await client.post("/api/v1/webhooks/razorpay", content=raw_body, headers=headers)
    assert response.status_code == 400
    assert "invalid" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_webhook_malformed_json_rejected(test_ctx, webhook_secret):
    """Confirm malformed non-JSON payload is rejected with HTTP 400."""
    client, session = test_ctx
    raw_body = b"NOT_VALID_JSON_CONTENT{{{{"
    sig = compute_signature(webhook_secret, raw_body)
    headers = {"X-Razorpay-Signature": sig, "Content-Type": "application/json"}

    response = await client.post("/api/v1/webhooks/razorpay", content=raw_body, headers=headers)
    assert response.status_code == 400
    assert "malformed" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_webhook_duplicate_delivery_idempotency(test_ctx, webhook_secret):
    """Confirm duplicate delivery returns DUPLICATE_IGNORED idempotently without duplicate recon."""
    client, session = test_ctx
    event_id = f"evt_dup_{utcnow().timestamp()}"
    payload_dict = {
        "event": "settlement.processed",
        "event_id": event_id,
        "payload": {
            "settlement": {
                "entity": {
                    "id": f"setl_dup_{utcnow().timestamp()}",
                    "amount": 2500000,
                    "fees": 50000,
                    "tax": 9000,
                    "utr": f"UTR_DUP_{utcnow().timestamp()}",
                    "status": "processed",
                    "created_at": 1725200000,
                }
            }
        },
    }
    raw_body = json.dumps(payload_dict).encode("utf-8")
    sig = compute_signature(webhook_secret, raw_body)
    headers = {"X-Razorpay-Signature": sig, "Content-Type": "application/json"}

    # First delivery
    res1 = await client.post("/api/v1/webhooks/razorpay", content=raw_body, headers=headers)
    assert res1.status_code == 200
    assert res1.json()["status"] == "PROCESSED"

    # Second delivery (replay)
    res2 = await client.post("/api/v1/webhooks/razorpay", content=raw_body, headers=headers)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["status"] == "DUPLICATE_IGNORED"
    assert "duplicate" in data2["message"].lower()


@pytest.mark.asyncio
async def test_webhook_settlement_no_bank_credit_creates_exception(test_ctx, webhook_secret):
    """Confirm settlement without bank credit does NOT claim match, but creates an exception."""
    client, session = test_ctx
    now = utcnow()
    setl_id = f"setl_nobank_{int(now.timestamp())}"
    utr = f"UTR_NOBANK_{int(now.timestamp())}"

    payload_dict = {
        "event": "settlement.processed",
        "event_id": f"evt_{setl_id}",
        "payload": {
            "settlement": {
                "entity": {
                    "id": setl_id,
                    "amount": 1000000,  # ₹10,000.00
                    "fees": 20000,      # ₹200.00
                    "tax": 3600,        # ₹36.00
                    "utr": utr,
                    "status": "processed",
                    "created_at": int(now.timestamp()),
                }
            }
        },
    }
    raw_body = json.dumps(payload_dict).encode("utf-8")
    sig = compute_signature(webhook_secret, raw_body)
    headers = {"X-Razorpay-Signature": sig, "Content-Type": "application/json"}

    response = await client.post("/api/v1/webhooks/razorpay", content=raw_body, headers=headers)
    assert response.status_code == 200
    data = response.json()

    # Must NOT claim bank credit
    assert data["reconciliation_status"] == "EXCEPTION"
    assert data["action"] == "ESCALATE_EXCEPTION"
    assert "exception created" in data["message"].lower()

    # Verify exception in database
    stmt_exc = select(ExceptionORM).where(ExceptionORM.explanation.contains(setl_id))
    exc = (await session.execute(stmt_exc)).scalar_one_or_none()
    assert exc is not None
    # Expected net: 10000 - 200 - 36 = 9764.00
    assert Decimal(str(exc.financial_exposure)) == Decimal("9764.00")
    assert exc.resolved is False


@pytest.mark.asyncio
async def test_webhook_settlement_with_matching_bank_credit_reconciles(test_ctx, webhook_secret):
    """Confirm settlement with matching bank credit reconciles into a Match record."""
    client, session = test_ctx
    now = utcnow()
    setl_id = f"setl_match_{int(now.timestamp())}"
    utr = f"UTR_MATCH_{int(now.timestamp())}"

    # 1. Pre-seed matching bank statement credit
    # Gross: ₹50,000.00, Fee: ₹1,000.00, Tax: ₹180.00 -> Expected Net: ₹48,820.00
    bank_tx = TransactionORM(
        id=f"tx_bank_{setl_id}",
        domain_transaction_id=f"bk_{setl_id}",
        source=TransactionSource.BANK,
        reference_number=utr,
        order_id=None,
        amount=Decimal("48820.00"),
        currency="INR",
        timestamp=now,
        fee=None,
        tax=None,
        status=TransactionStatus.PROCESSED,
        meta_data={"type": "credit"},
        narration=f"NEFT CR - RAZORPAY SETTLEMENT {utr}",
        created_at=now,
    )
    session.add(bank_tx)
    await session.commit()

    # 2. Ingest settlement.processed webhook
    payload_dict = {
        "event": "settlement.processed",
        "event_id": f"evt_{setl_id}",
        "payload": {
            "settlement": {
                "entity": {
                    "id": setl_id,
                    "amount": 5000000,  # ₹50,000.00 gross
                    "fees": 100000,     # ₹1,000.00 fee
                    "tax": 18000,       # ₹180.00 tax
                    "utr": utr,
                    "status": "processed",
                    "created_at": int(now.timestamp()),
                }
            }
        },
    }
    raw_body = json.dumps(payload_dict).encode("utf-8")
    sig = compute_signature(webhook_secret, raw_body)
    headers = {"X-Razorpay-Signature": sig, "Content-Type": "application/json"}

    response = await client.post("/api/v1/webhooks/razorpay", content=raw_body, headers=headers)
    assert response.status_code == 200
    data = response.json()

    assert data["reconciliation_status"] == "MATCHED"
    assert data["action"] == "AUTO_MATCH"
    assert data["match_id"] is not None
    assert data["matched_transaction_id"] == f"bk_{setl_id}"

    # Verify Match in PostgreSQL
    stmt_match = select(MatchORM).where(MatchORM.id == data["match_id"])
    match_rec = (await session.execute(stmt_match)).scalar_one_or_none()
    assert match_rec is not None
    assert match_rec.confidence == Decimal("1.00")
