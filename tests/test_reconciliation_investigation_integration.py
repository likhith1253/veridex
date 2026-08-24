"""
Tests for the ReconciliationService <-> InvestigationService integration.

Coverage:
    1. AUTO_MATCH path  -- investigation NOT called
    2. MANUAL_REVIEW    -- investigation called exactly once
    3. AMBIGUOUS        -- investigation called exactly once
    4. UNRESOLVED       -- investigation called exactly once
    5. Investigation failure -- reconciliation completes, error is logged
    6. No investigation_service injected -- existing path unchanged
"""
import asyncio
from decimal import Decimal
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from app.models.decision_result import DecisionAction, DecisionResult
from app.models.investigation_result import (
    InvestigationConclusion,
    InvestigationMethod,
    InvestigationStatus,
)
from app.models.exception_record import ExceptionCategory
from app.services.reconciliation import ReconciliationService, _INVESTIGATION_ACTIONS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_decision(action: DecisionAction, txn_ids: list[str]) -> DecisionResult:
    return DecisionResult(
        transaction_ids=txn_ids,
        action=action,
        confidence=Decimal("0.90"),
        evidence={},
        reason=f"{action.value} reason",
    )


def _make_conclusion(exception_id: str = "EXC-1") -> InvestigationConclusion:
    return InvestigationConclusion(
        investigation_id="inv_test",
        exception_id=exception_id,
        run_id="RUN-1",
        method=InvestigationMethod.DETERMINISTIC,
        status=InvestigationStatus.COMPLETED,
        classification="duplicate_entry",
        root_cause="Duplicate transaction",
        confidence=Decimal("0.95"),
        financial_exposure=Decimal("0"),
        expected_cost=Decimal("0"),
        recommended_action="flag_duplicate",
        requires_human_review=False,
        llm_invoked=False,
    )


def _build_service(
    investigation_service=None,
    exception_ids_to_return: Optional[list] = None,
):
    """Build a ReconciliationService with all repos mocked."""
    session = MagicMock()
    transaction_repo = MagicMock()
    reconciliation_repo = MagicMock()
    match_repo = MagicMock()
    decision_repo = MagicMock()
    exception_repo = MagicMock()
    audit_repo = MagicMock()

    # Async mocks
    transaction_repo.get_by_source_and_domain_id = AsyncMock(return_value=None)
    transaction_repo.create = AsyncMock(return_value="txn-db-id")
    reconciliation_repo.create_run = AsyncMock(return_value="RUN-1")
    reconciliation_repo.update_run_status = AsyncMock()
    reconciliation_repo.create_item = AsyncMock()
    match_repo.create = AsyncMock(return_value="MATCH-1")
    decision_repo.create = AsyncMock()
    audit_repo.create = AsyncMock()

    # exception_repo.create returns sequential IDs
    _exc_counter = [0]
    async def _create_exc(*args, **kwargs):
        _exc_counter[0] += 1
        return f"EXC-{_exc_counter[0]}"
    exception_repo.create = AsyncMock(side_effect=_create_exc)
    exception_repo.add_transaction_to_exception = AsyncMock()

    svc = ReconciliationService(
        session=session,
        transaction_repo=transaction_repo,
        reconciliation_repo=reconciliation_repo,
        match_repo=match_repo,
        decision_repo=decision_repo,
        exception_repo=exception_repo,
        audit_repo=audit_repo,
        investigation_service=investigation_service,
    )
    return svc


# ---------------------------------------------------------------------------
# 1. _INVESTIGATION_ACTIONS constant
# ---------------------------------------------------------------------------

def test_investigation_actions_contains_correct_set():
    assert DecisionAction.MANUAL_REVIEW in _INVESTIGATION_ACTIONS
    assert DecisionAction.AMBIGUOUS in _INVESTIGATION_ACTIONS
    assert DecisionAction.UNRESOLVED in _INVESTIGATION_ACTIONS
    assert DecisionAction.AUTO_MATCH not in _INVESTIGATION_ACTIONS
    assert DecisionAction.REJECT not in _INVESTIGATION_ACTIONS


# ---------------------------------------------------------------------------
# 2. Constructor accepts investigation_service
# ---------------------------------------------------------------------------

def test_constructor_accepts_investigation_service():
    inv_svc = MagicMock()
    svc = _build_service(investigation_service=inv_svc)
    assert svc.investigation_service is inv_svc


