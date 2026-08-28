import logging
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from app.database.repositories import (
    AuditRepository,
    DecisionRepository,
    ExceptionRepository,
    MatchRepository,
    ReconciliationRepository,
    TransactionRepository,
)
from app.matching.candidate import CandidateGenerator
from app.matching.decision import DecisionPolicy
from app.matching.deterministic import DeterministicMatcher
from app.matching.features import FeatureExtractor
from app.matching.ml_scorer import MLScorer
from app.investigation.analyzer import DeterministicAnalyzer
from app.investigation.evidence import InvestigationContextBuilder
from app.models.decision_result import DecisionAction
from app.models.exception_record import ExceptionCategory, ExceptionRecord
from app.models.match_result import MatchResult, MatchType
from app.models.reconciliation_summary import ReconciliationSummary
from app.models.transaction import Transaction, TransactionSource

if TYPE_CHECKING:
    from app.investigation.service import InvestigationService

logger = logging.getLogger(__name__)

# Actions that require investigation escalation.
_INVESTIGATION_ACTIONS = {
    DecisionAction.MANUAL_REVIEW,
    DecisionAction.AMBIGUOUS,
    DecisionAction.UNRESOLVED,
}


class ReconciliationService:
    """Async orchestrator for the end-to-end reconciliation pipeline."""

    def __init__(
        self,
        session,
        transaction_repo: TransactionRepository,
        reconciliation_repo: ReconciliationRepository,
        match_repo: MatchRepository,
        decision_repo: DecisionRepository,
        exception_repo: ExceptionRepository,
        audit_repo: AuditRepository,
        ml_scorer: Optional[MLScorer] = None,
        investigation_service: Optional["InvestigationService"] = None,
    ):
        """Initialize reconciliation service with dependencies.
        
        Args:
            session: Database session
            transaction_repo: Transaction repository
            reconciliation_repo: Reconciliation repository
            match_repo: Match repository
            decision_repo: Decision repository
            exception_repo: Exception repository
            audit_repo: Audit repository
            ml_scorer: Optional ML scorer for candidate scoring
            investigation_service: Optional investigation service; when provided,
                MANUAL_REVIEW / AMBIGUOUS / UNRESOLVED decisions are automatically
                investigated.  AUTO_MATCH decisions are never passed to it.
        """
        self.session = session
        self.transaction_repo = transaction_repo
        self.reconciliation_repo = reconciliation_repo
        self.match_repo = match_repo
        self.decision_repo = decision_repo
        self.exception_repo = exception_repo
        self.audit_repo = audit_repo
        self.ml_scorer = ml_scorer
        self.investigation_service = investigation_service

    async def run_reconciliation(
        self, transactions_by_source: dict[TransactionSource, list[Transaction]], run_id: str
    ) -> ReconciliationSummary:
        """Run the end-to-end reconciliation pipeline.
        
        Args:
            transactions_by_source: Normalized transactions grouped by source
            run_id: Unique identifier for this reconciliation run
            
        Returns:
            ReconciliationSummary with execution results
        """
        started_at = datetime.now(timezone.utc)
        run_orm_id: Optional[str] = None
        
        try:
            # Create ReconciliationRun with RUNNING status
            from app.models.reconciliation_run import ReconciliationRun, RunStatus
            
            total_txns = sum(len(txns) for txns in transactions_by_source.values())
            gateway_count = len(transactions_by_source.get(TransactionSource.GATEWAY, []))
            ledger_count = len(transactions_by_source.get(TransactionSource.LEDGER, []))
            bank_count = len(transactions_by_source.get(TransactionSource.BANK, []))
            
            run_domain = ReconciliationRun(
                run_id=run_id,
                status=RunStatus.RUNNING,
                started_at=started_at,
                gateway_count=gateway_count,
                ledger_count=ledger_count,
                bank_count=bank_count,
                match_count=0,
                exception_count=0,
            )
            run_orm_id = await self.reconciliation_repo.create_run(run_domain)
            
            # Persist transactions (reuse existing if same source+domain_id)
            persisted_txns, txn_orm_ids = await self._persist_transactions(transactions_by_source)
            
            # Create ReconciliationItems for all transactions (using ORM UUIDs as FK)
            await self._create_reconciliation_items(run_orm_id, txn_orm_ids)
            
            # Run DeterministicMatcher
            matcher = DeterministicMatcher(transactions_by_source)
            deterministic_matches = matcher.match_all()
            
            # Track matched transaction IDs from high-confidence deterministic matches
            matched_txn_ids = set()
            high_conf_deterministic_matches = []
            for match in deterministic_matches:
                if match.confidence >= Decimal("0.95"):
                    matched_txn_ids.update(match.transaction_ids)
                    high_conf_deterministic_matches.append(match)
            
            # For unresolved transactions, run CandidateGenerator + MLScorer
            unresolved_txns = self._get_unresolved_transactions(persisted_txns, matched_txn_ids)
            ml_matches = []
            if unresolved_txns and self.ml_scorer:
                ml_matches = await self._run_ml_scoring(unresolved_txns, transactions_by_source)
            
            # Combine all matches (high-confidence deterministic + ML matches + remaining fallback)
            if self.ml_scorer:
                ml_matched_txn_ids = {tid for m in ml_matches for tid in m.transaction_ids}
                remaining_det_matches = [
                    m for m in deterministic_matches
                    if m.confidence < Decimal("0.95") and not any(tid in ml_matched_txn_ids for tid in m.transaction_ids)
                ]
                raw_all_matches = high_conf_deterministic_matches + ml_matches + remaining_det_matches
            else:
                raw_all_matches = deterministic_matches

            # Enforce strict disjoint match assignment across all final matches
            assigned_tids = set()
            all_matches = []
            for m in raw_all_matches:
                unassigned = [tid for tid in m.transaction_ids if tid not in assigned_tids]
                if len(unassigned) >= 2:
                    m_clean = m.model_copy(update={"transaction_ids": unassigned})
                    all_matches.append(m_clean)
                    assigned_tids.update(unassigned)
            
            # Run DecisionPolicy for all candidates
            decision_policy = DecisionPolicy()
            decisions = await self._make_decisions(all_matches, transactions_by_source, decision_policy)
            
            # Persist matches via MatchRepository
            # match.transaction_ids holds domain txn_ids; FK needs ORM UUIDs
            match_ids = []
            for match in all_matches:
                orm_match = match.model_copy(
                    update={"transaction_ids": [txn_orm_ids.get(tid, tid) for tid in match.transaction_ids]}
                )
                match_id = await self.match_repo.create(orm_match, run_orm_id)
                match_ids.append(match_id)
            
            # Persist decisions via DecisionRepository
            for decision, match_id in zip(decisions, match_ids):
                await self.decision_repo.create(decision, run_orm_id, match_id)
            
            # Create exceptions for MANUAL_REVIEW, AMBIGUOUS, UNRESOLVED, REJECT
            txn_by_id_map = {txn.txn_id: txn for txns in transactions_by_source.values() for txn in txns}
            exception_ids = await self._create_exceptions_with_ids(decisions, run_orm_id, txn_orm_ids, txn_by_id_map)
            exception_count = len(exception_ids)
            
            # Write audit events for all stages
            await self._write_audit_events(run_orm_id, all_matches, decisions, txn_orm_ids)
            
            # Trigger investigation for escalated decisions (not AUTO_MATCH)
            if self.investigation_service is not None:
                await self._run_investigations(
                    run_id=run_orm_id,
                    decisions=decisions,
                    exception_ids=exception_ids,
                    txn_by_id={txn_id: txn for txns in transactions_by_source.values() for txn_id, txn in [(t.txn_id, t) for t in txns]},
                )
            
            # Update ReconciliationRun with COMPLETED status and counts
            await self._update_run_completion(
                run_orm_id,
                len(deterministic_matches),
                len(ml_matches),
                exception_count,
            )
            
            # Build summary
            completed_at = datetime.now(timezone.utc)
            summary = self._build_summary(
                run_id,
                total_txns,
                len(deterministic_matches),
                len(ml_matches),
                decisions,
                exception_count,
                started_at,
                completed_at,
            )
            
            return summary
            
        except Exception as e:
            # Mark run as FAILED on exception if run was created
            if run_orm_id:
                try:
                    await self.reconciliation_repo.update_run_status(run_orm_id, "failed")
                except Exception:
                    pass
            raise

    async def _persist_transactions(
        self, transactions_by_source: dict[TransactionSource, list[Transaction]]
    ) -> tuple[dict[str, Transaction], dict[str, str]]:
        """Persist transactions, reusing existing if same source+domain_id.
        
        Args:
            transactions_by_source: Transactions grouped by source
            
        Returns:
            Tuple of:
            - Dict mapping domain txn_id to Transaction domain model
            - Dict mapping domain txn_id to ORM UUID (for FK use)
        """
        persisted: dict[str, Transaction] = {}
        orm_ids: dict[str, str] = {}  # domain_txn_id -> ORM UUID
        
        for source, txns in transactions_by_source.items():
            for txn in txns:
                # Check if transaction already exists by source + domain_id
                existing_orm = await self.transaction_repo.get_orm_by_source_and_domain_id(
                    source.value, txn.txn_id
                )
                if existing_orm:
                    persisted[txn.txn_id] = txn
                    orm_ids[txn.txn_id] = existing_orm
                else:
                    orm_uuid = await self.transaction_repo.create(txn)
                    persisted[txn.txn_id] = txn
                    orm_ids[txn.txn_id] = orm_uuid
        
        return persisted, orm_ids

    async def _create_reconciliation_items(
        self, run_id: str, txn_orm_ids: dict[str, str]
    ) -> None:
        """Create ReconciliationItems for all transactions using ORM UUIDs as FK.
        
        Args:
            run_id: Reconciliation run ORM ID
            txn_orm_ids: Dict mapping domain txn_id to ORM UUID
        """
        for _domain_id, orm_uuid in txn_orm_ids.items():
            await self.reconciliation_repo.create_item(run_id, orm_uuid, "pending")

    def _get_unresolved_transactions(
        self, transactions: dict[str, Transaction], matched_txn_ids: set[str]
    ) -> list[Transaction]:
        """Get transactions that were not matched deterministically.
        
        Args:
            transactions: All transactions
            matched_txn_ids: IDs of already matched transactions
            
        Returns:
            List of unmatched transactions
        """
        return [txn for txn_id, txn in transactions.items() if txn_id not in matched_txn_ids]

    async def _run_ml_scoring(
        self, unresolved_txns: list[Transaction], transactions_by_source: dict[TransactionSource, list[Transaction]]
    ) -> list[MatchResult]:
        """Run ML scoring on unresolved transactions using the trained ML model artifact.

        1. For each unresolved transaction, generate candidates via CandidateGenerator.
        2. Extract features via FeatureExtractor.
        3. Predict match probability with MLScorer.
        4. Return MatchResult proposals (with PROBABLE match type) for downstream DecisionPolicy.

        Groq / InvestigationService are never touched here.
        """
        if not self.ml_scorer or not unresolved_txns:
            return []

        t0 = time.monotonic()
        feature_extractor = FeatureExtractor()
        candidate_gen = CandidateGenerator(transactions_by_source)

        # ------------------------------------------------------------------ #
        # Score unresolved candidate pairs                                    #
        # ------------------------------------------------------------------ #
        results: list[MatchResult] = []
        already_proposed: set[str] = set()
        unresolved_ids = {t.txn_id for t in unresolved_txns}

        for txn in unresolved_txns:
            if txn.txn_id in already_proposed:
                continue

            candidates = [c for c in candidate_gen.get_candidates(txn) if c.txn_id in unresolved_ids and c.txn_id not in already_proposed]
            if not candidates:
                continue

            # Extract features for all candidates
            cand_features = [feature_extractor.extract_features(txn, c) for c in candidates]

            try:
                probs = self.ml_scorer.predict(cand_features)
            except Exception as exc:
                logger.warning(
                    "ML prediction failed for txn %s: %s", txn.txn_id, exc
                )
                continue

            # Pick the best candidate
            best_idx = max(range(len(probs)), key=lambda i: probs[i])
            best_prob = probs[best_idx]
            best_cand = candidates[best_idx]

            # Only emit a result for non-trivially low probabilities so that
            # DecisionPolicy.evaluate_ml() can assign UNRESOLVED / MANUAL_REVIEW /
            # PROPOSE_MATCH as appropriate.  We skip pairs whose best probability
            # is essentially zero (< 0.05) to avoid polluting downstream stages.
            if best_prob < 0.05:
                continue

            pair_key = tuple(sorted([txn.txn_id, best_cand.txn_id]))
            if tuple(sorted([txn.txn_id, best_cand.txn_id])) in {
                tuple(sorted([r.transaction_ids[0], r.transaction_ids[1]]))
                for r in results
                if len(r.transaction_ids) >= 2
            }:
                continue

            results.append(
                MatchResult(
                    transaction_ids=[txn.txn_id, best_cand.txn_id],
                    confidence=Decimal(str(round(best_prob, 6))),
                    reason=f"ML candidate scoring (prob={best_prob:.4f})",
                    match_type=MatchType.PROBABLE,
                    evidence={
                        "ml_probability": best_prob,
                        "model_type": self.ml_scorer.model_type,
                    },
                )
            )
            already_proposed.add(txn.txn_id)
            already_proposed.add(best_cand.txn_id)

        elapsed_ms = (time.monotonic() - t0) * 1000
        logger.info(
            "ML scoring: %d unresolved → %d proposals in %.1f ms",
            len(unresolved_txns),
            len(results),
            elapsed_ms,
        )
        return results

    async def _make_decisions(
        self, matches: list, transactions_by_source: dict[TransactionSource, list[Transaction]], decision_policy: DecisionPolicy
    ) -> list:
        """Make decisions for all matches using DecisionPolicy.
        
        Args:
            matches: List of match results
            transactions_by_source: All transactions grouped by source
            decision_policy: Decision policy instance
            
        Returns:
            List of DecisionResult objects
        """
        decisions = []
        txn_by_id = {}
        for txns in transactions_by_source.values():
            for txn in txns:
                txn_by_id[txn.txn_id] = txn
        
        for match in matches:
            if len(match.transaction_ids) >= 2:
                txn1 = txn_by_id.get(match.transaction_ids[0])
                txn2 = txn_by_id.get(match.transaction_ids[1])
                
                if txn1 and txn2:
                    # For high-confidence deterministic matches, use evaluate_deterministic
                    if match.confidence >= Decimal("0.95") and match.match_type != MatchType.PROBABLE and "ml" not in str(match.reason).lower():
                        decision = decision_policy.evaluate_deterministic(match)
                    else:
                        decision = decision_policy.evaluate_ml(
                            txn1, txn2, float(match.confidence), transactions_by_source
                        )
                    decisions.append(decision)
        
        return decisions

    async def _create_exceptions(self, decisions: list, run_id: str) -> int:
        """Create exceptions for MANUAL_REVIEW, AMBIGUOUS, UNRESOLVED, REJECT.
        
        Args:
            decisions: List of DecisionResult objects
            run_id: Reconciliation run ID
            
        Returns:
            Number of exceptions created
        """
        return len(await self._create_exceptions_with_ids(decisions, run_id))

    async def _create_exceptions_with_ids(
        self,
        decisions: list,
        run_id: str,
        txn_orm_ids: dict[str, str] | None = None,
        txn_by_id: dict[str, Transaction] | None = None,
    ) -> list[tuple[str, list[str], object]]:
        """Create exceptions and return (exception_id, transaction_ids, decision) tuples.

        Returns:
            List of (exception_id, transaction_ids, decision) tuples for created exceptions.
        """
        exception_actions = {
            DecisionAction.MANUAL_REVIEW,
            DecisionAction.AMBIGUOUS,
            DecisionAction.UNRESOLVED,
            DecisionAction.REJECT,
        }

        def _to_orm_id(domain_id: str) -> str:
            """Translate domain txn_id to ORM UUID if mapping is available."""
            if txn_orm_ids:
                return txn_orm_ids.get(domain_id, domain_id)
            return domain_id

        results = []
        for decision in decisions:
            if decision.action in exception_actions:
                first_txn_id = _to_orm_id(decision.transaction_ids[0]) if decision.transaction_ids else None
                
                # Derive ground truth category, exposure, explanation, and action
                category = ExceptionCategory.UNEXPLAINED
                explanation = decision.reason
                recommended_action = "escalate_manual"
                exposure = Decimal("0.00")
                confidence = decision.confidence or Decimal("0.50")
                evidence_dict = decision.evidence or {}

                involved_txns = []
                if txn_by_id and decision.transaction_ids:
                    involved_txns = [txn_by_id[tid] for tid in decision.transaction_ids if tid in txn_by_id]

                if involved_txns:
                    max_amt = max(t.amount for t in involved_txns)
                    min_amt = min(t.amount for t in involved_txns)

                    ctx = InvestigationContextBuilder.build(
                        exception_id="temp",
                        run_id=run_id,
                        transactions=involved_txns,
                        decision=decision,
                    )
                    analysis = DeterministicAnalyzer.analyze(ctx.evidence, involved_txns, decision)
                    category = analysis.detected_category
                    explanation = f"{analysis.root_cause}: {analysis.explanation}"
                    recommended_action = analysis.recommended_action
                    confidence = analysis.confidence

                    if category in (ExceptionCategory.FEE_MISMATCH, ExceptionCategory.CURRENCY_ROUNDING, ExceptionCategory.PARTIAL_REFUND):
                        exposure = max_amt - min_amt if max_amt != min_amt else max_amt
                    else:
                        exposure = max_amt
                elif decision.evidence and "amount" in decision.evidence:
                    try:
                        exposure = Decimal(str(decision.evidence["amount"]))
                    except Exception:
                        exposure = Decimal("0.00")

                expected_cost = (exposure * (Decimal("1.0") - confidence)).quantize(Decimal("0.01"))
                if expected_cost == Decimal("0.00") and exposure > Decimal("0.00"):
                    expected_cost = exposure

                exception = ExceptionRecord(
                    transaction_id=first_txn_id,
                    category=category,
                    confidence=confidence,
                    financial_exposure=exposure,
                    expected_cost=expected_cost,
                    explanation=explanation,
                    evidence=evidence_dict,
                    recommended_action=recommended_action,
                )
                exception_id = await self.exception_repo.create(exception, run_id, first_txn_id)
                # Add remaining transaction IDs to the exception
                for txn_id in decision.transaction_ids[1:]:
                    await self.exception_repo.add_transaction_to_exception(exception_id, _to_orm_id(txn_id))
                results.append((exception_id, decision.transaction_ids, decision))

        return results

    async def _run_investigations(
        self,
        run_id: str,
        decisions: list,
        exception_ids: list[tuple[str, list[str], object]],
        txn_by_id: dict,
    ) -> None:
        """Invoke InvestigationService for each escalated exception.

        Only called when self.investigation_service is not None.
        Failures are logged and do not abort the reconciliation run.

        Args:
            run_id: Reconciliation run ID.
            decisions: All decision results (used for lookup; exception_ids already filtered).
            exception_ids: List of (exception_id, transaction_ids, decision) from _create_exceptions_with_ids.
            txn_by_id: Map of txn_id -> Transaction domain object.
        """
        for exception_id, txn_ids, decision in exception_ids:
            if decision.action not in _INVESTIGATION_ACTIONS:
                # REJECT is created as an exception but is not investigated.
                continue
            transactions = [txn_by_id[tid] for tid in txn_ids if tid in txn_by_id]
            try:
                await self.investigation_service.investigate(
                    exception_id=exception_id,
                    run_id=run_id,
                    transactions=transactions,
                    decision=decision,
                )
            except Exception as exc:
                logger.error(
                    "Investigation failed for exception %s (run %s): %s",
                    exception_id,
                    run_id,
                    exc,
                    exc_info=True,
                )

    async def _write_audit_events(
        self, run_id: str, matches: list, decisions: list, txn_orm_ids: dict[str, str] | None = None
    ) -> None:
        """Write audit events for all stages.
        
        Args:
            run_id: Reconciliation run ID
            matches: List of match results
            decisions: List of decision results
            txn_orm_ids: Mapping from domain txn_id to ORM UUID for FK translation
        """
        from app.models.audit_event import AuditEvent

        def _to_orm_id(domain_id: str | None) -> str | None:
            if domain_id is None:
                return None
            if txn_orm_ids:
                return txn_orm_ids.get(domain_id, domain_id)
            return domain_id
        
        # Log matching stage
        for match in matches:
            event = AuditEvent(
                run_id=run_id,
                transaction_id=_to_orm_id(match.transaction_ids[0]) if match.transaction_ids else None,
                stage="matching",
                event="match_created",
                evidence=match.evidence,
            )
            await self.audit_repo.create(event)
        
        # Log decision stage
        for decision in decisions:
            event = AuditEvent(
                run_id=run_id,
                transaction_id=_to_orm_id(decision.transaction_ids[0]) if decision.transaction_ids else None,
                stage="decision",
                event=decision.action.value,
                evidence=decision.evidence,
                decision={"action": decision.action.value, "reason": decision.reason},
            )
            await self.audit_repo.create(event)

    async def _update_run_completion(
        self, run_id: str, deterministic_matches: int, ml_proposals: int, exception_count: int
    ) -> None:
        """Update ReconciliationRun with COMPLETED status and counts.
        
        Args:
            run_id: Reconciliation run ORM ID
            deterministic_matches: Number of deterministic matches
            ml_proposals: Number of ML proposals
            exception_count: Number of exceptions created
        """
        # Get the ORM object
        from app.database.models import ReconciliationRun as ReconciliationRunORM
        from sqlalchemy import select
        
        result = await self.session.execute(
            select(ReconciliationRunORM).where(ReconciliationRunORM.id == run_id)
        )
        orm = result.scalar_one_or_none()
        
        if orm:
            orm.status = "completed"
            orm.completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
            orm.match_count = deterministic_matches + ml_proposals
            orm.exception_count = exception_count
            await self.session.flush()

    def _build_summary(
        self,
        run_id: str,
        total_transactions: int,
        deterministic_matches: int,
        ml_proposals: int,
        decisions: list,
        exceptions_created: int,
        started_at: datetime,
        completed_at: datetime,
    ) -> ReconciliationSummary:
        """Build ReconciliationSummary from execution results.
        
        Args:
            run_id: Reconciliation run ID
            total_transactions: Total number of transactions
            deterministic_matches: Number of deterministic matches
            ml_proposals: Number of ML proposals
            decisions: List of decisions
            exceptions_created: Number of exceptions created
            started_at: Start timestamp
            completed_at: Completion timestamp
            
        Returns:
            ReconciliationSummary
        """
        manual_reviews = sum(1 for d in decisions if d.action == DecisionAction.MANUAL_REVIEW)
        ambiguous = sum(1 for d in decisions if d.action == DecisionAction.AMBIGUOUS)
        unresolved = sum(1 for d in decisions if d.action == DecisionAction.UNRESOLVED)
        rejected = sum(1 for d in decisions if d.action == DecisionAction.REJECT)
        
        return ReconciliationSummary(
            run_id=run_id,
            total_transactions=total_transactions,
            deterministic_matches=deterministic_matches,
            ml_proposals=ml_proposals,
            manual_reviews=manual_reviews,
            ambiguous=ambiguous,
            unresolved=unresolved,
            rejected=rejected,
            exceptions_created=exceptions_created,
            completed_successfully=True,
            started_at=started_at,
            completed_at=completed_at,
        )
