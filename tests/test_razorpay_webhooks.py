"""
Integration and Unit tests for Razorpay Webhook HMAC Verification and Durable Idempotency.
"""

import hashlib
import hmac
import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.integrations.razorpay.config import RazorpayConfig
from app.integrations.razorpay.exceptions import RazorpaySignatureError
from app.integrations.razorpay.webhooks import RazorpayWebhookHandler


@pytest.mark.asyncio
async def test_webhook_signature_verification():
    secret = "rzp_test_secret_test_suite"
    config = RazorpayConfig(webhook_secret=secret)
    handler = RazorpayWebhookHandler(config=config)

    raw_body = b'{"event":"payment.captured","id":"evt_12345"}'
    valid_sig = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    invalid_sig = "bad_signature_value"

    assert handler.verify_signature(raw_body, valid_sig) is True
    assert handler.verify_signature(raw_body, invalid_sig) is False
    assert handler.verify_signature(raw_body, None) is False


@pytest.mark.asyncio
async def test_webhook_processing_and_idempotency():
    secret = "rzp_test_secret_test_suite"
    config = RazorpayConfig(webhook_secret=secret)
    handler = RazorpayWebhookHandler(config=config)

    payload_dict = {
        "event": "settlement.processed",
        "event_id": "evt_settle_test_001",
        "payload": {
            "settlement": {
                "entity": {
                    "id": "setl_test_webhook_001",
                    "amount": 2500000,
                    "fees": 50000,
                    "tax": 9000,
                    "utr": "UTR_WH_TEST_001",
                    "status": "processed",
                    "created_at": 1725200000,
                }
            }
        },
    }
    raw_body = json.dumps(payload_dict).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    # Mock database session
    session = AsyncMock()
    # First query for idempotency: None (not yet processed)
    res_none = MagicMock()
    res_none.scalar_one_or_none.return_value = None
    # Second query for run check: None (creates new run)
    res_run = MagicMock()
    res_run.scalars.return_value.first.return_value = None
    res_run.scalars.return_value.all.return_value = []
    session.execute.side_effect = [res_none, res_run, res_none, res_none, res_run, res_none]
    session.add = MagicMock()
    session.flush = AsyncMock()

    # 1. First execution: should be PROCESSED
    res1 = await handler.process_webhook(raw_body=raw_body, signature=sig, session=session)
    assert res1.status == "PROCESSED"
    assert res1.event_id == "evt_settle_test_001"
    assert res1.event_type == "settlement.processed"

    # 2. Second execution (replay/duplicate)
    existing_mock = MagicMock(event_id="evt_settle_test_001")
    res_existing = MagicMock()
    res_existing.scalar_one_or_none.return_value = existing_mock
    session.execute.side_effect = [res_existing]

    res2 = await handler.process_webhook(raw_body=raw_body, signature=sig, session=session)
    assert res2.status == "DUPLICATE_IGNORED"
    assert res2.event_id == "evt_settle_test_001"
    assert "duplicate" in res2.message.lower()


@pytest.mark.asyncio
async def test_webhook_invalid_signature_raises_error():
    secret = "rzp_test_secret_test_suite"
    config = RazorpayConfig(webhook_secret=secret)
    handler = RazorpayWebhookHandler(config=config)

    raw_body = b'{"event":"payment.captured"}'
    bad_sig = "0000000000000000000000000000000000000000000000000000000000000000"

    session = AsyncMock()
    with pytest.raises(RazorpaySignatureError):
        await handler.process_webhook(raw_body=raw_body, signature=bad_sig, session=session)
