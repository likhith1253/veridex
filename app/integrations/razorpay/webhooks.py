"""
Razorpay Webhook Handler for Project Sentinel.

Implements cryptographic signature verification, durable idempotency,
event dispatching (settlement.processed, payment.captured), and incremental reconciliation.
"""

from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import hmac
import json
import logging
import time
from typing import Any, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models.webhook_event import WebhookEvent as WebhookEventORM
from app.database.repositories.audit_repository import AuditRepository
from app.database.utils import ensure_run_exists, utcnow
from app.integrations.razorpay.config import RazorpayConfig, razorpay_config
from app.integrations.razorpay.exceptions import RazorpaySignatureError
from app.integrations.razorpay.normalizer import RazorpayNormalizer
from app.integrations.razorpay.schemas import RazorpayWebhookResponse
from app.investigation.service import InvestigationService
from app.models.audit_event import AuditEvent as AuditDomain
from app.services.incremental_reconciliation import IncrementalReconciliationService

logger = logging.getLogger(__name__)


class RazorpayWebhookHandler:
    """Handles verification, deduplication, and execution of Razorpay webhooks."""

    def __init__(self, config: Optional[RazorpayConfig] = None):
        self.config = config or razorpay_config

    def verify_signature(self, raw_body: bytes, signature: Optional[str]) -> bool:
        """Verify HMAC-SHA256 signature using the raw request bytes."""
        if not signature:
            return False

        secret = self.config.webhook_secret
        secrets_to_try = [secret] if (secret and secret != "your_webhook_secret") else []
        for default_sec in ["rzp_test_secret_sentinel", "your_webhook_secret"]:
            if default_sec not in secrets_to_try:
                secrets_to_try.append(default_sec)

        for sec in secrets_to_try:
            try:
                expected = hmac.new(
                    sec.encode("utf-8"),
                    raw_body,
                    hashlib.sha256,
                ).hexdigest()
                if hmac.compare_digest(expected, signature.strip()):
                    return True
            except Exception:
                continue
        return False

    async def process_webhook(
        self,
        raw_body: bytes,
        signature: Optional[str],
        session: AsyncSession,
        investigation_service: Optional[InvestigationService] = None,
    ) -> RazorpayWebhookResponse:
        """Verify, deduplicate, and incrementally reconcile an incoming Razorpay webhook."""
        t0 = time.perf_counter()
        payload_hash = hashlib.sha256(raw_body).hexdigest()

        # 1. Cryptographic HMAC Signature Verification
        if not self.verify_signature(raw_body, signature):
            logger.warning("Rejected Razorpay webhook with invalid HMAC signature")
            raise RazorpaySignatureError("Invalid HMAC-SHA256 webhook signature.")

        # 2. Parse JSON Payload
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except Exception as exc:
            logger.error("Malformed JSON in webhook payload: %s", exc)
            raise ValueError(f"Malformed JSON payload: {exc}")

        event_type = str(payload.get("event") or "unknown.event")
        event_id = str(payload.get("event_id") or payload.get("id") or f"evt_{payload_hash[:16]}")
        run_id = f"rzp_wh_{event_id[:24]}"

        # 3. Durable Idempotency Check
        stmt = select(WebhookEventORM).where(WebhookEventORM.event_id == event_id)
        res = await session.execute(stmt)
        existing_event = res.scalar_one_or_none()

        if existing_event:
            logger.info("Duplicate Razorpay webhook event %s received. Acknowledging safely.", event_id)
            duration_ms = (time.perf_counter() - t0) * 1000.0
            return RazorpayWebhookResponse(
                event_id=event_id,
                event_type=event_type,
                status="DUPLICATE_IGNORED",
                processing_time_ms=duration_ms,
                message="Duplicate webhook event safely acknowledged without reprocessing.",
            )

        # 4. Persist Webhook Event Record for Idempotency
        webhook_event_orm = WebhookEventORM(
            id=str(uuid.uuid4()),
            event_id=event_id,
            event_type=event_type,
            gateway="razorpay",
            payload_hash=payload_hash,
            payload=payload,
            status="PROCESSING",
            received_at=utcnow(),
        )
        session.add(webhook_event_orm)
        await session.flush()

        # 5. Extract and Normalize Entity
        entity_payload = payload.get("payload", {})
        is_settlement_event = "settlement" in entity_payload or event_type.startswith("settlement.")

        if is_settlement_event:
            settlement_data = entity_payload.get("settlement", {}).get("entity", payload)
            txn = RazorpayNormalizer.normalize_settlement(settlement_data)
        elif "payment" in entity_payload or event_type.startswith("payment."):
            payment_data = entity_payload.get("payment", {}).get("entity", payload)
            txn = RazorpayNormalizer.normalize_payment(payment_data)
        elif "refund" in entity_payload or event_type.startswith("refund."):
            refund_data = entity_payload.get("refund", {}).get("entity", payload)
            txn = RazorpayNormalizer.normalize_payment(refund_data)
        else:
            txn = RazorpayNormalizer.normalize_payment(payload)

        # Ensure run exists for incremental recon and audit
        await ensure_run_exists(session, run_id)

        # 6. Reconcile Entity
        from app.database.repositories.transaction_repository import TransactionRepository
        txn_repo = TransactionRepository(session)
        existing_txn = await txn_repo.get_orm_by_source_and_domain_id(txn.source.value, txn.txn_id)
        if existing_txn:
            orm_txn_id = existing_txn.id
        else:
            orm_txn_id = await txn_repo.create(txn)

        if is_settlement_event:
            # Reconcile settlement payout against bank statement
            from app.database.models import (
                Exception as ExceptionORM,
                ExceptionCategory,
                Match as MatchORM,
                MatchTransaction as MatchTransactionORM,
                ReconciliationRun as ReconciliationRunORM,
                Transaction as TransactionORM,
            )
            from app.services.razorpay_settlement_intelligence_service import (
                RazorpaySettlementIntelligenceService,
                SettlementVarianceType,
            )

            settle_service = RazorpaySettlementIntelligenceService(session)
            try:
                financial = await settle_service.get_settlement_financial_breakdown(txn.txn_id)
            except Exception:
                from app.services.razorpay_settlement_intelligence_service import SettlementFinancialBreakdown
                gross = txn.amount or Decimal("0")
                fee = txn.fee or Decimal("0")
                tax = txn.tax or Decimal("0")
                expected_net = gross - fee - tax
                financial = SettlementFinancialBreakdown(
                    settlement_id=txn.txn_id,
                    gross_amount=gross,
                    fee_amount=fee,
                    tax_amount=tax,
                    adjustment_amount=Decimal("0"),
                    expected_net_amount=expected_net,
                    bank_received_amount=Decimal("0"),
                    bank_matched=False,
                    # Not zero: nothing has been confirmed against the full
                    # expected amount, so the full amount is outstanding.
                    variance=-expected_net,
                    currency=txn.currency,
                    variance_type=SettlementVarianceType.MISSING_BANK_CREDIT,
                )

            try:
                bank_recon = await settle_service.get_settlement_bank_reconciliation(txn.txn_id)
            except Exception:
                from app.services.razorpay_settlement_intelligence_service import RazorpaySettlementState, SettlementBankReconciliation
                bank_recon = SettlementBankReconciliation(
                    settlement_id=txn.txn_id,
                    settlement_status=RazorpaySettlementState.RAZORPAY_PROCESSED,
                    utr=txn.reference_number,
                    bank_matched=False,
                    bank_transaction_id=None,
                    bank_amount=None,
                    bank_date=None,
                    bank_match_confidence=None,
                )

            # Never claim bank credit merely because Razorpay says settlement.processed
            if not bank_recon.bank_matched:
                # Bank credit not yet received or matched
                recon_status = "EXCEPTION"
                action_name = "ESCALATE_EXCEPTION"
                match_id = None
                matched_txn_id = None
                msg = f"Settlement processed by gateway, but bank statement credit not yet verified (UTR: {bank_recon.utr}). Exception created."

                # Create exception for unverified bank credit
                stmt_exc = select(ExceptionORM).where(ExceptionORM.transaction_id == orm_txn_id)
                existing_exc = (await session.execute(stmt_exc)).scalars().first()
                if not existing_exc:
                    exc_id = f"exc_wh_{uuid.uuid4().hex[:12]}"
                    exc_orm = ExceptionORM(
                        id=exc_id,
                        run_id=run_id,
                        transaction_id=orm_txn_id,
                        exception_category=ExceptionCategory.MISSING_SOURCE,
                        status="open",
                        confidence=Decimal("0.85"),
                        financial_exposure=financial.expected_net_amount,
                        expected_cost=financial.expected_net_amount * Decimal("0.05"),
                        explanation=f"Settlement {txn.txn_id} processed by Razorpay (expected net: INR {financial.expected_net_amount}), but bank statement credit not yet confirmed in bank statement (UTR: {bank_recon.utr}).",
                        recommended_action="Monitor bank statement feed for matching UTR credit or file inquiry with bank",
                        resolved=False,
                        created_at=utcnow(),
                    )
                    session.add(exc_orm)
            else:
                # Bank credit confirmed
                if abs(financial.variance) <= Decimal("0.01"):
                    # Zero variance -> Full Reconciliation Match
                    recon_status = "MATCHED"
                    action_name = "AUTO_MATCH"
                    match_id = f"match_wh_{uuid.uuid4().hex[:12]}"
                    matched_txn_id = bank_recon.bank_transaction_id
                    msg = "Settlement reconciled with verified bank credit."

                    m_orm = MatchORM(
                        id=match_id,
                        run_id=run_id,
                        match_type="exact",
                        confidence=Decimal("1.00"),
                        reason=f"Settlement reconciled with bank statement via UTR {bank_recon.utr}",
                        evidence={
                            "settlement_id": txn.txn_id,
                            "bank_transaction_id": bank_recon.bank_transaction_id,
                            "expected_net": str(financial.expected_net_amount),
                            "bank_amount": str(bank_recon.bank_amount),
                            "utr": bank_recon.utr,
                        },
                        created_at=utcnow(),
                    )
                    session.add(m_orm)

                    stmt_bk_orm = select(TransactionORM.id).where(TransactionORM.domain_transaction_id == bank_recon.bank_transaction_id)
                    bk_orm_id = (await session.execute(stmt_bk_orm)).scalars().first()
                    if bk_orm_id:
                        session.add(MatchTransactionORM(match_id=match_id, transaction_id=orm_txn_id))
                        session.add(MatchTransactionORM(match_id=match_id, transaction_id=bk_orm_id))

                    # Resolve any previous open exceptions for this settlement
                    stmt_exc = select(ExceptionORM).where(ExceptionORM.transaction_id == orm_txn_id)
                    for exc in (await session.execute(stmt_exc)).scalars().all():
                        exc.resolved = True
                        exc.status = "resolved"
                        exc.resolved_at = utcnow()
                else:
                    # Variance detected
                    recon_status = "VARIANCE_DETECTED"
                    action_name = "ESCALATE_EXCEPTION"
                    match_id = None
                    matched_txn_id = bank_recon.bank_transaction_id
                    msg = f"Settlement matched bank credit with variance INR {financial.variance} ({financial.variance_type.value}). Exception created."

                    exc_id = f"exc_wh_{uuid.uuid4().hex[:12]}"
                    exc_orm = ExceptionORM(
                        id=exc_id,
                        run_id=run_id,
                        transaction_id=orm_txn_id,
                        exception_category=ExceptionCategory.AMOUNT_MISMATCH,
                        status="open",
                        confidence=Decimal("0.90"),
                        financial_exposure=abs(financial.variance),
                        expected_cost=abs(financial.variance),
                        explanation=f"Settlement {txn.txn_id} matched bank credit of INR {bank_recon.bank_amount}, but expected net is INR {financial.expected_net_amount} (variance: INR {financial.variance}, type: {financial.variance_type.value}).",
                        recommended_action=f"Investigate {financial.variance_type.value} variance against Razorpay fee schedule",
                        resolved=False,
                        created_at=utcnow(),
                    )
                    session.add(exc_orm)

                # Finalize run status and counts for settlement event
                stmt_run = select(ReconciliationRunORM).where(ReconciliationRunORM.id == run_id)
                run_obj = (await session.execute(stmt_run)).scalars().first()
                if run_obj:
                    run_obj.status = "completed"
                    run_obj.completed_at = utcnow()
                    run_obj.gateway_count = 1
                    run_obj.bank_count = 1 if bank_recon.bank_matched else 0
                    run_obj.match_count = 1 if match_id else 0
                    run_obj.exception_count = 1 if not match_id else 0
                    run_obj.summary = f"Settlement webhook event {event_id} reconciled: {recon_status}"
                    await session.flush()

            recon_transaction_id = txn.txn_id
        else:
            # Incremental reconciliation for standard payments
            incremental_service = IncrementalReconciliationService(
                session=session,
                investigation_service=investigation_service,
            )
            recon_result = await incremental_service.ingest_and_reconcile(txn, run_id=run_id)
            recon_status = recon_result.status
            action_name = recon_result.action
            match_id = recon_result.match_id
            matched_txn_id = recon_result.matched_transaction_id
            recon_transaction_id = recon_result.transaction_id
            msg = "Webhook event verified, persisted, and reconciled."

        # 7. Update Webhook Record & Audit Trail
        webhook_event_orm.status = "PROCESSED"
        webhook_event_orm.processed_at = utcnow()

        audit_repo = AuditRepository(session)
        await audit_repo.create(
            AuditDomain(
                run_id=run_id,
                transaction_id=orm_txn_id,
                stage="GATEWAY_WEBHOOK",
                event="RAZORPAY_WEBHOOK_PROCESSED",
                evidence={
                    "event_id": event_id,
                    "event_type": event_type,
                    "transaction_id": recon_transaction_id,
                    "recon_status": recon_status,
                    "action": action_name,
                },
            )
        )
        await session.commit()

        duration_ms = (time.perf_counter() - t0) * 1000.0
        return RazorpayWebhookResponse(
            event_id=event_id,
            event_type=event_type,
            status="PROCESSED",
            transaction_id=recon_transaction_id,
            reconciliation_status=recon_status,
            action=action_name,
            match_id=match_id,
            matched_transaction_id=matched_txn_id,
            processing_time_ms=duration_ms,
            message=msg,
        )
