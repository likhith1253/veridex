"""
Integration and Unit tests for Razorpay Integration Service (Sync, Fallback, Idempotency, Unified Sync).
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
    res_run = MagicMock()
    res_run.scalars.return_value.first.return_value = None
    res_existing = MagicMock()
    res_existing.scalar_one_or_none.return_value = None
    session.execute.return_value = res_existing
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    req = RazorpaySyncRequest(limit=10, auto_reconcile=False, use_fallback_if_unconfigured=True)

    res = await service.sync_payments(session=session, req=req)
    assert res.source == "synthetic_fallback"
    assert res.records_fetched == 10
    assert res.records_normalized == 10
    assert res.records_inserted == 10
    assert res.records_skipped == 0
    assert res.records_rejected == 0
    assert "warning" in res.model_dump()


@pytest.mark.asyncio
async def test_integration_service_synthetic_fallback_orders():
    config = RazorpayConfig(key_id="", key_secret="", webhook_secret="")
    service = RazorpayIntegrationService(config=config)

    session = AsyncMock()
    res_existing = MagicMock()
    res_existing.scalar_one_or_none.return_value = None
    session.execute.return_value = res_existing
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    req = RazorpaySyncRequest(limit=5, auto_reconcile=False, use_fallback_if_unconfigured=True)

    res = await service.sync_orders(session=session, req=req)
    assert res.source == "synthetic_fallback"
    assert res.entity_type == "orders"
    assert res.records_fetched == 5
    assert res.records_normalized == 5
    assert res.records_inserted == 5
    assert res.records_rejected == 0


@pytest.mark.asyncio
async def test_integration_service_synthetic_fallback_settlements():
    config = RazorpayConfig(key_id="", key_secret="", webhook_secret="")
    service = RazorpayIntegrationService(config=config)

    session = AsyncMock()
    res_existing = MagicMock()
    res_existing.scalar_one_or_none.return_value = None
    session.execute.return_value = res_existing
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    req = RazorpaySyncRequest(limit=5, auto_reconcile=False, use_fallback_if_unconfigured=True)

    res = await service.sync_settlements(session=session, req=req)
    assert res.source == "synthetic_fallback"
    assert res.records_fetched == 5
    assert res.records_normalized == 5
    assert res.records_inserted == 5
    assert res.records_rejected == 0


@pytest.mark.asyncio
async def test_integration_service_idempotent_duplicate_sync():
    """Verify that synchronizing existing transactions skips them and produces 0 duplicates."""
    config = RazorpayConfig(key_id="", key_secret="", webhook_secret="")
    service = RazorpayIntegrationService(config=config)

    session = AsyncMock()
    # Mock existing record found on query
    mock_orm = MagicMock(id="existing_orm_id_123")
    res_existing = MagicMock()
    res_existing.scalar_one_or_none.return_value = mock_orm
    session.execute.return_value = res_existing
    session.add = MagicMock()
    session.flush = AsyncMock()

    req = RazorpaySyncRequest(limit=5, auto_reconcile=False, use_fallback_if_unconfigured=True)

    res = await service.sync_payments(session=session, req=req)
    assert res.records_fetched == 5
    assert res.records_normalized == 5
    assert res.records_inserted == 0
    assert res.records_skipped == 5



@pytest.mark.asyncio
async def test_integration_service_unified_sync_all():
    config = RazorpayConfig(key_id="", key_secret="", webhook_secret="")
    service = RazorpayIntegrationService(config=config)

    session = AsyncMock()
    res_existing = MagicMock()
    res_existing.scalar_one_or_none.return_value = None
    session.execute.return_value = res_existing
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()

    req = RazorpaySyncRequest(limit=4, auto_reconcile=False, use_fallback_if_unconfigured=True)

    res = await service.sync_all(session=session, req=req)
    assert res.total_records_fetched == 12  # 4 payments + 4 orders + 4 settlements
    assert res.total_records_normalized == 12
    assert res.total_records_inserted == 12
    assert res.total_records_skipped == 0
    assert res.payments.entity_type == "payments"
    assert res.orders.entity_type == "orders"
    assert res.settlements.entity_type == "settlements"
