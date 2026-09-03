import logging
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import HTTPException, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.investigation_dossier import (
    InvestigationDossier,
    RelatedIDs,
    RootCauseCandidate,
)

InvestigationDossierResponse = InvestigationDossier

from app.database.mappers.transaction_mapper import orm_to_domain
from app.database.models import (
    Exception as ExceptionORM,
    ExceptionTransaction as ExceptionTransactionORM,
    Investigation as InvestigationORM,
    Match as MatchORM,
    MatchTransaction as MatchTransactionORM,
    Transaction as TransactionORM,
    TransactionSource,
)
from app.database.repositories.audit_repository import AuditRepository
from app.database.repositories.investigation_repository import InvestigationRepository
from app.graph.investigation_graph import InvestigationGraphRunner
from app.graph.state import InvestigationState
from app.models.audit_event import AuditEvent
from app.models.decision_result import DecisionResult
from app.models.investigation_result import InvestigationConclusion
from app.models.transaction import Transaction

logger = logging.getLogger(__name__)


class InvestigationService:
    """Service orchestrating the investigation workflow and persistence.

    Acts as the boundary between reconciliation exceptions and the LangGraph
    investigation engine, managing context translation, graph execution,
    persistence in PostgreSQL, and audit trail generation.
    """

    def __init__(
        self,
        session: AsyncSession,
        investigation_repo: InvestigationRepository,
        audit_repo: AuditRepository,
        graph_runner: Optional[InvestigationGraphRunner] = None,
    ):
        """Initialize investigation service with dependencies.

        Args:
            session: Database session for transactional coordination.
            investigation_repo: Repository for persisting investigation conclusions.
            audit_repo: Repository for logging audit events.
            graph_runner: Optional compiled LangGraph workflow runner.
        """
        self.session = session
        self.investigation_repo = investigation_repo
        self.audit_repo = audit_repo
        self.graph_runner = graph_runner or InvestigationGraphRunner()

    async def investigate(
        self,
        exception_id: str,
        run_id: str,
        transactions: list[Transaction],
        decision: Optional[DecisionResult] = None,
        investigation_id: Optional[str] = None,
    ) -> InvestigationConclusion:
        """Run an investigation for an exception, persist the conclusion, and write audit events.

        Args:
            exception_id: Identifier of the exception being investigated.
            run_id: Reconciliation run identifier.
            transactions: List of canonical transactions involved in the exception.
            decision: Optional preliminary decision result from reconciliation policy.
            investigation_id: Optional unique idempotency key (generated if omitted).

        Returns:
            InvestigationConclusion containing the structured investigation result.
        """
        inv_id = investigation_id or f"inv_{uuid.uuid4().hex[:12]}"

        # 1. Build initial serializable graph state
        initial_state = InvestigationState(
            investigation_id=inv_id,
            exception_id=exception_id,
            run_id=run_id,
            decision=decision.model_dump() if decision else None,
            transactions=[t.model_dump() for t in transactions],
        )

        logger.info(
            f"Starting investigation {inv_id} for exception {exception_id} (run {run_id}) "
            f"with {len(transactions)} transactions."
        )

        # 2. Execute the LangGraph workflow
        conclusion = await self.graph_runner.run(initial_state)

        # 3. Persist conclusion via InvestigationRepository
        await self.investigation_repo.create(conclusion)

        # 4. Record audit event via AuditRepository
        audit_event = AuditEvent(
            run_id=run_id,
            transaction_id=None,
            stage="investigation",
            event="investigation_completed",
            evidence={
                "investigation_id": conclusion.investigation_id,
                "exception_id": conclusion.exception_id,
                "transaction_ids": [t.txn_id for t in transactions],
                "method": conclusion.method.value,
                "classification": conclusion.classification.value,
                "confidence": str(conclusion.confidence),
                "financial_exposure": str(conclusion.financial_exposure),
                "expected_cost": str(conclusion.expected_cost),
                "recommended_action": conclusion.recommended_action,
                "requires_human_review": conclusion.requires_human_review,
                "llm_invoked": conclusion.llm_invoked,
            },
            decision={
                "root_cause": conclusion.root_cause,
                "recommended_action": conclusion.recommended_action,
                "classification": conclusion.classification.value,
            },
        )
        await self.audit_repo.create(audit_event)

        logger.info(
            f"Investigation {inv_id} completed successfully: "
            f"method={conclusion.method.value}, classification={conclusion.classification.value}"
        )

        return conclusion

    async def get_investigation(self, investigation_id: str) -> Optional[InvestigationConclusion]:
        """Retrieve an investigation conclusion by its idempotency ID."""
        return await self.investigation_repo.get_by_investigation_id(investigation_id)

    async def get_by_exception(self, exception_id: str) -> list[InvestigationConclusion]:
        """Retrieve all investigation conclusions for a specific exception."""
        return await self.investigation_repo.get_by_exception_id(exception_id)

    async def get_by_exceptions(self, exception_ids: list[str]) -> list[InvestigationConclusion]:
        """Retrieve all investigation conclusions for a list of exceptions in a single query."""
        return await self.investigation_repo.get_by_exception_ids(exception_ids)

    async def get_by_run(self, run_id: str) -> list[InvestigationConclusion]:
        """Retrieve all investigation conclusions for a reconciliation run."""
        return await self.investigation_repo.get_by_run_id(run_id)

    async def build_investigation_dossier(self, entity_id: str) -> InvestigationDossierResponse:
        """Build a comprehensive AI investigation and evidence dossier for an exception, settlement, or transaction."""
        entity_id = entity_id.strip()
        now = datetime.now(timezone.utc)

        # -------------------------------------------------------------
        # 1. Direct Investigation lookup (by investigation_id)
        # -------------------------------------------------------------
        inv_stmt = select(InvestigationORM).where(InvestigationORM.investigation_id == entity_id)
        inv = (await self.session.execute(inv_stmt)).scalar_one_or_none()
        if inv:
            exc_stmt = select(ExceptionORM).where(ExceptionORM.id == inv.exception_id)
            exc = (await self.session.execute(exc_stmt)).scalar_one_or_none()

            tx_stmt = (
                select(TransactionORM)
                .join(ExceptionTransactionORM, ExceptionTransactionORM.transaction_id == TransactionORM.id)
                .where(ExceptionTransactionORM.exception_id == inv.exception_id)
            )
            txns = list((await self.session.execute(tx_stmt)).scalars().all())
            if exc and exc.transaction_id and not any(t.id == exc.transaction_id for t in txns):
                pt = (await self.session.execute(select(TransactionORM).where(TransactionORM.id == exc.transaction_id))).scalar_one_or_none()
                if pt:
                    txns.append(pt)

            rel_ids = RelatedIDs(
                transaction_ids=[t.domain_transaction_id for t in txns],
                order_id=next((t.order_id for t in txns if t.order_id), None),
                settlement_id=next((t.domain_transaction_id for t in txns if t.meta_data and t.meta_data.get("type") == "settlement"), None),
                reference_number=next((t.reference_number for t in txns if t.reference_number), None),
            )

            is_insufficient = len(txns) == 0
            root_candidates = [
                RootCauseCandidate(
                    cause=inv.root_cause,
                    confidence=inv.confidence,
                    evidence=f"Investigation {inv.investigation_id} classified as '{inv.classification}' via {inv.method} with confidence {inv.confidence}.",
                )
            ]
            recon_evidence = {
                "investigation_id": inv.investigation_id,
                "exception_id": inv.exception_id,
                "classification": inv.classification,
                "historical_cases_used": inv.historical_cases_used,
                "evidence_payload": inv.evidence,
                "transactions": [
                    {
                        "txn_id": t.domain_transaction_id,
                        "amount": str(t.amount),
                        "source": t.source.value if hasattr(t.source, "value") else str(t.source),
                        "status": t.status.value if hasattr(t.status, "value") else str(t.status),
                        "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                    }
                    for t in txns
                ],
            }

            return InvestigationDossierResponse(
                investigation_id=inv.investigation_id,
                entity_id=entity_id,
                entity_type="investigation",
                status=inv.status,
                exception_status=exc.status if exc else inv.status,
                financial_exposure=inv.financial_exposure,
                variance=inv.financial_exposure,
                variance_type="INVESTIGATION_CONCLUSION",
                related_ids=rel_ids,
                reconciliation_evidence=recon_evidence,
                root_cause_candidates=root_candidates,
                recommended_action=inv.recommended_action,
                requires_human_review=inv.requires_human_review,
                insufficient_evidence=is_insufficient,
                evidence_summary=f"Investigation conclusion confirmed for exception {inv.exception_id}: {inv.root_cause}.",
                method=inv.method,
                llm_invoked=inv.llm_invoked,
                created_at=inv.created_at,
            )

        # -------------------------------------------------------------
        # 2. Exception lookup (by exception_id or linked transaction ID)
        # -------------------------------------------------------------
        stmt_exc = select(ExceptionORM).where(
            or_(
                ExceptionORM.id == entity_id,
                ExceptionORM.transaction_id == entity_id,
            )
        )
        exc = (await self.session.execute(stmt_exc)).scalars().first()

        if not exc:
            stmt_domain = (
                select(ExceptionORM)
                .join(TransactionORM, ExceptionORM.transaction_id == TransactionORM.id)
                .where(TransactionORM.domain_transaction_id == entity_id)
            )
            exc = (await self.session.execute(stmt_domain)).scalars().first()

        if not exc:
            stmt_et = (
                select(ExceptionORM)
                .join(ExceptionTransactionORM, ExceptionTransactionORM.exception_id == ExceptionORM.id)
                .join(TransactionORM, ExceptionTransactionORM.transaction_id == TransactionORM.id)
                .where(or_(TransactionORM.id == entity_id, TransactionORM.domain_transaction_id == entity_id))
            )
            exc = (await self.session.execute(stmt_et)).scalars().first()

        if exc:
            stmt_tx = (
                select(TransactionORM)
                .join(ExceptionTransactionORM, ExceptionTransactionORM.transaction_id == TransactionORM.id)
                .where(ExceptionTransactionORM.exception_id == exc.id)
            )
            txns = list((await self.session.execute(stmt_tx)).scalars().all())
            if exc.transaction_id and not any(t.id == exc.transaction_id for t in txns):
                pt = (await self.session.execute(select(TransactionORM).where(TransactionORM.id == exc.transaction_id))).scalar_one_or_none()
                if pt:
                    txns.append(pt)

            rel_ids = RelatedIDs(
                transaction_ids=[t.domain_transaction_id for t in txns],
                order_id=next((t.order_id for t in txns if t.order_id), None),
                settlement_id=next((t.domain_transaction_id for t in txns if t.meta_data and t.meta_data.get("type") == "settlement"), None),
                reference_number=next((t.reference_number for t in txns if t.reference_number), None),
            )

            # Resolved exception case
            if exc.resolved or (exc.status and exc.status.lower() in ("resolved", "matched")):
                return InvestigationDossierResponse(
                    investigation_id=f"dossier_res_{exc.id[:8]}",
                    entity_id=entity_id,
                    entity_type="exception",
                    status="RESOLVED",
                    exception_status=exc.status,
                    financial_exposure=Decimal("0.00"),
                    variance=Decimal("0.00"),
                    variance_type="RESOLVED",
                    related_ids=rel_ids,
                    reconciliation_evidence={
                        "exception_id": exc.id,
                        "resolved": True,
                        "resolved_at": exc.resolved_at.isoformat() if exc.resolved_at else None,
                        "status": exc.status,
                        "transactions": [
                            {"txn_id": t.domain_transaction_id, "amount": str(t.amount), "source": t.source.value if hasattr(t.source, "value") else str(t.source)}
                            for t in txns
                        ],
                    },
                    root_cause_candidates=[
                        RootCauseCandidate(
                            cause=f"Exception resolved - {exc.explanation}",
                            confidence=Decimal("1.00"),
                            evidence=f"Exception {exc.id} status is '{exc.status}' and marked resolved={exc.resolved}.",
                        )
                    ],
                    recommended_action="No action required - exception resolved",
                    requires_human_review=False,
                    insufficient_evidence=False,
                    evidence_summary=f"Exception {exc.id} has been fully resolved with zero residual exposure.",
                    method="deterministic",
                    llm_invoked=False,
                    created_at=now,
                )

            # Insufficient evidence case (no linked transactions)
            if len(txns) == 0:
                return InvestigationDossierResponse(
                    investigation_id=f"dossier_insuf_{exc.id[:8]}",
                    entity_id=entity_id,
                    entity_type="exception",
                    status="INSUFFICIENT_EVIDENCE",
                    exception_status=exc.status,
                    financial_exposure=Decimal(str(exc.financial_exposure or "0.00")),
                    variance=Decimal(str(exc.financial_exposure or "0.00")),
                    variance_type="UNKNOWN",
                    related_ids=rel_ids,
                    reconciliation_evidence={
                        "exception_id": exc.id,
                        "exception_category": str(exc.exception_category),
                        "records_found": 0,
                    },
                    root_cause_candidates=[
                        RootCauseCandidate(
                            cause="Insufficient evidence to establish root cause",
                            confidence=Decimal("0.10"),
                            evidence="No linked transaction counterpart records exist in database for this exception.",
                        )
                    ],
                    recommended_action="Manual audit required - provide missing transaction counterpart records",
                    requires_human_review=True,
                    insufficient_evidence=True,
                    evidence_summary="Required transaction records are missing; insufficient evidence to establish root cause.",
                    method="deterministic",
                    llm_invoked=False,
                    created_at=now,
                )

            # Active exception with linked transactions
            stmt_inv = select(InvestigationORM).where(InvestigationORM.exception_id == exc.id)
            inv_rec = (await self.session.execute(stmt_inv)).scalar_one_or_none()

            if inv_rec:
                conclusion_root_cause = inv_rec.root_cause
                conclusion_confidence = inv_rec.confidence
                conclusion_action = inv_rec.recommended_action
                conclusion_method = inv_rec.method
                conclusion_llm = inv_rec.llm_invoked
                conclusion_hitl = inv_rec.requires_human_review
            else:
                domain_txns = [orm_to_domain(t) for t in txns]
                conclusion = await self.investigate(
                    exception_id=exc.id,
                    run_id=exc.run_id,
                    transactions=domain_txns,
                    investigation_id=f"inv_{exc.id[:8]}_{uuid.uuid4().hex[:6]}",
                )
                conclusion_root_cause = conclusion.root_cause
                conclusion_confidence = conclusion.confidence
                conclusion_action = conclusion.recommended_action
                conclusion_method = conclusion.method.value if hasattr(conclusion.method, "value") else str(conclusion.method)
                conclusion_llm = conclusion.llm_invoked
                conclusion_hitl = conclusion.requires_human_review

            amounts = [t.amount for t in txns if t.amount is not None]
            if len(amounts) >= 2:
                variance = abs(amounts[0] - amounts[1])
                var_type = "AMOUNT_MISMATCH" if variance > Decimal("0") else "NO_VARIANCE"
            else:
                variance = Decimal(str(exc.financial_exposure or "0.00"))
                var_type = "MISSING_COUNTERPART"

            candidates = [
                RootCauseCandidate(
                    cause=conclusion_root_cause,
                    confidence=conclusion_confidence,
                    evidence=f"Category '{exc.exception_category}' verified across {len(txns)} transaction record(s). Financial exposure is ₹{exc.financial_exposure}.",
                )
            ]

            recon_evidence = {
                "exception_id": exc.id,
                "category": str(exc.exception_category),
                "run_id": exc.run_id,
                "confidence": str(exc.confidence),
                "transactions": [
                    {
                        "txn_id": t.domain_transaction_id,
                        "source": t.source.value if hasattr(t.source, "value") else str(t.source),
                        "amount": str(t.amount),
                        "currency": t.currency,
                        "reference_number": t.reference_number,
                        "fee": str(t.fee) if t.fee is not None else None,
                        "tax": str(t.tax) if t.tax is not None else None,
                        "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                    }
                    for t in txns
                ],
            }

            return InvestigationDossierResponse(
                investigation_id=f"dossier_exc_{exc.id[:8]}",
                entity_id=entity_id,
                entity_type="exception",
                status=exc.status.upper() if exc.status else "OPEN",
                exception_status=exc.status,
                financial_exposure=Decimal(str(exc.financial_exposure or "0.00")),
                variance=variance,
                variance_type=var_type,
                related_ids=rel_ids,
                reconciliation_evidence=recon_evidence,
                root_cause_candidates=candidates,
                recommended_action=conclusion_action or exc.recommended_action or "Review exception and verify feed settlement",
                requires_human_review=conclusion_hitl,
                insufficient_evidence=False,
                evidence_summary=f"Exception {exc.id} ({exc.exception_category}): {conclusion_root_cause}",
                method=conclusion_method,
                llm_invoked=conclusion_llm,
                created_at=now,
            )

        # -------------------------------------------------------------
        # 3. Settlement lookup (by settlement_id or reference / UTR)
        # -------------------------------------------------------------
        stmt_setl = select(TransactionORM).where(
            and_(
                or_(
                    TransactionORM.domain_transaction_id == entity_id,
                    TransactionORM.id == entity_id,
                    TransactionORM.reference_number == entity_id,
                ),
                TransactionORM.source == TransactionSource.GATEWAY.value,
                TransactionORM.meta_data["type"].astext == "settlement",
            )
        )
        setl_tx = (await self.session.execute(stmt_setl)).scalar_one_or_none()

        if setl_tx:
            from app.services.razorpay_settlement_intelligence_service import (
                RazorpaySettlementIntelligenceService,
                SettlementVarianceType,
            )

            settle_intel = RazorpaySettlementIntelligenceService(self.session)
            breakdown = await settle_intel.get_settlement_financial_breakdown(setl_tx.domain_transaction_id)
            bank_recon = await settle_intel.get_settlement_bank_reconciliation(setl_tx.domain_transaction_id)
            linkage = await settle_intel.get_settlement_transaction_linkage(setl_tx.domain_transaction_id)

            rel_ids = RelatedIDs(
                transaction_ids=[setl_tx.domain_transaction_id] + linkage.linked_transaction_ids,
                order_id=setl_tx.order_id,
                settlement_id=setl_tx.domain_transaction_id,
                reference_number=bank_recon.utr,
            )

            recon_evidence = {
                "settlement_id": setl_tx.domain_transaction_id,
                "gross_amount": str(breakdown.gross_amount),
                "fee_amount": str(breakdown.fee_amount),
                "tax_amount": str(breakdown.tax_amount),
                "expected_net_amount": str(breakdown.expected_net_amount),
                "bank_received_amount": str(breakdown.bank_received_amount),
                "variance": str(breakdown.variance),
                "variance_type": breakdown.variance_type.value,
                "utr": bank_recon.utr,
                "bank_matched": bank_recon.bank_matched,
                "bank_transaction_id": bank_recon.bank_transaction_id,
                "linked_transactions_count": linkage.linked_transaction_count,
            }

            if breakdown.variance_type == SettlementVarianceType.NO_VARIANCE:
                root_candidates = [
                    RootCauseCandidate(
                        cause="Settlement reconciled with bank statement",
                        confidence=Decimal("1.00"),
                        evidence=f"Expected net ₹{breakdown.expected_net_amount} matched bank credit of ₹{breakdown.bank_received_amount} via UTR {bank_recon.utr}.",
                    )
                ]
                rec_action = "No action required - settlement reconciled"
                hitl = False
            else:
                raw_causes = settle_intel._determine_root_cause_candidates(
                    breakdown.variance_type, breakdown.variance, bank_recon.settlement_status
                )
                root_candidates = [
                    RootCauseCandidate(
                        cause=c,
                        confidence=Decimal("0.90") if idx == 0 else Decimal("0.75"),
                        evidence=f"Gross ₹{breakdown.gross_amount}, fee ₹{breakdown.fee_amount}, tax ₹{breakdown.tax_amount}, expected net ₹{breakdown.expected_net_amount} vs bank credit ₹{breakdown.bank_received_amount} (variance ₹{breakdown.variance}).",
                    )
                    for idx, c in enumerate(raw_causes[:3])
                ]
                rec_action = settle_intel._determine_recommended_action(
                    breakdown.variance_type, bank_recon.settlement_status, breakdown.variance
                )
                hitl = True

            if breakdown.variance_type == SettlementVarianceType.NO_VARIANCE:
                settlement_exposure = Decimal("0.00")
                settlement_variance = Decimal("0.00")
            elif breakdown.variance_type == SettlementVarianceType.MISSING_BANK_CREDIT:
                settlement_exposure = breakdown.expected_net_amount
                settlement_variance = -breakdown.expected_net_amount
            else:
                settlement_exposure = abs(breakdown.variance)
                settlement_variance = breakdown.variance

            return InvestigationDossierResponse(
                investigation_id=f"dossier_setl_{setl_tx.domain_transaction_id[:12]}",
                entity_id=entity_id,
                entity_type="settlement",
                status=bank_recon.settlement_status.value,
                exception_status=None,
                financial_exposure=settlement_exposure,
                variance=settlement_variance,
                variance_type=breakdown.variance_type.value,
                related_ids=rel_ids,
                reconciliation_evidence=recon_evidence,
                root_cause_candidates=root_candidates,
                recommended_action=rec_action,
                requires_human_review=hitl,
                insufficient_evidence=False,
                evidence_summary=f"Settlement {setl_tx.domain_transaction_id}: variance is ₹{settlement_variance} ({breakdown.variance_type.value}).",
                method="deterministic",
                llm_invoked=False,
                created_at=now,
            )

        # -------------------------------------------------------------
        # 4. Matched Transaction lookup (by match_id or transaction ID)
        # -------------------------------------------------------------
        match_record = (await self.session.execute(select(MatchORM).where(MatchORM.id == entity_id))).scalars().first()
        if not match_record:
            stmt_match = (
                select(MatchORM)
                .join(MatchTransactionORM, MatchTransactionORM.match_id == MatchORM.id)
                .join(TransactionORM, MatchTransactionORM.transaction_id == TransactionORM.id)
                .where(or_(TransactionORM.id == entity_id, TransactionORM.domain_transaction_id == entity_id))
            )
            match_record = (await self.session.execute(stmt_match)).scalars().first()

        if match_record:
            stmt_mt = (
                select(TransactionORM)
                .join(MatchTransactionORM, MatchTransactionORM.transaction_id == TransactionORM.id)
                .where(MatchTransactionORM.match_id == match_record.id)
            )
            matched_txns = list((await self.session.execute(stmt_mt)).scalars().all())

            rel_ids = RelatedIDs(
                transaction_ids=[t.domain_transaction_id for t in matched_txns],
                order_id=next((t.order_id for t in matched_txns if t.order_id), None),
                settlement_id=next((t.domain_transaction_id for t in matched_txns if t.meta_data and t.meta_data.get("type") == "settlement"), None),
                reference_number=next((t.reference_number for t in matched_txns if t.reference_number), None),
            )

            recon_evidence = {
                "match_id": match_record.id,
                "match_type": match_record.match_type.value if hasattr(match_record.match_type, "value") else str(match_record.match_type),
                "confidence": str(match_record.confidence),
                "reason": match_record.reason,
                "transactions": [
                    {"txn_id": t.domain_transaction_id, "source": t.source.value if hasattr(t.source, "value") else str(t.source), "amount": str(t.amount)}
                    for t in matched_txns
                ],
            }

            return InvestigationDossierResponse(
                investigation_id=f"dossier_match_{match_record.id[:8]}",
                entity_id=entity_id,
                entity_type="matched_transaction",
                status="MATCHED",
                exception_status=None,
                financial_exposure=Decimal("0.00"),
                variance=Decimal("0.00"),
                variance_type="NO_VARIANCE",
                related_ids=rel_ids,
                reconciliation_evidence=recon_evidence,
                root_cause_candidates=[
                    RootCauseCandidate(
                        cause=f"Reconciled ({match_record.match_type.value if hasattr(match_record.match_type, 'value') else match_record.match_type})",
                        confidence=match_record.confidence,
                        evidence=f"Deterministic/ML match verified across {len(matched_txns)} feed records with confidence {match_record.confidence}: {match_record.reason}",
                    )
                ],
                recommended_action="No action required - transaction reconciled",
                requires_human_review=False,
                insufficient_evidence=False,
                evidence_summary=f"Transaction match {match_record.id} verified with 0.00 variance and zero exposure.",
                method="deterministic",
                llm_invoked=False,
                created_at=now,
            )

        # -------------------------------------------------------------
        # 5. Standalone Transaction lookup (processed or orphan)
        # -------------------------------------------------------------
        stmt_single_tx = select(TransactionORM).where(
            or_(TransactionORM.id == entity_id, TransactionORM.domain_transaction_id == entity_id)
        )
        single_tx = (await self.session.execute(stmt_single_tx)).scalar_one_or_none()
        if single_tx:
            rel_ids = RelatedIDs(
                transaction_ids=[single_tx.domain_transaction_id],
                order_id=single_tx.order_id,
                settlement_id=single_tx.domain_transaction_id if single_tx.meta_data and single_tx.meta_data.get("type") == "settlement" else None,
                reference_number=single_tx.reference_number,
            )
            if single_tx.status.value == "processed":
                return InvestigationDossierResponse(
                    investigation_id=f"dossier_tx_{single_tx.id[:8]}",
                    entity_id=entity_id,
                    entity_type="transaction",
                    status="PROCESSED",
                    exception_status=None,
                    financial_exposure=Decimal("0.00"),
                    variance=Decimal("0.00"),
                    variance_type="NO_VARIANCE",
                    related_ids=rel_ids,
                    reconciliation_evidence={
                        "txn_id": single_tx.domain_transaction_id,
                        "source": single_tx.source.value if hasattr(single_tx.source, "value") else str(single_tx.source),
                        "amount": str(single_tx.amount),
                        "status": single_tx.status.value,
                    },
                    root_cause_candidates=[
                        RootCauseCandidate(
                            cause="Transaction processed normally",
                            confidence=Decimal("1.00"),
                            evidence=f"Transaction {single_tx.domain_transaction_id} is in PROCESSED status with zero active exceptions.",
                        )
                    ],
                    recommended_action="No action required",
                    requires_human_review=False,
                    insufficient_evidence=False,
                    evidence_summary=f"Transaction {single_tx.domain_transaction_id} verified processed.",
                    method="deterministic",
                    llm_invoked=False,
                    created_at=now,
                )
            else:
                return InvestigationDossierResponse(
                    investigation_id=f"dossier_orphan_{single_tx.id[:8]}",
                    entity_id=entity_id,
                    entity_type="transaction",
                    status="INSUFFICIENT_EVIDENCE",
                    exception_status=single_tx.status.value,
                    financial_exposure=single_tx.amount,
                    variance=single_tx.amount,
                    variance_type="MISSING_COUNTERPART",
                    related_ids=rel_ids,
                    reconciliation_evidence={
                        "txn_id": single_tx.domain_transaction_id,
                        "source": single_tx.source.value if hasattr(single_tx.source, "value") else str(single_tx.source),
                        "amount": str(single_tx.amount),
                        "status": single_tx.status.value,
                        "counterparts_found": 0,
                    },
                    root_cause_candidates=[
                        RootCauseCandidate(
                            cause="Insufficient evidence - orphan transaction without feed counterparts",
                            confidence=Decimal("0.20"),
                            evidence=f"Transaction {single_tx.domain_transaction_id} found in {single_tx.source.value} with amount ₹{single_tx.amount}, but no counterpart records exist in database.",
                        )
                    ],
                    recommended_action="Supply missing feed counterpart records for reconciliation",
                    requires_human_review=True,
                    insufficient_evidence=True,
                    evidence_summary=f"Transaction {single_tx.domain_transaction_id} has no counterpart records; evidence is insufficient to determine root cause.",
                    method="deterministic",
                    llm_invoked=False,
                    created_at=now,
                )

        # -------------------------------------------------------------
        # 6. Entity not found anywhere
        # -------------------------------------------------------------
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Investigation entity not found for ID '{entity_id}'",
        )

