import pytest
from unittest.mock import AsyncMock

from app.services.copilot_service import FinanceCopilotService


@pytest.mark.asyncio
async def test_copilot_handles_risk_question_with_grounded_context():
    service = FinanceCopilotService(session=AsyncMock())
    service._gather_context = AsyncMock(return_value={
        "summary": {"unresolved_monetary_exposure_inr": 125000.0, "match_rate": 87.5},
        "source_health": {"overall_health": "DEGRADED", "sources": {"gateway": {"health_status": "DEGRADED"}}},
        "exceptions": [
            {"exception_id": "exc-900", "category": "unexplained", "financial_exposure_inr": 80000.0, "status": "open", "risk_bucket": "high"},
            {"exception_id": "exc-901", "category": "delayed_settlement", "financial_exposure_inr": 45000.0, "status": "open", "risk_bucket": "medium"},
        ],
        "top_exception": {
            "exception_id": "exc-900",
            "root_cause": "Bank settlement arrived after the ledger cutoff.",
            "recommended_action": "escalate_manual",
            "next_steps": ["Escalate to the finance lead.", "Confirm settlement timing."],
            "financial_exposure_inr": 80000.0,
            "risk_bucket": "high",
        },
    })

    result = await service.answer_question("Which exception needs attention first?", run_id="run-42")

    assert result["question"] == "Which exception needs attention first?"
    assert "exc-900" in result["answer"]
    assert result["recommendation"]
    assert result["fact_summary"]["highest_risk_exception_id"] == "exc-900"
    assert result["evidence"][0]["exception_id"] == "exc-900"


@pytest.mark.asyncio
async def test_copilot_rejects_empty_question():
    service = FinanceCopilotService(session=AsyncMock())

    with pytest.raises(ValueError, match="Question"):
        await service.answer_question("   ")


@pytest.mark.asyncio
async def test_copilot_generates_daily_brief_with_evidence():
    service = FinanceCopilotService(session=AsyncMock())
    service._gather_context = AsyncMock(return_value={
        "summary": {"unresolved_monetary_exposure_inr": 420000.0, "match_rate": 72.5},
        "source_health": {"overall_health": "DEGRADED", "sources": {"gateway": {"health_status": "DEGRADED"}}},
        "top_exception": {
            "exception_id": "exc-102",
            "risk_bucket": "critical",
            "financial_exposure_inr": 180000.0,
            "recommended_action": "escalate_manual",
            "why_it_happened": "Settlement timing mismatch between gateway and bank feed.",
        },
        "exceptions": [],
        "intelligence": [],
    })

    brief = await service.generate_daily_brief(run_id="run-77")

    assert brief["status"] == "Critical"
    assert brief["highest_risk_exception"] == "exc-102"
    assert brief["human_review_required"] is True
    assert brief["evidence"]
    assert "settlement timing mismatch" in brief["why"].lower()


@pytest.mark.asyncio
async def test_copilot_human_review_boundary_is_detected():
    service = FinanceCopilotService(session=AsyncMock())
    service._gather_context = AsyncMock(return_value={
        "summary": {"unresolved_monetary_exposure_inr": 110000.0, "match_rate": 88.0},
        "source_health": {"overall_health": "HEALTHY", "sources": {}},
        "top_exception": {"exception_id": "exc-555", "risk_bucket": "high", "financial_exposure_inr": 110000.0},
        "exceptions": [],
        "intelligence": [],
    })

    result = await service.answer_question("What requires human review?", run_id="run-99")

    assert result["needs_human_review"] is True
    assert "Human review is required" in result["answer"]


@pytest.mark.asyncio
async def test_copilot_empty_scope_returns_no_data_message():
    service = FinanceCopilotService(session=AsyncMock())
    service._gather_context = AsyncMock(return_value={
        "summary": {"unresolved_monetary_exposure_inr": 0.0, "match_rate": 100.0},
        "source_health": {"overall_health": "HEALTHY", "sources": {}},
        "exceptions": [],
        "top_exception": None,
        "intelligence": [],
    })

    result = await service.answer_question("Which exception needs attention first?", run_id="run-empty")

    assert "no open exceptions" in result["answer"].lower()
    assert result["needs_human_review"] is False


@pytest.mark.asyncio
async def test_copilot_question_with_invalid_input_raises():
    service = FinanceCopilotService(session=AsyncMock())

    with pytest.raises(ValueError):
        await service.answer_question(" ")
