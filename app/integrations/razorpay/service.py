"""
Razorpay Integration Orchestration Service for Project Sentinel.

Coordinates payment, order & settlement synchronization, fallback simulation,
idempotent database persistence, and status monitoring.
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
from app.database.repositories.transaction_repository import TransactionRepository
from app.database.utils import ensure_run_exists, utcnow
from app.integrations.razorpay.client import RazorpayClient
from app.integrations.razorpay.config import RazorpayConfig, razorpay_config
from app.integrations.razorpay.exceptions import RazorpayConfigError
from app.integrations.razorpay.normalizer import RazorpayNormalizer
from app.integrations.razorpay.schemas import (
    RazorpayStatusResponse,
    RazorpaySyncRequest,
    RazorpaySyncResponse,
    RazorpayUnifiedSyncResponse,
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

    def _generate_synthetic_orders(self, count: int) -> list[dict[str, Any]]:
        """Generate realistic synthetic Razorpay order payloads for fallback simulation."""
        items = []
        now_ts = int(datetime.now(timezone.utc).timestamp())
        for i in range(1, count + 1):
            amount_paise = 250000 + (i * 12500)
            items.append({
                "id": f"order_syn_{i:04d}",
                "entity": "order",
                "amount": amount_paise,
                "currency": "INR",
                "status": "paid",
                "receipt": f"rcpt_syn_{i:04d}",
                "attempts": 1,
                "created_at": now_ts - (i * 300) - 30,
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

    async def _ingest_transactions_idempotent(
        self,
        session: AsyncSession,
        transactions: list[Transaction],
        run_id: str,
        auto_reconcile: bool,
        investigation_service: Optional[InvestigationService] = None,
    ) -> tuple[int, int, int, Optional[dict[str, Any]]]:
        """Idempotently persist transactions and optionally trigger incremental reconciliation.
        
        Returns: (inserted_count, updated_count, skipped_count, recon_summary)
        """
        txn_repo = TransactionRepository(session)
        inserted_count = 0
        skipped_count = 0
        matched_count = 0
        exception_count = 0

        incremental_service = None
        if auto_reconcile:
            incremental_service = IncrementalReconciliationService(
                session=session,
                investigation_service=investigation_service,
            )

        for txn in transactions:
            existing_id = await txn_repo.get_orm_by_source_and_domain_id(txn.source.value, txn.txn_id)
            if existing_id:
                skipped_count += 1
                continue

            if incremental_service:
                res = await incremental_service.ingest_and_reconcile(txn, run_id=run_id)
                inserted_count += 1
                if "MATCHED" in res.status:
                    matched_count += 1
                elif "EXCEPTION" in res.status:
                    exception_count += 1
            else:
                await txn_repo.create(txn)
                inserted_count += 1

        recon_summary = None
        if auto_reconcile and transactions:
            recon_summary = {
                "total_processed": len(transactions),
                "inserted_count": inserted_count,
                "skipped_count": skipped_count,
                "matched_count": matched_count,
                "exception_count": exception_count,
            }

        return (inserted_count, 0, skipped_count, recon_summary)

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
                evidence={"limit": req.limit, "entity_type": "payments"},
            )
        )

        source = f"razorpay_{self.config.mode}"
        warning = None
        errors: list[str] = []
        raw_items: list[dict[str, Any]] = []

        if self.config.is_configured:
            try:
                raw_items = await self.client.fetch_paginated_entities(
                    endpoint="/payments",
                    limit=req.limit,
                    from_ts=req.from_timestamp,
                    to_ts=req.to_timestamp,
                )
                if not raw_items and req.use_fallback_if_unconfigured and self.config.mode == "test":
                    raw_items = self._generate_synthetic_payments(req.limit)
                    source = "synthetic_fallback"
                    warning = "Razorpay Test account returned 0 live payments; generated simulation batch."
            except Exception as exc:
                logger.warning("Razorpay API live sync failed: %s", exc)
                errors.append(str(exc))
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

        normalized_txns: list[Transaction] = []
        rejected = 0
        for item in raw_items:
            try:
                txn = RazorpayNormalizer.normalize_payment(item)
                normalized_txns.append(txn)
            except Exception as e:
                logger.warning("Failed to normalize payment item %s: %s", item.get("id"), e)
                rejected += 1

        inserted, updated, skipped, recon_summary = await self._ingest_transactions_idempotent(
            session=session,
            transactions=normalized_txns,
            run_id=run_id,
            auto_reconcile=req.auto_reconcile,
            investigation_service=investigation_service,
        )

        await audit_repo.create(
            AuditDomain(
                run_id=run_id,
                stage="GATEWAY_SYNC",
                event="RAZORPAY_SYNC_COMPLETED",
                evidence={
                    "source": source,
                    "entity_type": "payments",
                    "records_fetched": len(raw_items),
                    "records_normalized": len(normalized_txns),
                    "records_inserted": inserted,
                    "records_skipped": skipped,
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
            records_inserted=inserted,
            records_updated=updated,
            records_skipped=skipped,
            records_rejected=rejected,
            run_id=run_id,
            duration_ms=duration_ms,
            reconciliation_summary=recon_summary,
            warning=warning,
            errors=errors,
        )

    async def sync_orders(
        self,
        session: AsyncSession,
        req: RazorpaySyncRequest,
        investigation_service: Optional[InvestigationService] = None,
    ) -> RazorpaySyncResponse:
        """Fetch orders from Razorpay API (or fallback simulator), normalize into ledger source, and reconcile."""
        t0 = time.perf_counter()
        run_id = f"rzp_sync_ord_{int(time.time())}"
        await ensure_run_exists(session, run_id)
        audit_repo = AuditRepository(session)

        await audit_repo.create(
            AuditDomain(
                run_id=run_id,
                stage="GATEWAY_SYNC",
                event="RAZORPAY_SYNC_STARTED",
                evidence={"limit": req.limit, "entity_type": "orders"},
            )
        )

        source = f"razorpay_{self.config.mode}"
        warning = None
        errors: list[str] = []
        raw_items: list[dict[str, Any]] = []

        if self.config.is_configured:
            try:
                raw_items = await self.client.fetch_paginated_entities(
                    endpoint="/orders",
                    limit=req.limit,
                    from_ts=req.from_timestamp,
                    to_ts=req.to_timestamp,
                )
                if not raw_items and req.use_fallback_if_unconfigured and self.config.mode == "test":
                    raw_items = self._generate_synthetic_orders(req.limit)
                    source = "synthetic_fallback"
                    warning = "Razorpay Test account returned 0 live orders; generated simulation batch."
            except Exception as exc:
                logger.warning("Razorpay API live orders sync failed: %s", exc)
                errors.append(str(exc))
                if not req.use_fallback_if_unconfigured:
                    raise
                warning = f"Live Razorpay API call failed ({exc}); falling back to controlled synthetic simulation."
                source = "synthetic_fallback"
                raw_items = self._generate_synthetic_orders(req.limit)
        else:
            if not req.use_fallback_if_unconfigured:
                raise RazorpayConfigError("Razorpay credentials are not configured and fallback is disabled.")
            source = "synthetic_fallback"
            warning = "Razorpay credentials not configured. Executing with synthetic simulation data."
            raw_items = self._generate_synthetic_orders(req.limit)

        normalized_txns: list[Transaction] = []
        rejected = 0
        for item in raw_items:
            try:
                txn = RazorpayNormalizer.normalize_order(item)
                normalized_txns.append(txn)
            except Exception as e:
                logger.warning("Failed to normalize order item %s: %s", item.get("id"), e)
                rejected += 1

        inserted, updated, skipped, recon_summary = await self._ingest_transactions_idempotent(
            session=session,
            transactions=normalized_txns,
            run_id=run_id,
            auto_reconcile=req.auto_reconcile,
            investigation_service=investigation_service,
        )

        await audit_repo.create(
            AuditDomain(
                run_id=run_id,
                stage="GATEWAY_SYNC",
                event="RAZORPAY_SYNC_COMPLETED",
                evidence={
                    "source": source,
                    "entity_type": "orders",
                    "records_fetched": len(raw_items),
                    "records_normalized": len(normalized_txns),
                    "records_inserted": inserted,
                    "records_skipped": skipped,
                    "records_rejected": rejected,
                    "recon_summary": recon_summary,
                },
            )
        )

        duration_ms = (time.perf_counter() - t0) * 1000.0
        return RazorpaySyncResponse(
            source=source,
            mode=self.config.mode,
            entity_type="orders",
            records_fetched=len(raw_items),
            records_normalized=len(normalized_txns),
            records_inserted=inserted,
            records_updated=updated,
            records_skipped=skipped,
            records_rejected=rejected,
            run_id=run_id,
            duration_ms=duration_ms,
            reconciliation_summary=recon_summary,
            warning=warning,
            errors=errors,
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
                evidence={"limit": req.limit, "entity_type": "settlements"},
            )
        )

        source = f"razorpay_{self.config.mode}"
        warning = None
        errors: list[str] = []
        raw_items: list[dict[str, Any]] = []

        if self.config.is_configured:
            try:
                raw_items = await self.client.fetch_paginated_entities(
                    endpoint="/settlements",
                    limit=req.limit,
                    from_ts=req.from_timestamp,
                    to_ts=req.to_timestamp,
                )
                if not raw_items and req.use_fallback_if_unconfigured and self.config.mode == "test":
                    raw_items = self._generate_synthetic_settlements(req.limit)
                    source = "synthetic_fallback"
                    warning = "Razorpay Test account returned 0 live settlements; generated simulation batch."
            except Exception as exc:
                logger.warning("Razorpay API live settlements sync failed: %s", exc)
                errors.append(str(exc))
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

        inserted, updated, skipped, recon_summary = await self._ingest_transactions_idempotent(
            session=session,
            transactions=normalized_txns,
            run_id=run_id,
            auto_reconcile=req.auto_reconcile,
            investigation_service=investigation_service,
        )

        await audit_repo.create(
            AuditDomain(
                run_id=run_id,
                stage="GATEWAY_SYNC",
                event="RAZORPAY_SYNC_COMPLETED",
                evidence={
                    "source": source,
                    "entity_type": "settlements",
                    "records_fetched": len(raw_items),
                    "records_normalized": len(normalized_txns),
                    "records_inserted": inserted,
                    "records_skipped": skipped,
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
            records_inserted=inserted,
            records_updated=updated,
            records_skipped=skipped,
            records_rejected=rejected,
            run_id=run_id,
            duration_ms=duration_ms,
            reconciliation_summary=recon_summary,
            warning=warning,
            errors=errors,
        )

    async def sync_all(
        self,
        session: AsyncSession,
        req: RazorpaySyncRequest,
        investigation_service: Optional[InvestigationService] = None,
    ) -> RazorpayUnifiedSyncResponse:
        """Unified synchronization across payments, orders, and settlements in a single run."""
        t0 = time.perf_counter()
        run_id = f"rzp_sync_all_{int(time.time())}"
        await ensure_run_exists(session, run_id)

        pay_res = await self.sync_payments(session=session, req=req, investigation_service=investigation_service)
        ord_res = await self.sync_orders(session=session, req=req, investigation_service=investigation_service)
        setl_res = await self.sync_settlements(session=session, req=req, investigation_service=investigation_service)

        total_fetched = pay_res.records_fetched + ord_res.records_fetched + setl_res.records_fetched
        total_normalized = pay_res.records_normalized + ord_res.records_normalized + setl_res.records_normalized
        total_inserted = pay_res.records_inserted + ord_res.records_inserted + setl_res.records_inserted
        total_skipped = pay_res.records_skipped + ord_res.records_skipped + setl_res.records_skipped
        total_rejected = pay_res.records_rejected + ord_res.records_rejected + setl_res.records_rejected
        combined_errors = pay_res.errors + ord_res.errors + setl_res.errors

        total_duration_ms = (time.perf_counter() - t0) * 1000.0
        return RazorpayUnifiedSyncResponse(
            run_id=run_id,
            source=pay_res.source,
            mode=self.config.mode,
            total_records_fetched=total_fetched,
            total_records_normalized=total_normalized,
            total_records_inserted=total_inserted,
            total_records_skipped=total_skipped,
            total_records_rejected=total_rejected,
            payments=pay_res,
            orders=ord_res,
            settlements=setl_res,
            total_duration_ms=total_duration_ms,
            errors=combined_errors,
        )
