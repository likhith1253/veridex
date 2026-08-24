"""
Human-in-the-Loop Decision Service for Project Sentinel.

Handles human controller actions on reconciliation exceptions:
- approve (confirms tentative proposal or manual match)
- reject (rejects proposed association)
- escalate (escalates to senior treasury/investigation team)
- resolve (marks discrepancy as resolved with credit note / write-off)

Guarantees:
- Strict state transition validation
- Zero silent mutation (every action produces an immutable AuditEvent)
- Records actor, timestamp, previous state, new state, and reason
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AuditEvent as AuditEventORM, Exception as ExceptionORM
from app.database.repositories.audit_repository import AuditRepository
from app.database.repositories.exception_repository import ExceptionRepository
from app.models.audit_event import AuditEvent


class HumanAction(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"
    RESOLVE = "resolve"


# Allowed state transitions mapping: current_status -> set of allowed actions
ALLOWED_TRANSITIONS = {
    "open": {HumanAction.APPROVE, HumanAction.REJECT, HumanAction.ESCALATE, HumanAction.RESOLVE},
    "pending_review": {HumanAction.APPROVE, HumanAction.REJECT, HumanAction.ESCALATE, HumanAction.RESOLVE},
    "escalated": {HumanAction.APPROVE, HumanAction.REJECT, HumanAction.RESOLVE},
    "resolved": set(),  # Terminal state
    "rejected": set(),  # Terminal state
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

        if prev_resolved:
            raise ValueError(f"Cannot perform action '{action.value}' on already resolved exception '{exception_id}'")

        allowed_actions = ALLOWED_TRANSITIONS.get(prev_status, {HumanAction.RESOLVE, HumanAction.ESCALATE})
        if action not in allowed_actions:
            raise ValueError(
                f"Invalid transition: Action '{action.value}' is not permitted from current status '{prev_status}'"
            )

        # 2. Determine new status
        if action == HumanAction.APPROVE:
            new_status = "approved"
            exc.resolved = True
        elif action == HumanAction.REJECT:
            new_status = "rejected"
            exc.resolved = True
        elif action == HumanAction.ESCALATE:
            new_status = "escalated"
            exc.resolved = False
        elif action == HumanAction.RESOLVE:
            new_status = "resolved"
            exc.resolved = True
        else:
            new_status = action.value

        exc.status = new_status
        await self.session.flush()

        # 3. Emit immutable AuditEvent
        txn_id = getattr(exc, "transaction_id", "unknown_txn")
        now_dt = datetime.now(timezone.utc)

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
                "reason": reason or "Applied by Finance Controller",
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
            reason=reason,
            audit_event_id=audit_id,
            timestamp=now_dt.isoformat(),
        )