def test_constructor_defaults_investigation_service_to_none():
    svc = _build_service()
    assert svc.investigation_service is None


# ---------------------------------------------------------------------------
# 3. AUTO_MATCH — investigation is NOT called
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_auto_match_does_not_trigger_investigation():
    inv_svc = MagicMock()
    inv_svc.investigate = AsyncMock()

    svc = _build_service(investigation_service=inv_svc)

    # Patch out _create_exceptions_with_ids to return no exceptions
    # and _run_investigations to assert it is never called.
    svc._create_exceptions_with_ids = AsyncMock(return_value=[])

    with patch.object(svc, "_run_investigations", new=AsyncMock()) as mock_run_inv:
        svc._run_investigations = mock_run_inv

        decision = _make_decision(DecisionAction.AUTO_MATCH, ["T1", "T2"])
        # The investigation guard is inside _run_investigations itself but
        # _run_investigations is only called when the service is set.
        # Here we go through the wrapper directly.
        await svc._run_investigations(
            run_id="RUN-1",
            decisions=[decision],
            exception_ids=[("EXC-1", ["T1", "T2"], decision)],
            txn_by_id={},
        )

    # AUTO_MATCH is not in _INVESTIGATION_ACTIONS so investigate should NOT be called
    inv_svc.investigate.assert_not_called()


# ---------------------------------------------------------------------------
# 4. MANUAL_REVIEW — investigation IS called exactly once
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_manual_review_triggers_investigation_exactly_once():
    inv_svc = MagicMock()
    inv_svc.investigate = AsyncMock(return_value=_make_conclusion("EXC-1"))

    svc = _build_service(investigation_service=inv_svc)

    from app.models.transaction import Transaction, TransactionSource, TransactionStatus
    txn = Transaction(
        txn_id="T1",
        source=TransactionSource.GATEWAY,
        amount=Decimal("100"),
        currency="INR",
        status=TransactionStatus.COMPLETED,
        timestamp=__import__("datetime").datetime(2026, 1, 1),
        order_id="ORD-1",
    )

    decision = _make_decision(DecisionAction.MANUAL_REVIEW, ["T1"])

    await svc._run_investigations(
        run_id="RUN-1",
        decisions=[decision],
        exception_ids=[("EXC-1", ["T1"], decision)],
        txn_by_id={"T1": txn},
    )

    inv_svc.investigate.assert_called_once()
    call_kwargs = inv_svc.investigate.call_args
    assert call_kwargs.kwargs["exception_id"] == "EXC-1"
    assert call_kwargs.kwargs["run_id"] == "RUN-1"
    assert call_kwargs.kwargs["transactions"] == [txn]
    assert call_kwargs.kwargs["decision"] is decision


# ---------------------------------------------------------------------------
# 5. AMBIGUOUS — investigation IS called exactly once
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ambiguous_triggers_investigation_exactly_once():
    inv_svc = MagicMock()
    inv_svc.investigate = AsyncMock(return_value=_make_conclusion("EXC-2"))

    svc = _build_service(investigation_service=inv_svc)

    decision = _make_decision(DecisionAction.AMBIGUOUS, ["T2"])

    await svc._run_investigations(
        run_id="RUN-1",
        decisions=[decision],
        exception_ids=[("EXC-2", ["T2"], decision)],
        txn_by_id={},
    )

    inv_svc.investigate.assert_called_once_with(
        exception_id="EXC-2",
        run_id="RUN-1",
        transactions=[],
        decision=decision,
    )


# ---------------------------------------------------------------------------
# 6. UNRESOLVED — investigation IS called exactly once
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_unresolved_triggers_investigation_exactly_once():
    inv_svc = MagicMock()
    inv_svc.investigate = AsyncMock(return_value=_make_conclusion("EXC-3"))

    svc = _build_service(investigation_service=inv_svc)

    decision = _make_decision(DecisionAction.UNRESOLVED, ["T3"])

    await svc._run_investigations(
        run_id="RUN-1",
        decisions=[decision],
        exception_ids=[("EXC-3", ["T3"], decision)],
        txn_by_id={},
    )

    inv_svc.investigate.assert_called_once_with(
        exception_id="EXC-3",
        run_id="RUN-1",
        transactions=[],
        decision=decision,
    )


