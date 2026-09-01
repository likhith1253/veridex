"""
Payment Gateway Webhook & Integration Routes for Project Sentinel.

Endpoints:
- GET  /api/v1/integrations/razorpay/status          (Safe connectivity & metadata status)
- POST /api/v1/integrations/razorpay/sync            (Unified sync for payments, orders, settlements)
- POST /api/v1/integrations/razorpay/sync/payments   (Synchronize payments feed)
- POST /api/v1/integrations/razorpay/sync/orders     (Synchronize orders feed)
- POST /api/v1/integrations/razorpay/sync/settlements(Synchronize settlements feed)
- POST /api/v1/integrations/razorpay/webhook         (Legacy / direct integration webhook)
"""

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session, get_investigation_service
from app.integrations.razorpay import (
    RazorpayIntegrationService,
    RazorpayNormalizer,
    RazorpaySignatureError,
    RazorpayStatusResponse,
    RazorpaySyncRequest,
    RazorpaySyncResponse,
    RazorpayUnifiedSyncResponse,
    RazorpayWebhookHandler,
    RazorpayWebhookResponse,
)
from app.investigation.service import InvestigationService
from app.services.incremental_reconciliation import IncrementalReconciliationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/integrations", tags=["Payment Integrations"])
webhook_handler = RazorpayWebhookHandler()
integration_service = RazorpayIntegrationService()


@router.get("/razorpay/status", response_model=RazorpayStatusResponse)
async def get_razorpay_status(
    session: AsyncSession = Depends(get_db_session),
) -> RazorpayStatusResponse:
    """Retrieve safe metadata and connectivity status for Razorpay integration."""
    return await integration_service.get_status(session=session)


@router.post("/razorpay/sync", response_model=RazorpayUnifiedSyncResponse)
async def sync_razorpay_all(
    request: RazorpaySyncRequest = RazorpaySyncRequest(),
    session: AsyncSession = Depends(get_db_session),
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> RazorpayUnifiedSyncResponse:
    """Unified synchronization across payments, orders, and settlements into Sentinel."""
    try:
        return await integration_service.sync_all(
            session=session,
            req=request,
            investigation_service=investigation_service,
        )
    except Exception as e:
        logger.error("Error during unified Razorpay sync: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed unified Razorpay sync: {str(e)}")


@router.post("/razorpay/sync/payments", response_model=RazorpaySyncResponse)
async def sync_razorpay_payments(
    request: RazorpaySyncRequest = RazorpaySyncRequest(),
    session: AsyncSession = Depends(get_db_session),
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> RazorpaySyncResponse:
    """Synchronize payments from Razorpay Test/Live API into Sentinel and reconcile."""
    try:
        return await integration_service.sync_payments(
            session=session,
            req=request,
            investigation_service=investigation_service,
        )
    except Exception as e:
        logger.error("Error syncing Razorpay payments: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to sync payments: {str(e)}")


@router.post("/razorpay/sync/orders", response_model=RazorpaySyncResponse)
async def sync_razorpay_orders(
    request: RazorpaySyncRequest = RazorpaySyncRequest(),
    session: AsyncSession = Depends(get_db_session),
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> RazorpaySyncResponse:
    """Synchronize orders from Razorpay Test/Live API into Sentinel internal ledger."""
    try:
        return await integration_service.sync_orders(
            session=session,
            req=request,
            investigation_service=investigation_service,
        )
    except Exception as e:
        logger.error("Error syncing Razorpay orders: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to sync orders: {str(e)}")


@router.post("/razorpay/sync/settlements", response_model=RazorpaySyncResponse)
async def sync_razorpay_settlements(
    request: RazorpaySyncRequest = RazorpaySyncRequest(),
    session: AsyncSession = Depends(get_db_session),
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> RazorpaySyncResponse:
    """Synchronize settlements from Razorpay Test/Live API into Sentinel and reconcile."""
    try:
        return await integration_service.sync_settlements(
            session=session,
            req=request,
            investigation_service=investigation_service,
        )
    except Exception as e:
        logger.error("Error syncing Razorpay settlements: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to sync settlements: {str(e)}")


@router.post("/razorpay/webhook")
async def handle_razorpay_webhook(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(None, alias="X-Razorpay-Signature"),
    session: AsyncSession = Depends(get_db_session),
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> dict[str, Any]:
    """Ingest Razorpay webhook, verify HMAC-SHA256 signature, and incrementally reconcile."""
    raw_body = await request.body()

    # 1. Signature Verification
    if x_razorpay_signature:
        if not webhook_handler.verify_signature(raw_body, x_razorpay_signature):
            logger.warning("Invalid Razorpay webhook signature received")
            raise HTTPException(status_code=400, detail="Invalid HMAC-SHA256 webhook signature")

    # 2. Parse payload
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {str(e)}")

    # 3. Translate to canonical Transaction
    payment_data = payload.get("payload", {}).get("payment", {}).get("entity", payload)
    txn = RazorpayNormalizer.normalize_payment(payment_data)

    # 4. Reconcile incrementally
    incremental_service = IncrementalReconciliationService(session, investigation_service=investigation_service)
    result = await incremental_service.ingest_and_reconcile(txn)
    await session.commit()

    return {
        "event_received": payload.get("event", "payment.captured"),
        "transaction_id": result.transaction_id,
        "status": result.status,
        "action": result.action,
        "match_id": result.match_id,
        "matched_transaction_id": result.matched_transaction_id,
        "processing_time_ms": result.processing_time_ms,
    }
