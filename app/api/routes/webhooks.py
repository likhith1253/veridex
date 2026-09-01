"""
Public Webhook Endpoints for Payment Gateways.

These endpoints do NOT require Sentinel API keys since they receive external callbacks.
Security is enforced cryptographically via HMAC-SHA256 signature verification.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session, get_investigation_service
from app.integrations.razorpay import (
    RazorpaySignatureError,
    RazorpayWebhookHandler,
    RazorpayWebhookResponse,
)
from app.investigation.service import InvestigationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["Webhooks"])
webhook_handler = RazorpayWebhookHandler()


@router.post("/razorpay", response_model=RazorpayWebhookResponse)
async def razorpay_webhook_endpoint(
    request: Request,
    x_razorpay_signature: Optional[str] = Header(None, alias="X-Razorpay-Signature"),
    session: AsyncSession = Depends(get_db_session),
    investigation_service: InvestigationService = Depends(get_investigation_service),
) -> RazorpayWebhookResponse:
    """Primary webhook receiver for Razorpay events (settlement.processed, payment.captured)."""
    raw_body = await request.body()
    try:
        return await webhook_handler.process_webhook(
            raw_body=raw_body,
            signature=x_razorpay_signature,
            session=session,
            investigation_service=investigation_service,
        )
    except RazorpaySignatureError as e:
        logger.warning("Rejected webhook with invalid signature: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        logger.warning("Rejected malformed webhook payload: %s", e)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Unhandled webhook processing error: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Webhook processing error: {str(e)}")