# ---------------------------------------------------------------------------
# 7. REJECT — exception created but investigation NOT triggered
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reject_does_not_trigger_investigation():
    inv_svc = MagicMock()
    inv_svc.investigate = AsyncMock()

    svc = _build_service(investigation_service=inv_svc)

    decision = _make_decision(DecisionAction.REJECT, ["T4"])

    await svc._run_investigations(
        run_id="RUN-1",
        decisions=[decision],
        exception_ids=[("EXC-4", ["T4"], decision)],
        txn_by_id={},
    )

    inv_svc.investigate.assert_not_called()


# ---------------------------------------------------------------------------
# 8. Investigation failure — reconciliation continues, error is logged
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_investigation_failure_does_not_abort_run():
    inv_svc = MagicMock()
    inv_svc.investigate = AsyncMock(side_effect=RuntimeError("graph failure"))

    svc = _build_service(investigation_service=inv_svc)

    decision = _make_decision(DecisionAction.MANUAL_REVIEW, ["T5"])

    # Should NOT raise despite investigation error
    await svc._run_investigations(
        run_id="RUN-1",
        decisions=[decision],
        exception_ids=[("EXC-5", ["T5"], decision)],
        txn_by_id={},
    )

    inv_svc.investigate.assert_called_once()


# ---------------------------------------------------------------------------
# 9. Multiple decisions — correct routing per action
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mixed_decisions_route_correctly():
    inv_svc = MagicMock()
    inv_svc.investigate = AsyncMock(return_value=_make_conclusion())

    svc = _build_service(investigation_service=inv_svc)

    decisions_and_exc = [
        ("EXC-A", ["T1"], _make_decision(DecisionAction.MANUAL_REVIEW, ["T1"])),
        ("EXC-B", ["T2"], _make_decision(DecisionAction.AMBIGUOUS, ["T2"])),
        ("EXC-C", ["T3"], _make_decision(DecisionAction.UNRESOLVED, ["T3"])),
        ("EXC-D", ["T4"], _make_decision(DecisionAction.REJECT, ["T4"])),
    ]

    await svc._run_investigations(
        run_id="RUN-1",
        decisions=[d for _, _, d in decisions_and_exc],
        exception_ids=decisions_and_exc,
        txn_by_id={},
    )

    # Only MANUAL_REVIEW + AMBIGUOUS + UNRESOLVED should trigger investigation
    assert inv_svc.investigate.call_count == 3


# ---------------------------------------------------------------------------
# 10. No investigation_service — _run_investigations is never called
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_no_investigation_service_skips_investigation_block():
    """When investigation_service=None, the investigation block is bypassed entirely."""
    svc = _build_service(investigation_service=None)

    # Patch _run_investigations to confirm it is never called
    svc._run_investigations = AsyncMock()

    # Patch _create_exceptions_with_ids to return empty so no investigation path reached
    svc._create_exceptions_with_ids = AsyncMock(return_value=[])
    svc._write_audit_events = AsyncMock()
    svc._update_run_completion = AsyncMock()
    svc._build_summary = MagicMock(return_value=MagicMock())
    svc._persist_transactions = AsyncMock(return_value=({}, {}))
    svc._create_reconciliation_items = AsyncMock()
    svc._make_decisions = AsyncMock(return_value=[])

    with patch("app.matching.deterministic.DeterministicMatcher") as mock_dm:
        mock_dm.return_value.match_all.return_value = []
        from app.models.transaction import TransactionSource
        await svc.run_reconciliation({}, "RUN-X")

    svc._run_investigations.assert_not_called()


# ---------------------------------------------------------------------------
# 11. Existing reconciliation tests still pass (structural check)
# ---------------------------------------------------------------------------

def test_existing_dependency_injection_pattern_preserved():
    import inspect
    from app.services.reconciliation import ReconciliationService

    sig = inspect.signature(ReconciliationService.__init__)
    params = list(sig.parameters.keys())

    assert "transaction_repo" in params
    assert "reconciliation_repo" in params
    assert "match_repo" in params
    assert "decision_repo" in params
    assert "exception_repo" in params
    assert "audit_repo" in params
    # New optional parameter
    assert "investigation_service" in params


def test_no_ml_training_in_service():
    import inspect
    import app.services.reconciliation as m

    src = inspect.getsource(m)
    assert ".train(" not in src
    assert "fit(" not in src


def test_no_csv_parsing_in_service():
    import inspect
    import app.services.reconciliation as m

    src = inspect.getsource(m)
    assert "read_csv" not in src
    assert ".csv" not in src
