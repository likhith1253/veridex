from datetime import datetime, timezone
from decimal import Decimal
import logging
from typing import Any, Optional
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    AuditEvent as AuditEventORM,
    Exception as ExceptionORM,
    FinanceAction as FinanceActionORM,
    Match as MatchORM,
    ReconciliationRun as ReconciliationRunORM,
    Transaction as TransactionORM,
)
from app.database.models.finance_action import ActionLifecycleState, FinanceActionType
from app.database.repositories.audit_repository import AuditRepository
from app.database.utils import ensure_run_exists, utcnow
from app.models.audit_event import AuditEvent as AuditDomain

logger = logging.getLogger(__name__)

MAX_POST_ADJUSTMENT_LIMIT = Decimal("5000.00")
MAX_WRITE_OFF_LIMIT = Decimal("100.00")
MAX_BOUNDED_TRANSACTION_LIMIT = Decimal("500000.00")

NON_HUMAN_ACTORS = {"ai", "ai_agent", "system", "llm", "automated", "bot"}


class PolicyViolationError(ValueError):
    """Raised when an action violates safety or human-in-the-loop policies."""
    pass


class FinanceActionService:
    """Manages policy-gated finance action lifecycle with mandatory human approval."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.audit_repo = AuditRepository(session)

    async def _resolve_run_id(self, preferred_run_id: Optional[str] = None) -> str:
        """Resolve a valid run_id for foreign key constraints."""
        if preferred_run_id:
            await ensure_run_exists(self.session, preferred_run_id)
            return preferred_run_id
        
        stmt = select(ReconciliationRunORM.id).limit(1)
        res = await self.session.execute(stmt)
        existing_run_id = res.scalars().first()
        if existing_run_id:
            return existing_run_id
            
        fallback_id = f"run_action_{uuid.uuid4().hex[:12]}"
        await ensure_run_exists(self.session, fallback_id)
        return fallback_id

    async def recommend_action(
        self,
        entity_type: str,
        entity_id: str,
        action_type: FinanceActionType,
        amount: Decimal,
        currency: str,
        recommended_by: str,
        recommendation_reason: str,
        evidence: Optional[dict[str, Any]] = None,
        run_id: Optional[str] = None,
    ) -> FinanceActionORM:
        """Create a recommended financial action and submit it for explicit approval.
        
        Lifecycle: DETECTED -> INVESTIGATING -> RECOMMENDED -> PENDING_APPROVAL
        """
        # 1. Enforce strict monetary bounds (no unrestricted money movement)
        if amount < Decimal("0.00"):
            raise PolicyViolationError("Negative action amounts are prohibited.")

        if action_type == FinanceActionType.POST_ADJUSTMENT and amount > MAX_POST_ADJUSTMENT_LIMIT:
            raise PolicyViolationError(
                f"Adjustment amount INR {amount} exceeds policy bound limit of INR {MAX_POST_ADJUSTMENT_LIMIT}."
            )
        if action_type == FinanceActionType.WRITE_OFF and amount > MAX_WRITE_OFF_LIMIT:
            raise PolicyViolationError(
                f"Write-off amount INR {amount} exceeds policy bound limit of INR {MAX_WRITE_OFF_LIMIT}."
            )
        if amount > MAX_BOUNDED_TRANSACTION_LIMIT:
            raise PolicyViolationError(
                f"Action amount INR {amount} exceeds maximum system ceiling of INR {MAX_BOUNDED_TRANSACTION_LIMIT}."
            )

        resolved_run_id = await self._resolve_run_id(run_id)
        action_id = f"act_{uuid.uuid4().hex[:16]}"
        now = utcnow()

        # Action is created in PENDING_APPROVAL after automated investigation/recommendation
        action_orm = FinanceActionORM(
            id=action_id,
            run_id=resolved_run_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action_type=action_type.value if hasattr(action_type, "value") else str(action_type),
            state=ActionLifecycleState.PENDING_APPROVAL.value,
            amount=amount,
            currency=currency,
            recommended_by=recommended_by,
            recommendation_reason=recommendation_reason,
            evidence=evidence or {},
            requested_by=recommended_by,
            created_at=now,
            updated_at=now,
        )
        self.session.add(action_orm)
        await self.session.flush()

        # Record audit trail
        await self.audit_repo.create(
            AuditDomain(
                run_id=resolved_run_id,
                transaction_id=None,
                stage="FINANCE_ACTION",
                event="ACTION_RECOMMENDED",
                evidence={
                    "action_id": action_id,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "action_type": action_orm.action_type,
                    "amount": str(amount),
                    "recommended_by": recommended_by,
                    "reason": recommendation_reason,
                    "state": action_orm.state,
                },
            )
        )
        await self.session.commit()
        return action_orm

    async def approve_action(
        self,
        action_id: str,
        actor: str,
        reason: str,
    ) -> FinanceActionORM:
        """Explicit human approval for a pending finance action.
        
        AI can recommend, but cannot independently approve or execute a financial action.
        """
        if not actor or actor.strip().lower() in NON_HUMAN_ACTORS:
            raise PolicyViolationError(
                "AI cannot independently approve financial actions; explicit human authorization is required."
            )

        stmt = select(FinanceActionORM).where(FinanceActionORM.id == action_id)
        res = await self.session.execute(stmt)
        action = res.scalar_one_or_none()
        if not action:
            raise ValueError(f"Finance action '{action_id}' not found.")

        if action.state != ActionLifecycleState.PENDING_APPROVAL.value:
            raise PolicyViolationError(
                f"Action cannot be approved from state '{action.state}'. Expected 'PENDING_APPROVAL'."
            )

        now = utcnow()
        action.state = ActionLifecycleState.APPROVED.value
        action.approved_by = actor.strip()
        action.decision_reason = reason.strip()
        action.updated_at = now
        await self.session.flush()

        # Audit trail
        await self.audit_repo.create(
            AuditDomain(
                run_id=action.run_id,
                transaction_id=None,
                stage="FINANCE_ACTION",
                event="ACTION_APPROVED",
                evidence={
                    "action_id": action.id,
                    "actor": actor,
                    "reason": reason,
                    "amount": str(action.amount),
                    "action_type": action.action_type,
                    "state": action.state,
                },
                decision={
                    "decision": "APPROVED",
                    "approver": actor,
                    "reason": reason,
                },
            )
        )
        await self.session.commit()
        return action

    async def reject_action(
        self,
        action_id: str,
        actor: str,
        reason: str,
    ) -> FinanceActionORM:
        """Explicit human rejection of a pending finance action."""
        if not actor or actor.strip().lower() in NON_HUMAN_ACTORS:
            raise PolicyViolationError(
                "AI cannot independently reject financial actions; human authorization is required."
            )

        stmt = select(FinanceActionORM).where(FinanceActionORM.id == action_id)
        res = await self.session.execute(stmt)
        action = res.scalar_one_or_none()
        if not action:
            raise ValueError(f"Finance action '{action_id}' not found.")

        if action.state != ActionLifecycleState.PENDING_APPROVAL.value:
            raise PolicyViolationError(
                f"Action cannot be rejected from state '{action.state}'. Expected 'PENDING_APPROVAL'."
            )

        now = utcnow()
        action.state = ActionLifecycleState.REJECTED.value
        action.rejected_by = actor.strip()
        action.decision_reason = reason.strip()
        action.updated_at = now
        await self.session.flush()

        # Audit trail
        await self.audit_repo.create(
            AuditDomain(
                run_id=action.run_id,
                transaction_id=None,
                stage="FINANCE_ACTION",
                event="ACTION_REJECTED",
                evidence={
                    "action_id": action.id,
                    "actor": actor,
                    "reason": reason,
                    "action_type": action.action_type,
                    "state": action.state,
                },
                decision={
                    "decision": "REJECTED",
                    "actor": actor,
                    "reason": reason,
                },
            )
        )
        await self.session.commit()
        return action

    async def execute_action(
        self,
        action_id: str,
        actor: str,
    ) -> FinanceActionORM:
        """Execute an approved bounded financial action.
        
        AI can recommend, but cannot independently execute a financial action.
        Approval must be explicit.
        """
        if not actor or actor.strip().lower() in NON_HUMAN_ACTORS:
            raise PolicyViolationError(
                "AI cannot independently execute a financial action; human execution is required."
            )

        stmt = select(FinanceActionORM).where(FinanceActionORM.id == action_id)
        res = await self.session.execute(stmt)
        action = res.scalar_one_or_none()
        if not action:
            raise ValueError(f"Finance action '{action_id}' not found.")

        if action.state != ActionLifecycleState.APPROVED.value:
            raise PolicyViolationError(
                f"Action must be in APPROVED state to execute. Current state: '{action.state}'."
            )

        now = utcnow()

        # Bounded Execution Handlers
        try:
            execution_details: dict[str, Any] = {
                "executed_by": actor,
                "executed_at": now.isoformat(),
            }

            if action.action_type == FinanceActionType.RECONCILE_MATCH.value:
                # Resolve exception if target is exception
                stmt_exc = select(ExceptionORM).where(ExceptionORM.id == action.entity_id)
                exc = (await self.session.execute(stmt_exc)).scalar_one_or_none()
                if exc:
                    exc.resolved = True
                    exc.status = "resolved"
                    exc.resolved_at = now
                    execution_details["exception_resolved"] = exc.id

            elif action.action_type == FinanceActionType.POST_ADJUSTMENT.value:
                if action.amount > MAX_POST_ADJUSTMENT_LIMIT:
                    raise PolicyViolationError(f"Adjustment amount exceeds limit INR {MAX_POST_ADJUSTMENT_LIMIT}")
                execution_details["posted_adjustment_amount"] = str(action.amount)
                execution_details["ledger_note"] = f"Bounded variance adjustment of INR {action.amount} posted by {actor}"

            elif action.action_type == FinanceActionType.WRITE_OFF.value:
                if action.amount > MAX_WRITE_OFF_LIMIT:
                    raise PolicyViolationError(f"Write-off amount exceeds limit INR {MAX_WRITE_OFF_LIMIT}")
                execution_details["write_off_amount"] = str(action.amount)
                execution_details["resolution_note"] = f"Immaterial variance written off by {actor}"

            elif action.action_type == FinanceActionType.INITIATE_INQUIRY.value:
                execution_details["inquiry_status"] = "SUBMITTED"
                execution_details["inquiry_reference"] = f"INQ-{uuid.uuid4().hex[:8].upper()}"

            elif action.action_type == FinanceActionType.FLAG_INVESTIGATION.value:
                execution_details["flagged"] = True
                execution_details["flag_priority"] = "HIGH"

            else:
                raise PolicyViolationError(f"Unsupported action type '{action.action_type}' for execution.")

            action.state = ActionLifecycleState.EXECUTED.value
            action.execution_result = execution_details
            action.updated_at = now
            await self.session.flush()

            # Record audit event
            await self.audit_repo.create(
                AuditDomain(
                    run_id=action.run_id,
                    transaction_id=None,
                    stage="FINANCE_ACTION",
                    event="ACTION_EXECUTED",
                    evidence={
                        "action_id": action.id,
                        "actor": actor,
                        "action_type": action.action_type,
                        "amount": str(action.amount),
                        "result": execution_details,
                    },
                )
            )
            await self.session.commit()
            return action

        except Exception as exc:
            action.state = ActionLifecycleState.FAILED.value
            action.error_message = str(exc)
            action.updated_at = now
            await self.session.flush()

            # Record failure in audit
            await self.audit_repo.create(
                AuditDomain(
                    run_id=action.run_id,
                    transaction_id=None,
                    stage="FINANCE_ACTION",
                    event="ACTION_EXECUTION_FAILED",
                    evidence={
                        "action_id": action.id,
                        "actor": actor,
                        "action_type": action.action_type,
                        "error": str(exc),
                    },
                )
            )
            await self.session.commit()
            return action

    async def get_action(self, action_id: str) -> Optional[FinanceActionORM]:
        """Fetch a finance action by ID."""
        stmt = select(FinanceActionORM).where(FinanceActionORM.id == action_id)
        res = await self.session.execute(stmt)
        return res.scalar_one_or_none()

    async def list_actions(
        self,
        state: Optional[str] = None,
        entity_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        limit: int = 50,
    ) -> list[FinanceActionORM]:
        """List finance actions matching criteria."""
        stmt = select(FinanceActionORM)
        if state:
            stmt = stmt.where(FinanceActionORM.state == state.upper())
        if entity_id:
            stmt = stmt.where(FinanceActionORM.entity_id == entity_id)
        if entity_type:
            stmt = stmt.where(FinanceActionORM.entity_type == entity_type)
        stmt = stmt.order_by(FinanceActionORM.created_at.desc()).limit(limit)
        res = await self.session.execute(stmt)
        return list(res.scalars().all())
