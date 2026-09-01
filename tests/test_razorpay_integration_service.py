"""
Integration and Unit tests for Razorpay Integration Service (Sync & Fallback).
"""

from decimal import Decimal
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.integrations.razorpay.config import RazorpayConfig
from app.integrations.razorpay.schemas import RazorpaySyncRequest
from app.integrations.razorpay.service import RazorpayIntegrationService


@pytest.mark.asyncio
async def test_integration_service_status():
    config = RazorpayConfig(key_id="rzp_test_sample", key_secret="secret", webhook_secret="whsec")
    service = RazorpayIntegrationService(config=config)

    session = AsyncMock()
    res_wh = MagicMock()
    res_wh.scalar_one_or_none.return_value = None
    res_audit = MagicMock()
    res_audit.scalar_one_or_none.return_value = None
    session.execute.side_effect = [res_wh, res_audit]

    status = await service.get_status(session=session)
    assert status.configured is True
    assert status.mode == "test"
    assert status.key_id_prefix == "rzp_test..."
    assert status.webhook_configured is True


@pytest.mark.asyncio
async def test_integration_service_synthetic_fallback_payments():
    config = RazorpayConfig(key_id="", key_secret="", webhook_secret="")
    service = RazorpayIntegrationService(config=config)

    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock())
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    req = RazorpaySyncRequest(limit=10, auto_reconcile=False, use_fallback_if_unconfigured=True)

    res = await service.sync_payments(session=session, req=req)
    assert res.source == "synthetic_fallback"
    assert res.records_fetched == 10
    assert res.records_normalized == 10
    assert res.records_rejected == 0
    assert "warning" in res.model_dump()


@pytest.mark.asyncio
async def test_integration_service_synthetic_fallback_settlements():
    config = RazorpayConfig(key_id="", key_secret="", webhook_secret="")
    service = RazorpayIntegrationService(config=config)

    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock())
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    req = RazorpaySyncRequest(limit=5, auto_reconcile=False, use_fallback_if_unconfigured=True)

    res = await service.sync_settlements(session=session, req=req)
    assert res.source == "synthetic_fallback"
    assert res.records_fetched == 5
    assert res.records_normalized == 5
    assert res.records_rejected == 0
