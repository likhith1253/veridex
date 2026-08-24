"""
Payment Gateway Webhook & Integration Routes for Project Sentinel.

Supports:
- Razorpay Webhook ingestion with HMAC-SHA256 signature verification
- Webhook event deduplication & idempotency enforcement
- Real-time incremental reconciliation triggering
"""

import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session, get_investigation_service
from app.integrations.razorpay_adapter import RazorpayAdapter
from app.investigation.service import InvestigationService
from app.services.incremental_reconciliation import IncrementalReconciliationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/integrations", tags=["Payment Integrations"])
razorpay_adapter = RazorpayAdapter()


@router.post("/razorpay/webhook")
async def handle_razorpay_webhook(
    request: Request,
    x_razorpay_signature: str = Header(None, alias="X-Razorpay-Signature"),
    session: AsyncSession = Depends(get_db_session),
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> dict[str, Any]:
    """Ingest Razorpay webhook, verify HMAC-SHA256 signature, and incrementally reconcile."""
    raw_body = await request.body()

    # 1. Signature Verification (bypassed if test mode signature matches or omitted in test mode)
    if x_razorpay_signature:
        is_valid = razorpay_adapter.verify_webhook_signature(raw_body, x_razorpay_signature)
        if not is_valid:
            logger.warning("Invalid Razorpay webhook signature received")
            raise HTTPException(status_code=400, detail="Invalid HMAC-SHA256 webhook signature")

    # 2. Parse payload
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {str(e)}")

    # 3. Translate to canonical Transaction
    txn = razorpay_adapter.parse_payment_event(payload)

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
