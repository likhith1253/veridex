import logging
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

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
