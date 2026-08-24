"""
Incremental / Real-Time Reconciliation Service for Project Sentinel.

Processes incoming single or micro-batch transactions in real time:
1. Persists transaction idempotently in PostgreSQL.
2. Identifies affected candidate scope (±3 days, matching currency, complementary sources).
3. Runs Deterministic Matching first (exact UTR, Order ID, Ref).
4. Falls back to XGBoost ML Scorer on candidates.
5. Evaluates DecisionPolicy.
6. Creates exceptions for unresolved/ambiguous items and selectively invokes investigation.
7. Logs state transitions to audit repository.
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.mappers.transaction_mapper import domain_to_orm, orm_to_domain
from app.database.models import (
    AuditEvent as AuditEventORM,
    Decision as DecisionORM,
    Exception as ExceptionORM,
    Match as MatchORM,
    ReconciliationRun as ReconciliationRunORM,
    Transaction as TransactionORM,
)
from app.database.repositories.audit_repository import AuditRepository
from app.database.repositories.decision_repository import DecisionRepository
from app.database.repositories.exception_repository import ExceptionRepository
from app.database.repositories.investigation_repository import InvestigationRepository
from app.database.repositories.match_repository import MatchRepository
from app.database.repositories.reconciliation_repository import ReconciliationRepository
from app.database.repositories.transaction_repository import TransactionRepository
from app.investigation.service import InvestigationService
from app.matching.candidate import CandidateGenerator
from app.matching.decision import DecisionPolicy
from app.matching.deterministic import DeterministicMatcher
from app.matching.features import FeatureExtractor
from app.matching.ml_scorer import MLScorer
from app.models.decision_result import DecisionAction
from app.models.match_result import MatchType
from app.models.transaction import Transaction, TransactionSource, TransactionStatus

logger = logging.getLogger(__name__)


@dataclass
class IncrementalReconciliationResult:
    """Result of an incremental real-time transaction reconciliation."""
    transaction_id: str
    status: str  # "MATCHED_DETERMINISTIC", "MATCHED_ML", "EXCEPTION_CREATED", "DUPLICATE_IGNORED"
    action: str  # DecisionAction enum value
    match_id: Optional[str] = None
    matched_transaction_id: Optional[str] = None
    confidence: float = 0.0
    exception_id: Optional[str] = None
    investigation_id: Optional[str] = None
    processing_time_ms: float = 0.0


class IncrementalReconciliationService:
    """Orchestrates single-transaction and streaming real-time reconciliation."""

    def __init__(
        self,
        session: AsyncSession,
        ml_scorer: Optional[MLScorer] = None,
        investigation_service: Optional[InvestigationService] = None,
    ):
        self.session = session
        self.ml_scorer = ml_scorer or MLScorer(model_type="xgboost")
        self.investigation_service = investigation_service
        self.feature_extractor = FeatureExtractor()
        self.decision_policy = DecisionPolicy()

        self.txn_repo = TransactionRepository(session)
        self.match_repo = MatchRepository(session)
        self.decision_repo = DecisionRepository(session)
        self.exception_repo = ExceptionRepository(session)
        self.audit_repo = AuditRepository(session)

    async def ingest_and_reconcile(
        self,
        incoming_txn: Transaction,
        run_id: str = "stream_live",
    ) -> IncrementalReconciliationResult:
        """Ingest a single transaction and reconcile it incrementally against active database scope."""
        t0 = datetime.now(timezone.utc)

        # 1. Idempotency Check: check if transaction already exists
        existing = await self.txn_repo.get_orm_by_source_and_domain_id(
            incoming_txn.source.value, incoming_txn.txn_id
        )
        if existing:
            return IncrementalReconciliationResult(
                transaction_id=incoming_txn.txn_id,
                status="DUPLICATE_IGNORED",
                action="ALREADY_INGESTED",
                processing_time_ms=(datetime.now(timezone.utc) - t0).total_seconds() * 1000,
            )

        # Ensure run record exists for foreign key integrity
        from app.database.models import ReconciliationRun as ReconciliationRunORM, ReconciliationRunStatus
        run_check = await self.session.execute(select(ReconciliationRunORM).where(ReconciliationRunORM.id == run_id))
        if not run_check.scalars().first():
            now_dt = datetime.now(timezone.utc).replace(tzinfo=None)
            new_run = ReconciliationRunORM(
                id=run_id,
                run_id=run_id,
                status=ReconciliationRunStatus.COMPLETED,
                started_at=now_dt,
                completed_at=now_dt,
                gateway_count=0,
                ledger_count=0,
                bank_count=0,
                match_count=0,
                exception_count=0,
                created_at=now_dt,
            )
            self.session.add(new_run)
            await self.session.flush()

        # 2. Persist new transaction
        orm_txn_id = await self.txn_repo.create(incoming_txn)

        # 3. Retrieve candidate scope from other sources within ±3 days
        delta = timedelta(days=3)
        min_dt = incoming_txn.timestamp - delta
        max_dt = incoming_txn.timestamp + delta

        # Convert min_dt/max_dt to naive UTC if needed
        min_dt_naive = min_dt.replace(tzinfo=None) if min_dt.tzinfo else min_dt
        max_dt_naive = max_dt.replace(tzinfo=None) if max_dt.tzinfo else max_dt

        stmt = select(TransactionORM).where(
            TransactionORM.source != incoming_txn.source.value,
            TransactionORM.currency == incoming_txn.currency,
            TransactionORM.timestamp >= min_dt_naive,
            TransactionORM.timestamp <= max_dt_naive,
        )
        res = await self.session.execute(stmt)
        candidate_orms = res.scalars().all()
        candidate_domain_txns = [orm_to_domain(c) for c in candidate_orms]

        # Group by source for candidate generator & deterministic matcher
        grouped_scope: dict[TransactionSource, list[Transaction]] = {
            TransactionSource.GATEWAY: [],
            TransactionSource.LEDGER: [],
            TransactionSource.BANK: [],
        }
        for c in candidate_domain_txns:
            grouped_scope[c.source].append(c)
        grouped_scope[incoming_txn.source].append(incoming_txn)

        # 4. Deterministic Matching First
        matcher = DeterministicMatcher(grouped_scope)
        det_matches = matcher.match_all()

        # Find if our new incoming transaction is in any deterministic match
        for d_match in det_matches:
            if incoming_txn.txn_id in d_match.transaction_ids and d_match.confidence >= Decimal("0.95"):
                # Deterministic match found!
                other_id = [tid for tid in d_match.transaction_ids if tid != incoming_txn.txn_id][0]
                match_id = await self.match_repo.create(d_match, run_id)
                dec_res = self.decision_policy.evaluate_deterministic(d_match)
                await self.decision_repo.create(dec_res, run_id, match_id)

                elapsed = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
                return IncrementalReconciliationResult(
                    transaction_id=incoming_txn.txn_id,
                    status="MATCHED_DETERMINISTIC",
                    action=dec_res.action.value,
                    match_id=match_id,
                    matched_transaction_id=other_id,
                    confidence=float(d_match.confidence),
                    processing_time_ms=elapsed,
                )

        # 5. ML Candidate Scoring Fallback
        cand_gen = CandidateGenerator(grouped_scope)
        candidates = cand_gen.get_candidates(incoming_txn)

        if candidates:
            cand_features = [self.feature_extractor.extract_features(incoming_txn, c) for c in candidates]
            try:
                probs = self.ml_scorer.predict(cand_features)
                best_idx = max(range(len(probs)), key=lambda i: probs[i])
                best_prob = probs[best_idx]
                best_cand = candidates[best_idx]

                if best_prob >= 0.70:
                    dec_res = self.decision_policy.evaluate_ml(
                        incoming_txn, best_cand, best_prob, grouped_scope
                    )
                    if dec_res.action in (DecisionAction.PROPOSE_MATCH, DecisionAction.AUTO_MATCH):
                        match_domain = d_match = None
                        from app.models.match_result import MatchResult
                        m_obj = MatchResult(
                            transaction_ids=[incoming_txn.txn_id, best_cand.txn_id],
                            confidence=Decimal(str(round(best_prob, 4))),
                            reason=f"ML candidate score: {best_prob:.3f}",
                            match_type=MatchType.PROBABLE,
                            evidence={"ml_probability": best_prob},
                        )
                        match_id = await self.match_repo.create(m_obj, run_id)
                        await self.decision_repo.create(dec_res, run_id, match_id)

                        elapsed = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
                        return IncrementalReconciliationResult(
                            transaction_id=incoming_txn.txn_id,
                            status="MATCHED_ML",
                            action=dec_res.action.value,
                            match_id=match_id,
                            matched_transaction_id=best_cand.txn_id,
                            confidence=best_prob,
                            processing_time_ms=elapsed,
                        )
            except Exception as e:
                logger.warning("Incremental ML scoring error: %s", e)

        # 6. Unresolved / Exception Creation
        from app.models.exception_record import ExceptionCategory, ExceptionRecord
        from app.risk.calculator import RiskCalculator
        from app.risk.interface import RiskInput

        risk_out = RiskCalculator.calculate(
            RiskInput(
                category=ExceptionCategory.UNEXPLAINED,
                financial_exposure=incoming_txn.amount,
                confidence=Decimal("0.30"),
                is_duplicate=False,
            )
        )

        exc_domain = ExceptionRecord(
            transaction_id=incoming_txn.txn_id,
            category=ExceptionCategory.UNEXPLAINED,
            confidence=Decimal("0.30"),
            financial_exposure=incoming_txn.amount,
            expected_cost=risk_out.expected_cost,
            explanation=f"No matching counterpart found in candidate window for {incoming_txn.source.value} {incoming_txn.txn_id}",
        )
        exc_id = await self.exception_repo.create(exc_domain, run_id, orm_txn_id)

        # 7. Selective Investigation
        inv_id = None
        if self.investigation_service:
            from app.investigation.exposure import ExposureCalculator
            should_escalate, _ = ExposureCalculator.should_escalate_to_llm(
                financial_exposure=incoming_txn.amount,
                category=ExceptionCategory.UNEXPLAINED,
                deterministic_confidence=Decimal("0.30"),
                is_duplicate=False,
            )
            if should_escalate:
                try:
                    c = await self.investigation_service.investigate(
                        exception_id=exc_id,
                        run_id=run_id,
                        transactions=[incoming_txn],
                    )
                    inv_id = c.investigation_id
                except Exception as ex:
                    logger.warning("Investigation invocation error: %s", ex)

        elapsed = (datetime.now(timezone.utc) - t0).total_seconds() * 1000
        return IncrementalReconciliationResult(
            transaction_id=incoming_txn.txn_id,
            status="EXCEPTION_CREATED",
            action=DecisionAction.UNRESOLVED.value,
            exception_id=exc_id,
            investigation_id=inv_id,
            confidence=0.30,
            processing_time_ms=elapsed,
        )
