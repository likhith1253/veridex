"""
Human-in-the-Loop Decision & Exception Workflow Service for Project Sentinel.

Handles human controller actions on reconciliation exceptions:
- approve (confirms tentative proposal or manual match)
- reject (rejects proposed association)
- escalate (escalates to senior treasury/investigation team)
- resolve (marks discrepancy as resolved with credit note / write-off)
- assign (assigns exception to a controller analyst)
- add_note (adds an auditable controller review note)
- investigate (transitions exception to INVESTIGATING status)

Guarantees:
- Strict state transition validation
- Zero silent mutation (every action produces an immutable AuditEvent)
- Records actor, timestamp, previous state, new state, and reason
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    AuditEvent as AuditEventORM,
    Exception as ExceptionORM,
    FinanceAction as FinanceActionORM,
)
from app.database.repositories.audit_repository import AuditRepository
from app.database.repositories.exception_repository import ExceptionRepository
from app.models.audit_event import AuditEvent


class HumanAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"
    RESOLVE = "resolve"
    ASSIGN = "assign"
    ADD_NOTE = "add_note"
    INVESTIGATE = "investigate"


# Allowed state transitions mapping: current_status -> set of allowed actions
ALLOWED_TRANSITIONS = {
    "open": {HumanAction.APPROVE, HumanAction.REJECT, HumanAction.ESCALATE, HumanAction.RESOLVE, HumanAction.ASSIGN, HumanAction.ADD_NOTE, HumanAction.INVESTIGATE},
    "investigating": {HumanAction.APPROVE, HumanAction.REJECT, HumanAction.ESCALATE, HumanAction.RESOLVE, HumanAction.ASSIGN, HumanAction.ADD_NOTE},
    "pending_review": {HumanAction.APPROVE, HumanAction.REJECT, HumanAction.ESCALATE, HumanAction.RESOLVE, HumanAction.ASSIGN, HumanAction.ADD_NOTE, HumanAction.INVESTIGATE},
    "escalated": {HumanAction.APPROVE, HumanAction.REJECT, HumanAction.RESOLVE, HumanAction.ASSIGN, HumanAction.ADD_NOTE},
    "approved": {HumanAction.ADD_NOTE},
    "resolved": {HumanAction.ADD_NOTE},  # Notes allowed on closed items for audit
    "rejected": {HumanAction.ADD_NOTE},
}


@dataclass
class HumanDecisionResult:
    """Result of human decision execution."""
    exception_id: str
    action: str
    actor: str
    previous_status: str
    new_status: str
    reason: Optional[str]
    audit_event_id: str
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class HumanDecisionService:
    """Service governing human actions, validation, and audit recording."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.exc_repo = ExceptionRepository(session)
        self.audit_repo = AuditRepository(session)

    async def apply_decision(
        self,
        exception_id: str,
        action: HumanAction,
        actor: str = "finance_controller_user",
        reason: Optional[str] = None,
        assigned_to: Optional[str] = None,
        note: Optional[str] = None,
    ) -> HumanDecisionResult:
        """Validate and apply a human action on an exception record."""
        # 1. Fetch ORM Exception
        stmt = select(ExceptionORM).where(ExceptionORM.id == exception_id)
        res = await self.session.execute(stmt)
        exc = res.scalar_one_or_none()

        if not exc:
            raise ValueError(f"Exception not found: {exception_id}")

        prev_status = getattr(exc, "status", "open")
        prev_resolved = getattr(exc, "resolved", False)

        if prev_resolved and action not in (HumanAction.ADD_NOTE,):
            raise ValueError(f"Cannot perform action '{action.value}' on already resolved exception '{exception_id}'")

        allowed_actions = ALLOWED_TRANSITIONS.get(prev_status, {HumanAction.RESOLVE, HumanAction.ESCALATE, HumanAction.ADD_NOTE})
        if action not in allowed_actions:
            raise ValueError(
                f"Invalid transition: Action '{action.value}' is not permitted from current status '{prev_status}'"
            )

        # 2. Determine new status & update meta
        evidence_dict = exc.evidence or {}
        now_dt = datetime.now(timezone.utc).replace(tzinfo=None)

        if action == HumanAction.APPROVE:
            new_status = "approved"
            exc.resolved = True
            exc.resolved_at = now_dt
        elif action == HumanAction.REJECT:
            new_status = "rejected"
            exc.resolved = True
            exc.resolved_at = now_dt
        elif action == HumanAction.ESCALATE:
            new_status = "escalated"
            exc.resolved = False
        elif action == HumanAction.RESOLVE:
            new_status = "resolved"
            exc.resolved = True
            exc.resolved_at = now_dt
        elif action == HumanAction.INVESTIGATE:
            new_status = "investigating"
            exc.resolved = False
        elif action == HumanAction.ASSIGN:
            new_status = prev_status
            evidence_dict["assigned_to"] = assigned_to or actor
            exc.evidence = evidence_dict
        elif action == HumanAction.ADD_NOTE:
            new_status = prev_status
            notes = evidence_dict.get("controller_notes", [])
            notes.append({"actor": actor, "note": note or reason, "timestamp": now_dt.isoformat()})
            evidence_dict["controller_notes"] = notes
            exc.evidence = evidence_dict
        else:
            new_status = action.value

        exc.status = new_status
        await self.session.flush()

        # Synchronize associated finance actions if resolving, approving, or rejecting
        if action in (HumanAction.RESOLVE, HumanAction.APPROVE):
            stmt_act = select(FinanceActionORM).where(
                FinanceActionORM.entity_id == exception_id,
                FinanceActionORM.state.in_(["PENDING_APPROVAL", "APPROVED"]),
            )
            linked_actions = (await self.session.execute(stmt_act)).scalars().all()
            for act in linked_actions:
                act.state = "EXECUTED"
                act.executed_by = actor
                act.execution_result = {
                    "resolution": f"Exception marked {new_status} by {actor}",
                    "reason": reason,
                }
                act.updated_at = now_dt
        elif action == HumanAction.REJECT:
            stmt_act = select(FinanceActionORM).where(
                FinanceActionORM.entity_id == exception_id,
                FinanceActionORM.state.in_(["PENDING_APPROVAL", "APPROVED"]),
            )
            linked_actions = (await self.session.execute(stmt_act)).scalars().all()
            for act in linked_actions:
                act.state = "REJECTED"
                act.rejected_by = actor
                act.decision_reason = reason
                act.updated_at = now_dt

        # 3. Emit immutable AuditEvent
        txn_id = getattr(exc, "transaction_id", "unknown_txn")
        audit_domain = AuditEvent(
            run_id=getattr(exc, "run_id", "manual_run"),
            stage="human_decision",
            event=f"HUMAN_DECISION_{action.value.upper()}",
            transaction_id=txn_id,
            evidence={
                "exception_id": exception_id,
                "actor": actor,
                "action": action.value,
                "previous_status": prev_status,
                "new_status": new_status,
                "reason": reason or note or "Applied by Finance Controller",
                "assigned_to": assigned_to,
            },
            timestamp=now_dt,
        )
        audit_id = await self.audit_repo.create(audit_domain)
        await self.session.commit()

        return HumanDecisionResult(
            exception_id=exception_id,
            action=action.value,
            actor=actor,
            previous_status=prev_status,
            new_status=new_status,
            reason=reason or note,
            audit_event_id=audit_id,
            timestamp=now_dt.isoformat(),
        )
