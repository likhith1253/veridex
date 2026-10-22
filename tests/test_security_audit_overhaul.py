"""Regression tests for the 2026-10 security audit (see docs/SECURITY.md)."""
import hashlib
import hmac
import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.main import create_app
from app.integrations.razorpay.config import RazorpayConfig
from app.integrations.razorpay.webhooks import RazorpayWebhookHandler

BODY = json.dumps({"event": "payment.captured", "payload": {}}).encode()


def _sig(secret: str, body: bytes = BODY) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


# --- Webhook signature verification -------------------------------------


def test_webhook_rejects_when_no_secret_configured():
    handler = RazorpayWebhookHandler(RazorpayConfig(webhook_secret=""))
    # Signatures made with formerly hardcoded fallback secrets must not verify.
    assert not handler.verify_signature(BODY, _sig("rzp_test_secret_sentinel"))
    assert not handler.verify_signature(BODY, _sig("your_webhook_secret"))
    assert not handler.verify_signature(BODY, _sig(""))


def test_webhook_only_accepts_configured_secret():
    handler = RazorpayWebhookHandler(RazorpayConfig(webhook_secret="s3cret-for-test"))
    assert handler.verify_signature(BODY, _sig("s3cret-for-test"))
    assert not handler.verify_signature(BODY, _sig("rzp_test_secret_sentinel"))
    assert not handler.verify_signature(BODY, None)
    assert not handler.verify_signature(BODY, "")
    assert not handler.verify_signature(BODY + b" ", _sig("s3cret-for-test"))


@pytest.mark.asyncio
async def test_legacy_integration_webhook_requires_signature():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/v1/integrations/razorpay/webhook", content=BODY)
        assert r.status_code == 400  # missing signature must not skip verification
        r = await c.post(
            "/api/v1/integrations/razorpay/webhook",
            content=BODY,
            headers={"X-Razorpay-Signature": "deadbeef"},
        )
        assert r.status_code == 400


@pytest.mark.asyncio
async def test_primary_webhook_rejects_bad_signature():
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/v1/webhooks/razorpay", content=BODY)
        assert r.status_code == 400
        r = await c.post(
            "/api/v1/webhooks/razorpay", content=BODY, headers={"X-Razorpay-Signature": "00"}
        )
        assert r.status_code == 400


# --- API key enforcement -------------------------------------------------

PROTECTED = [
    ("GET", "/api/v1/controller/summary"),
    ("GET", "/api/v1/controller/exceptions"),
    ("POST", "/api/v1/controller/ingest/batch"),
    ("GET", "/runs"),
    ("POST", "/reconciliation/runs"),
    ("GET", "/api/v1/integrations/razorpay/status"),
    ("POST", "/api/v1/integrations/razorpay/sync"),
    ("POST", "/api/v1/actions/recommend"),
    ("GET", "/api/v1/investigations/anything"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("method,path", PROTECTED)
async def test_protected_routes_require_key_when_configured(monkeypatch, method, path):
    monkeypatch.setenv("SENTINEL_API_KEY", "unit-test-key")
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.request(method, path, json={})
        assert r.status_code == 401
        r = await c.request(method, path, json={}, headers={"X-API-Key": "wrong"})
        assert r.status_code == 401


@pytest.mark.asyncio
async def test_public_routes_stay_public(monkeypatch):
    monkeypatch.setenv("SENTINEL_API_KEY", "unit-test-key")
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        assert (await c.get("/health")).status_code == 200
        assert (await c.get("/")).status_code == 200


@pytest.mark.asyncio
async def test_auth_fails_closed_in_production_without_key(monkeypatch):
    for k in ("VERIDEX_API_KEY", "SENTINEL_API_KEY", "API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        assert (await c.get("/runs")).status_code == 503
        assert (await c.get("/health")).status_code == 200


# --- CORS ----------------------------------------------------------------


@pytest.mark.asyncio
async def test_cors_does_not_allow_arbitrary_origin_with_credentials(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.example.com")
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/health", headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in r.headers
        assert "access-control-allow-credentials" not in r.headers
        r = await c.get("/health", headers={"Origin": "https://app.example.com"})
        assert r.headers.get("access-control-allow-origin") == "https://app.example.com"


# --- Input bounds --------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_ingest_rejects_oversized_batches():
    app = create_app()
    rec = {"txn_id": "t", "amount": "1.00"}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/v1/controller/ingest/batch", json={"gateway_records": [rec] * 10001}
        )
        assert r.status_code == 422
