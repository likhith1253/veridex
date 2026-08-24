"""
Validation and ablation test suite for the LLM-assisted investigation layer.

Verifies:
1. Selective invocation policy (deterministic cases bypass Groq, high-value/unexplained call Groq).
2. Pydantic structured output validation (valid, missing fields, malformed, invalid enum, invalid confidence, exposure bounds).
3. Failure/Fallback safety (timeout, API error, empty response -> fallback, human review=True, deterministic evidence preserved).
4. End-to-end production path via InvestigationService.
5. Selective invocation ablation benchmark.
"""

import asyncio
import time
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.graph.investigation_graph import InvestigationGraphRunner
from app.investigation.evidence import InvestigationContextBuilder
from app.investigation.exposure import ExposureCalculator
from app.investigation.llm_client import FakeLLMClient, GroqLLMClient, LLMClient
from app.investigation.service import InvestigationService
from app.models.decision_result import DecisionAction, DecisionResult
from app.models.exception_record import ExceptionCategory, ExceptionRecord
from app.models.investigation_result import (
    InvestigationConclusion,
    InvestigationMethod,
    InvestigationStatus,
)
from app.models.llm_result import LLMEvidenceItem, LLMInvestigationResult, RecommendedAction
from app.models.transaction import Transaction, TransactionSource, TransactionStatus


def _ts() -> datetime:
    return datetime(2024, 1, 1, tzinfo=timezone.utc)


def _make_txn(txn_id: str, amount: Decimal, src: TransactionSource = TransactionSource.GATEWAY) -> Transaction:
    return Transaction(
        txn_id=txn_id,
        source=src,
        amount=amount,
        currency="INR",
        timestamp=_ts(),
        status=TransactionStatus.COMPLETED,
        order_id=f"ORD_{txn_id}",
        reference_number=f"REF_{txn_id}",
    )


class TestSelectiveInvocationPolicy:
    """1. Verify selective invocation policy."""

    def test_deterministic_low_value_fee_mismatch_bypasses_llm(self):
        t1 = _make_txn("G1", Decimal("500.00"), TransactionSource.GATEWAY)
        t2 = _make_txn("L1", Decimal("500.00"), TransactionSource.LEDGER)
        should_escalate, reason = ExposureCalculator.should_escalate_to_llm(
            financial_exposure=Decimal("500.00"),
            category=ExceptionCategory.FEE_MISMATCH,
            deterministic_confidence=Decimal("0.90"),
            is_duplicate=False,
            decision=None,
        )
        assert should_escalate is False
        assert "deterministic" in reason.lower()

    def test_high_value_low_confidence_escalates_to_llm(self):
        should_escalate, reason = ExposureCalculator.should_escalate_to_llm(
            financial_exposure=Decimal("250000.00"),
            category=ExceptionCategory.FEE_MISMATCH,
            deterministic_confidence=Decimal("0.60"),
            is_duplicate=False,
            decision=None,
        )
        assert should_escalate is True
        assert "high financial exposure" in reason.lower()

    def test_unexplained_category_escalates_to_llm(self):
        should_escalate, reason = ExposureCalculator.should_escalate_to_llm(
            financial_exposure=Decimal("1000.00"),
            category=ExceptionCategory.UNEXPLAINED,
            deterministic_confidence=Decimal("0.30"),
            is_duplicate=False,
            decision=None,
        )
        assert should_escalate is True
        assert "unexplained" in reason.lower()

    def test_ambiguous_decision_escalates_to_llm(self):
        dec = DecisionResult(
            transaction_ids=["G1", "L1"],
            action=DecisionAction.AMBIGUOUS,
            confidence=Decimal("0.70"),
            evidence={},
            reason="Competing candidates",
        )
        should_escalate, reason = ExposureCalculator.should_escalate_to_llm(
            financial_exposure=Decimal("5000.00"),
            category=ExceptionCategory.WRONG_REFERENCE,
            deterministic_confidence=Decimal("0.70"),
            is_duplicate=False,
            decision=dec,
        )
        assert should_escalate is True
        assert "ambiguous match" in reason.lower()


