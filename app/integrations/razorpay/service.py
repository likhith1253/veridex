"""
Razorpay Integration Orchestration Service for Project Sentinel.

Coordinates payment & settlement synchronization, fallback simulation,
and status monitoring.
"""

from datetime import datetime, timezone
from decimal import Decimal
import logging
import time
from typing import Any, Optional
import uuid

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.audit import AuditEvent as AuditEventORM
from app.database.models.webhook_event import WebhookEvent as WebhookEventORM
from app.database.repositories.audit_repository import AuditRepository
from app.database.utils import ensure_run_exists, utcnow
from app.integrations.razorpay.client import RazorpayClient
from app.integrations.razorpay.config import RazorpayConfig, razorpay_config
from app.integrations.razorpay.exceptions import RazorpayConfigError
from app.integrations.razorpay.normalizer import RazorpayNormalizer
from app.integrations.razorpay.schemas import (
    RazorpayStatusResponse,
    RazorpaySyncRequest,
    RazorpaySyncResponse,
)
from app.investigation.service import InvestigationService
from app.models.audit_event import AuditEvent as AuditDomain
from app.models.transaction import Transaction, TransactionSource, TransactionStatus
from app.services.incremental_reconciliation import IncrementalReconciliationService

logger = logging.getLogger(__name__)


