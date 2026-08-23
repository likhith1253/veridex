from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

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
from app.matching.ml_scorer import MLScorer
from app.models.decision_result import DecisionAction
from app.models.exception_record import ExceptionCategory, ExceptionRecord
from app.models.reconciliation_summary import ReconciliationSummary
from app.models.transaction import Transaction, TransactionSource


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
        """
        self.session = session
        self.transaction_repo = transaction_repo
        self.reconciliation_repo = reconciliation_repo
        self.match_repo = match_repo
        self.decision_repo = decision_repo
        self.exception_repo = exception_repo
        self.audit_repo = audit_repo
        self.ml_scorer = ml_scorer

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
            persisted_txns = await self._persist_transactions(transactions_by_source)
            
            # Create ReconciliationItems for all transactions
            await self._create_reconciliation_items(run_orm_id, persisted_txns)
            
            # Run DeterministicMatcher
            matcher = DeterministicMatcher(transactions_by_source)
            deterministic_matches = matcher.match_all()
            
            # Track matched transaction IDs
            matched_txn_ids = set()
            for match in deterministic_matches:
                matched_txn_ids.update(match.transaction_ids)
            
            # For unresolved transactions, run CandidateGenerator + MLScorer
            unresolved_txns = self._get_unresolved_transactions(persisted_txns, matched_txn_ids)
            ml_matches = []
            if unresolved_txns and self.ml_scorer:
                ml_matches = await self._run_ml_scoring(unresolved_txns, transactions_by_source)
            
            # Combine all matches
            all_matches = deterministic_matches + ml_matches
            
            # Run DecisionPolicy for all candidates
            decision_policy = DecisionPolicy()
            decisions = await self._make_decisions(all_matches, transactions_by_source, decision_policy)
            
            # Persist matches via MatchRepository
            match_ids = []
            for match in all_matches:
                match_id = await self.match_repo.create(match, run_orm_id)
                match_ids.append(match_id)
            
            # Persist decisions via DecisionRepository
            for decision, match_id in zip(decisions, match_ids):
                await self.decision_repo.create(decision, run_orm_id, match_id)
            
            # Create exceptions for MANUAL_REVIEW, AMBIGUOUS, UNRESOLVED, REJECT
            exception_count = await self._create_exceptions(decisions, run_orm_id)
            
            # Write audit events for all stages
            await self._write_audit_events(run_orm_id, all_matches, decisions)
            
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
            # Mark run as FAILED on exception
            await self.reconciliation_repo.update_run_status(run_orm_id, "failed")
            raise

    async def _persist_transactions(
        self, transactions_by_source: dict[TransactionSource, list[Transaction]]
    ) -> dict[str, Transaction]:
        """Persist transactions, reusing existing if same source+domain_id.
        
        Args:
            transactions_by_source: Transactions grouped by source
            
        Returns:
            Dict mapping txn_id to persisted Transaction
        """
        persisted = {}
        
        for source, txns in transactions_by_source.items():
            for txn in txns:
                # Check if transaction already exists
                existing = await self.transaction_repo.get_by_source_and_domain_id(
                    source.value, txn.txn_id
                )
                if existing:
                    persisted[txn.txn_id] = existing
                else:
                    txn_id = await self.transaction_repo.create(txn)
                    persisted[txn.txn_id] = txn
        
        return persisted

    async def _create_reconciliation_items(
        self, run_id: str, transactions: dict[str, Transaction]
    ) -> None:
        """Create ReconciliationItems for all transactions.
        
        Args:
            run_id: Reconciliation run ID
            transactions: Dict mapping txn_id to Transaction
        """
        for txn_id, txn in transactions.items():
            await self.reconciliation_repo.create_item(run_id, txn_id, "pending")

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
    ) -> list:
        """Run ML scoring on unresolved transactions.
        
        Args:
            unresolved_txns: List of unmatched transactions
            transactions_by_source: All transactions grouped by source
            
        Returns:
            List of ML-generated match results
        """
        # Placeholder for ML scoring
        # In a full implementation, this would:
        # 1. Generate candidates using CandidateGenerator
        # 2. Extract features using FeatureExtractor
        # 3. Score using MLScorer
        # 4. Return scored candidates as MatchResult objects
        
        # For now, return empty list as ML scoring is not fully integrated
        return []

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
                    # For deterministic matches, use high confidence
                    if match.confidence >= Decimal("0.95"):
                        decision = decision_policy.evaluate_deterministic(match)
                    else:
                        # For ML matches, would use ml_probability
                        # For now, use match confidence as proxy
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
        exception_actions = {
            DecisionAction.MANUAL_REVIEW,
            DecisionAction.AMBIGUOUS,
            DecisionAction.UNRESOLVED,
            DecisionAction.REJECT,
        }
        
        count = 0
        for decision in decisions:
            if decision.action in exception_actions:
                for txn_id in decision.transaction_ids:
                    exception = ExceptionRecord(
                        transaction_id=txn_id,
                        category=ExceptionCategory.UNEXPLAINED,
                        confidence=decision.confidence,
                        financial_exposure=Decimal("0"),  # Would be calculated from transaction amount
                        expected_cost=Decimal("0"),  # Would be calculated based on risk
                        explanation=decision.reason,
                        evidence=decision.evidence,
                        recommended_action=None,
                    )
                    await self.exception_repo.create(exception, run_id, txn_id)
                    count += 1
        
        return count

    async def _write_audit_events(self, run_id: str, matches: list, decisions: list) -> None:
        """Write audit events for all stages.
        
        Args:
            run_id: Reconciliation run ID
            matches: List of match results
            decisions: List of decision results
        """
        from app.models.audit_event import AuditEvent
        
        # Log matching stage
        for match in matches:
            event = AuditEvent(
                run_id=run_id,
                transaction_id=match.transaction_ids[0] if match.transaction_ids else None,
                stage="matching",
                event="match_created",
                evidence=match.evidence,
            )
            await self.audit_repo.create(event)
        
        # Log decision stage
        for decision in decisions:
            event = AuditEvent(
                run_id=run_id,
                transaction_id=decision.transaction_ids[0] if decision.transaction_ids else None,
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
            orm.completed_at = datetime.now(timezone.utc)
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