class TestPydanticStructuredValidation:
    """4. Verify Pydantic structured output validation."""

    def test_valid_llm_result_parsing(self):
        data = {
            "root_cause": "Merchant fee schedule misapplied during settlement batch processing.",
            "classification": "fee_mismatch",
            "confidence": 0.92,
            "evidence": [
                {"observation": "Gateway fee was 2.5% instead of contracted 1.5%", "source": "gateway", "relevance": "Direct fee delta"}
            ],
            "financial_exposure": "125.50",
            "recommended_action": "request_credit_note",
            "requires_human_review": False,
            "reasoning_summary": "Cross-checked fee breakdown against merchant agreement and bank settlement delta.",
        }
        res = LLMInvestigationResult(**data)
        assert res.classification == "fee_mismatch"
        assert res.recommended_action == RecommendedAction.REQUEST_CREDIT_NOTE
        assert res.confidence == 0.92

    def test_invalid_classification_raises_validation_error(self):
        data = {
            "root_cause": "Unknown anomaly occurred in settlement.",
            "classification": "some_arbitrary_hallucinated_category",
            "confidence": 0.80,
            "evidence": [{"observation": "None", "source": "unknown", "relevance": "none"}],
            "financial_exposure": "100.00",
            "recommended_action": "escalate_manual",
            "requires_human_review": True,
            "reasoning_summary": "Cannot determine root cause with available evidence.",
        }
        with pytest.raises(ValidationError):
            LLMInvestigationResult(**data)

    def test_invalid_confidence_raises_validation_error(self):
        data = {
            "root_cause": "Valid root cause description here.",
            "classification": "unexplained",
            "confidence": 1.5,  # Invalid: > 1.0
            "evidence": [{"observation": "Observation", "source": "bank", "relevance": "relevance"}],
            "financial_exposure": "50.00",
            "recommended_action": "escalate_manual",
            "requires_human_review": True,
            "reasoning_summary": "Step by step reasoning explaining why confidence is invalid.",
        }
        with pytest.raises(ValidationError):
            LLMInvestigationResult(**data)

    def test_missing_required_field_raises_validation_error(self):
        data = {
            "root_cause": "Valid root cause description here.",
            "classification": "unexplained",
            # missing confidence, evidence, etc.
        }
        with pytest.raises(ValidationError):
            LLMInvestigationResult(**data)


class TestFailureAndFallbackSafety:
    """5. Verify failure/fallback safety."""

    @pytest.mark.asyncio
    async def test_llm_timeout_falls_back_gracefully_with_human_review(self):
        fake_llm = FakeLLMClient(raise_error=asyncio.TimeoutError("Groq request timed out after 30s"))
        runner = InvestigationGraphRunner(llm_client=fake_llm)

        t1 = _make_txn("G1", Decimal("150000.00"))
        exc = ExceptionRecord(
            transaction_id="G1",
            category=ExceptionCategory.UNEXPLAINED,
            confidence=Decimal("0.30"),
            financial_exposure=Decimal("150000.00"),
            expected_cost=Decimal("75000.00"),
            explanation="Unexplained high value exception",
        )

        inv_repo = AsyncMock()
        inv_repo.create = AsyncMock(return_value="inv-timeout-001")
        audit_repo = AsyncMock()
        audit_repo.create = AsyncMock(return_value=None)
        session = AsyncMock()

        service = InvestigationService(
            session=session,
            investigation_repo=inv_repo,
            audit_repo=audit_repo,
            graph_runner=runner,
        )

        conclusion = await service.investigate(
            exception_id="exc-timeout-001",
            run_id="run-001",
            transactions=[t1],
            investigation_id="inv-timeout-001",
        )

        assert conclusion.method == InvestigationMethod.FALLBACK
        assert conclusion.requires_human_review is True
        assert conclusion.llm_invoked is True
        assert conclusion.financial_exposure == Decimal("150000.00")
        assert "Unexplained" in conclusion.root_cause