class RazorpayIntegrationService:
    """Orchestrates synchronization between Razorpay APIs and Sentinel's Reconciliation Engine."""

    def __init__(
        self,
        config: Optional[RazorpayConfig] = None,
        client: Optional[RazorpayClient] = None,
    ):
        self.config = config or razorpay_config
        self.client = client or RazorpayClient(config=self.config)

    async def get_status(self, session: Optional[AsyncSession] = None) -> RazorpayStatusResponse:
        """Query connectivity status and safe configuration metadata."""
        is_reachable = False
        if self.config.is_configured:
            is_reachable = await self.client.check_connectivity()

        last_sync_at = None
        last_webhook_at = None

        if session:
            try:
                wh_stmt = select(func.max(WebhookEventORM.received_at))
                wh_res = await session.execute(wh_stmt)
                last_webhook_at = wh_res.scalar_one_or_none()

                sync_stmt = (
                    select(func.max(AuditEventORM.timestamp))
                    .where(AuditEventORM.event_type.like("RAZORPAY_SYNC_%"))
                )
                sync_res = await session.execute(sync_stmt)
                last_sync_at = sync_res.scalar_one_or_none()
            except Exception as e:
                logger.warning("Error fetching last sync/webhook timestamps: %s", e)

        return RazorpayStatusResponse(
            configured=self.config.is_configured,
            mode=self.config.mode,
            key_id_prefix=self.config.key_id_prefix,
            webhook_configured=self.config.is_webhook_configured,
            api_reachable=is_reachable,
            last_sync_at=last_sync_at,
            last_webhook_at=last_webhook_at,
            last_error=None if (self.config.is_configured and is_reachable) else ("Unconfigured" if not self.config.is_configured else "Unreachable API"),
        )

    def _generate_synthetic_payments(self, count: int) -> list[dict[str, Any]]:
        """Generate realistic synthetic Razorpay payment payloads for fallback simulation."""
        items = []
        now_ts = int(datetime.now(timezone.utc).timestamp())
        for i in range(1, count + 1):
            amount_paise = 250000 + (i * 12500)
            fee_paise = int(amount_paise * 0.02)
            tax_paise = int(fee_paise * 0.18)
            items.append({
                "id": f"pay_syn_{i:04d}_{now_ts}",
                "entity": "payment",
                "amount": amount_paise,
                "currency": "INR",
                "status": "captured",
                "order_id": f"order_syn_{i:04d}",
                "method": "upi" if i % 2 == 0 else "card",
                "fee": fee_paise,
                "tax": tax_paise,
                "created_at": now_ts - (i * 300),
                "acquirer_data": {
                    "rrn": f"RRN{now_ts}{i:04d}",
                    "utr": f"UTR{now_ts}{i:04d}",
                },
                "email": f"customer_{i}@example.com",
            })
        return items

    def _generate_synthetic_settlements(self, count: int) -> list[dict[str, Any]]:
        """Generate realistic synthetic Razorpay settlement payloads for fallback simulation."""
        items = []
        now_ts = int(datetime.now(timezone.utc).timestamp())
        for i in range(1, count + 1):
            amount_paise = 5000000 + (i * 500000)
            fee_paise = int(amount_paise * 0.02)
            tax_paise = int(fee_paise * 0.18)
            items.append({
                "id": f"setl_syn_{i:04d}_{now_ts}",
                "entity": "settlement",
                "amount": amount_paise,
                "currency": "INR",
                "status": "processed",
                "fees": fee_paise,
                "tax": tax_paise,
                "utr": f"SBIN{now_ts}{i:04d}",
                "created_at": now_ts - (i * 86400),
            })
        return items

    async def sync_payments(
        self,
        session: AsyncSession,
        req: RazorpaySyncRequest,
        investigation_service: Optional[InvestigationService] = None,
    ) -> RazorpaySyncResponse:
        """Fetch payments from Razorpay API (or fallback simulator), normalize, and reconcile."""
        t0 = time.perf_counter()
        run_id = f"rzp_sync_pay_{int(time.time())}"
        await ensure_run_exists(session, run_id)
        audit_repo = AuditRepository(session)

        await audit_repo.create(
            AuditDomain(
                run_id=run_id,
                stage="GATEWAY_SYNC",
                event="RAZORPAY_SYNC_STARTED",
                evidence={"limit": req.limit},
            )
        )

        source = f"razorpay_{self.config.mode}"
        warning = None
        raw_items: list[dict[str, Any]] = []

        if self.config.is_configured:
            try:
                res = await self.client.fetch_payments(
                    count=req.limit,
                    skip=req.skip,
                    from_ts=req.from_timestamp,
                    to_ts=req.to_timestamp,
                )
                raw_items = res.get("items", [])
                if not raw_items and "entity" in res and res["entity"] == "payment":
                    raw_items = [res]
                elif not raw_items and req.use_fallback_if_unconfigured and self.config.mode == "test":
                    raw_items = self._generate_synthetic_payments(req.limit)
                    source = "synthetic_fallback"
                    warning = "Razorpay Test account returned 0 live payments; generated simulation batch."
            except Exception as exc:
                logger.warning("Razorpay API live sync failed: %s", exc)
                if not req.use_fallback_if_unconfigured:
                    raise
                warning = f"Live Razorpay API call failed ({exc}); falling back to controlled synthetic simulation."
                source = "synthetic_fallback"
                raw_items = self._generate_synthetic_payments(req.limit)
        else:
            if not req.use_fallback_if_unconfigured:
                raise RazorpayConfigError("Razorpay credentials are not configured and fallback is disabled.")
            source = "synthetic_fallback"
            warning = "Razorpay credentials not configured. Executing with synthetic simulation data."
            raw_items = self._generate_synthetic_payments(req.limit)

        # Normalize items
        normalized_txns: list[Transaction] = []
        rejected = 0
        for item in raw_items:
            try:
                txn = RazorpayNormalizer.normalize_payment(item)
                normalized_txns.append(txn)
            except Exception as e:
                logger.warning("Failed to normalize payment item %s: %s", item.get("id"), e)
                rejected += 1

        # Reconcile if requested
        recon_summary = None
        if req.auto_reconcile and normalized_txns:
            incremental_service = IncrementalReconciliationService(
                session=session,
                investigation_service=investigation_service,
            )
            matched_count = 0
            exception_count = 0
            for txn in normalized_txns:
                res = await incremental_service.ingest_and_reconcile(txn, run_id=run_id)
                if "MATCHED" in res.status:
                    matched_count += 1
                elif "EXCEPTION" in res.status:
                    exception_count += 1

            recon_summary = {
                "total_processed": len(normalized_txns),
                "matched_count": matched_count,
                "exception_count": exception_count,
            }

        await audit_repo.create(
            AuditDomain(
                run_id=run_id,
                stage="GATEWAY_SYNC",
                event="RAZORPAY_SYNC_COMPLETED",
                evidence={
                    "source": source,
                    "records_normalized": len(normalized_txns),
                    "records_rejected": rejected,
                    "recon_summary": recon_summary,
                },
            )
        )

        duration_ms = (time.perf_counter() - t0) * 1000.0
        return RazorpaySyncResponse(
            source=source,
            mode=self.config.mode,
            entity_type="payments",
            records_fetched=len(raw_items),
            records_normalized=len(normalized_txns),
            records_rejected=rejected,
            run_id=run_id,
            duration_ms=duration_ms,
            reconciliation_summary=recon_summary,
            warning=warning,
        )

    async def sync_settlements(
        self,
        session: AsyncSession,
        req: RazorpaySyncRequest,
        investigation_service: Optional[InvestigationService] = None,
    ) -> RazorpaySyncResponse:
        """Fetch settlements from Razorpay API (or fallback simulator), normalize, and reconcile."""
        t0 = time.perf_counter()
        run_id = f"rzp_sync_setl_{int(time.time())}"
        await ensure_run_exists(session, run_id)
        audit_repo = AuditRepository(session)

        await audit_repo.create(
            AuditDomain(
                run_id=run_id,
                stage="GATEWAY_SYNC",
                event="RAZORPAY_SYNC_STARTED",
                evidence={"limit": req.limit},
            )
        )

        source = f"razorpay_{self.config.mode}"
        warning = None
        raw_items: list[dict[str, Any]] = []

        if self.config.is_configured:
            try:
                res = await self.client.fetch_settlements(
                    count=req.limit,
                    skip=req.skip,
                    from_ts=req.from_timestamp,
                    to_ts=req.to_timestamp,
                )
                raw_items = res.get("items", [])
                if not raw_items and "entity" in res and res["entity"] == "settlement":
                    raw_items = [res]
                elif not raw_items and req.use_fallback_if_unconfigured and self.config.mode == "test":
                    raw_items = self._generate_synthetic_settlements(req.limit)
                    source = "synthetic_fallback"
                    warning = "Razorpay Test account returned 0 live settlements; generated simulation batch."
            except Exception as exc:
                logger.warning("Razorpay API live settlements sync failed: %s", exc)
                if not req.use_fallback_if_unconfigured:
                    raise
                warning = f"Live Razorpay API settlements call failed ({exc}); falling back to synthetic simulation."
                source = "synthetic_fallback"
                raw_items = self._generate_synthetic_settlements(req.limit)
        else:
            if not req.use_fallback_if_unconfigured:
                raise RazorpayConfigError("Razorpay credentials are not configured and fallback is disabled.")
            source = "synthetic_fallback"
            warning = "Razorpay credentials not configured. Executing with synthetic simulation data."
            raw_items = self._generate_synthetic_settlements(req.limit)

        normalized_txns: list[Transaction] = []
        rejected = 0
        for item in raw_items:
            try:
                txn = RazorpayNormalizer.normalize_settlement(item)
                normalized_txns.append(txn)
            except Exception as e:
                logger.warning("Failed to normalize settlement item %s: %s", item.get("id"), e)
                rejected += 1

        recon_summary = None
        if req.auto_reconcile and normalized_txns:
            incremental_service = IncrementalReconciliationService(
                session=session,
                investigation_service=investigation_service,
            )
            matched_count = 0
            exception_count = 0
            for txn in normalized_txns:
                res = await incremental_service.ingest_and_reconcile(txn, run_id=run_id)
                if "MATCHED" in res.status:
                    matched_count += 1
                elif "EXCEPTION" in res.status:
                    exception_count += 1

            recon_summary = {
                "total_processed": len(normalized_txns),
                "matched_count": matched_count,
                "exception_count": exception_count,
            }

        await audit_repo.create(
            AuditDomain(
                run_id=run_id,
                stage="GATEWAY_SYNC",
                event="RAZORPAY_SYNC_COMPLETED",
                evidence={
                    "source": source,
                    "records_normalized": len(normalized_txns),
                    "records_rejected": rejected,
                    "recon_summary": recon_summary,
                },
            )
        )

        duration_ms = (time.perf_counter() - t0) * 1000.0
        return RazorpaySyncResponse(
            source=source,
            mode=self.config.mode,
            entity_type="settlements",
            records_fetched=len(raw_items),
            records_normalized=len(normalized_txns),
            records_rejected=rejected,
            run_id=run_id,
            duration_ms=duration_ms,
            reconciliation_summary=recon_summary,
            warning=warning,
        )
