"""
API Route tests for Razorpay Integration & Webhook Endpoints.
"""

import hashlib
import hmac
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
from httpx import ASGITransport

from app.api.dependencies import get_db_session
from app.api.main import app


@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    res_mock = MagicMock()
    res_mock.scalar_one_or_none.return_value = None
    res_mock.scalars.return_value.first.return_value = None
    res_mock.scalars.return_value.all.return_value = []
    session.execute.return_value = res_mock
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_get_razorpay_status_endpoint(mock_db_session):
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    try:
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/integrations/razorpay/status")
            assert response.status_code == 200
            data = response.json()
            assert "configured" in data
            assert "mode" in data
            assert "key_id_prefix" in data
            assert "webhook_configured" in data
            # Ensure secrets are NEVER exposed in JSON responses
            assert "key_secret" not in data
            assert "webhook_secret" not in data
    finally:
        app.dependency_overrides.pop(get_db_session, None)


@pytest.mark.asyncio
async def test_sync_razorpay_payments_endpoint(mock_db_session):
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    mock_payments = [
        {"id": f"pay_test_{i}", "entity": "payment", "amount": 10000, "currency": "INR", "status": "captured", "created_at": 1725200000}
        for i in range(5)
    ]
    try:
        with patch("app.integrations.razorpay.client.RazorpayClient.fetch_paginated_entities", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_payments
            transport = ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                payload = {"limit": 5, "auto_reconcile": False, "use_fallback_if_unconfigured": True}
                response = await client.post("/api/v1/integrations/razorpay/sync/payments", json=payload)
                assert response.status_code == 200
                data = response.json()
                assert data["records_fetched"] == 5
                assert data["records_normalized"] == 5
                assert "run_id" in data
    finally:
        app.dependency_overrides.pop(get_db_session, None)


@pytest.mark.asyncio
async def test_sync_razorpay_orders_endpoint(mock_db_session):
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    mock_orders = [
        {"id": f"order_test_{i}", "entity": "order", "amount": 10000, "currency": "INR", "status": "paid", "created_at": 1725200000}
        for i in range(5)
    ]
    try:
        with patch("app.integrations.razorpay.client.RazorpayClient.fetch_paginated_entities", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_orders
            transport = ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                payload = {"limit": 5, "auto_reconcile": False, "use_fallback_if_unconfigured": True}
                response = await client.post("/api/v1/integrations/razorpay/sync/orders", json=payload)
                assert response.status_code == 200
                data = response.json()
                assert data["records_fetched"] == 5
                assert data["records_normalized"] == 5
                assert data["entity_type"] == "orders"
    finally:
        app.dependency_overrides.pop(get_db_session, None)


@pytest.mark.asyncio
async def test_sync_razorpay_unified_all_endpoint(mock_db_session):
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    mock_items = [
        {"id": f"item_test_{i}", "entity": "payment", "amount": 10000, "currency": "INR", "status": "captured", "created_at": 1725200000}
        for i in range(3)
    ]
    try:
        with patch("app.integrations.razorpay.client.RazorpayClient.fetch_paginated_entities", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = mock_items
            transport = ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                payload = {"limit": 3, "auto_reconcile": False, "use_fallback_if_unconfigured": True}
                response = await client.post("/api/v1/integrations/razorpay/sync", json=payload)
                assert response.status_code == 200
                data = response.json()
                assert data["total_records_fetched"] == 9
                assert "payments" in data
                assert "orders" in data
                assert "settlements" in data
    finally:
        app.dependency_overrides.pop(get_db_session, None)


@pytest.mark.asyncio
async def test_public_webhook_endpoint_success_and_deduplication(mock_db_session):
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    secret = "rzp_test_secret_sentinel"

    payload_dict = {
        "event": "payment.captured",
        "event_id": "evt_route_test_999",
        "payload": {
            "payment": {
                "entity": {
                    "id": "pay_route_test_999",
                    "amount": 150000,
                    "currency": "INR",
                    "status": "captured",
                    "order_id": "order_route_999",
                    "fee": 3000,
                    "tax": 540,
                    "created_at": 1725200000,
                }
            }
        },
    }
    raw_body = json.dumps(payload_dict).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()

    try:
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            headers = {"X-Razorpay-Signature": sig, "Content-Type": "application/json"}
            resp1 = await client.post("/api/v1/webhooks/razorpay", content=raw_body, headers=headers)
            assert resp1.status_code == 200
            assert resp1.json()["status"] == "PROCESSED"
            assert resp1.json()["event_id"] == "evt_route_test_999"
    finally:
        app.dependency_overrides.pop(get_db_session, None)


@pytest.mark.asyncio
async def test_public_webhook_invalid_signature_rejected(mock_db_session):
    app.dependency_overrides[get_db_session] = lambda: mock_db_session
    raw_body = b'{"event":"payment.captured","id":"evt_bad_sig"}'
    headers = {"X-Razorpay-Signature": "invalid_signature_hash", "Content-Type": "application/json"}

    try:
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/webhooks/razorpay", content=raw_body, headers=headers)
            assert resp.status_code == 400
            assert "signature" in resp.json()["detail"].lower()
    finally:
        app.dependency_overrides.pop(get_db_session, None)
