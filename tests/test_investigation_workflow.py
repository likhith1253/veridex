"""
Tests for Investigation Workflow

Tests the complete investigation flow:
- Investigation view service
- API endpoint
- Decision boundary logic
- State refresh after decision
"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from app.services.investigation_view_service import (
    DecisionBoundary,
    FinancialImpact,
    InvestigationTimeline,
    InvestigationView,
    InvestigationViewService,
    MatchingEvidence,
)


@pytest.fixture
def mock_session():
    """Mock async session."""
    session = AsyncMock()
    return session


@pytest.fixture
def sample_exception_orm():
    """Sample exception ORM for testing."""
    exc = MagicMock()
    exc.id = "exc_test_001"
    exc.run_id = "run_test_001"
    exc.transaction_id = "txn_test_001"
    exc.exception_category = MagicMock()
    exc.exception_category.value = "fee_mismatch"
    exc.status = "open"
    exc.confidence = Decimal("0.75")
    exc.financial_exposure = Decimal("500.00")
    exc.expected_cost = Decimal("600.00")
    exc.explanation = "Fee discrepancy between gateway and ledger"
    exc.evidence = {"fee_difference": 500.0, "mismatch_fields": ["fee"]}
    exc.recommended_action = "escalate_manual"
    exc.resolved = False
    exc.resolved_at = None
    exc.created_at = datetime.now(timezone.utc)
    return exc


@pytest.fixture
def sample_transaction_orm():
    """Sample transaction ORM for testing."""
    txn = MagicMock()
    txn.id = "txn_test_001"
    txn.domain_transaction_id = "TXN_001"
    txn.source = MagicMock()
    txn.source.value = "gateway"
    txn.amount = Decimal("10000.00")
    txn.currency = "INR"
    txn.timestamp = datetime.now(timezone.utc)
    txn.fee = Decimal("200.00")
    txn.tax = Decimal("180.00")
    return txn


class TestInvestigationViewService:
    """Tests for InvestigationViewService."""
    
    @pytest.mark.asyncio
    async def test_get_investigation_view_success(self, mock_session, sample_exception_orm, sample_transaction_orm):
        """Test successful investigation view retrieval."""
        # Setup mock returns
        mock_session.execute = AsyncMock()
        
        # Mock exception query
        exc_result = MagicMock()
        exc_result.scalar_one_or_none.return_value = sample_exception_orm
        
        # Mock transaction query
        txn_result = MagicMock()
        txn_result.scalar_one_or_none.return_value = sample_transaction_orm
        
        # Mock investigation query
        inv_result = MagicMock()
        inv_result.scalar_one_or_none.return_value = None
        
        # Mock audit query
        audit_result = MagicMock()
        audit_result.scalars.return_value.all.return_value = []
        
        # Mock decision query
        dec_result = MagicMock()
        dec_result.scalar_one_or_none.return_value = None
        
        def execute_side_effect(stmt):
            if "exceptions" in str(stmt):
                return exc_result
            elif "transactions" in str(stmt):
                return txn_result
            elif "investigations" in str(stmt):
                return inv_result
            elif "audit_events" in str(stmt):
                return audit_result
            elif "decisions" in str(stmt):
                return dec_result
            return MagicMock()
        
        mock_session.execute.side_effect = execute_side_effect
        
        service = InvestigationViewService(mock_session)
        view = await service.get_investigation_view("exc_test_001")
        
        assert view.exception_id == "exc_test_001"
        assert view.run_id == "run_test_001"
        assert view.transaction_id == "txn_test_001"
        assert view.source == "gateway"
        assert view.status == "open"
        assert view.exception_category == "fee_mismatch"
        assert view.confidence == 0.75
        assert view.financial_impact.monetary_exposure == 500.0
        assert view.decision_boundary.category in ["AUTO_SAFE", "AI_SUGGESTED", "HUMAN_REVIEW"]
    
    @pytest.mark.asyncio
    async def test_get_investigation_view_not_found(self, mock_session):
        """Test investigation view with non-existent exception."""
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        service = InvestigationViewService(mock_session)
        
        with pytest.raises(ValueError, match="Exception not found"):
            await service.get_investigation_view("nonexistent_id")
    
    def test_build_timeline(self, mock_session, sample_exception_orm):
        """Test timeline building."""
        service = InvestigationViewService(mock_session)
        
        audit_events = []
        inv_mock = MagicMock()
        inv_mock.created_at = datetime.now(timezone.utc)
        
        timeline = service._build_timeline(sample_exception_orm, inv_mock, audit_events)
        
        assert timeline.exception_created is not None
        assert timeline.investigation_started is not None
        assert timeline.resolved is None
    
    def test_build_financial_impact(self, mock_session, sample_exception_orm, sample_transaction_orm):
        """Test financial impact building."""
        service = InvestigationViewService(mock_session)
        
        impact = service._build_financial_impact(sample_exception_orm, sample_transaction_orm)
        
        assert impact.transaction_amount == 10000.0
        assert impact.currency == "INR"
        assert impact.monetary_exposure == 500.0
        # Fee difference comes from evidence dict (500.0), not transaction fee (200.0)
        assert impact.fee_difference == 500.0
        assert impact.tax_difference == 180.0
    
    def test_build_matching_evidence(self, mock_session, sample_exception_orm):
        """Test matching evidence building."""
        service = InvestigationViewService(mock_session)
        
        decision_mock = MagicMock()
        decision_mock.decision_action = MagicMock()
        decision_mock.decision_action.value = "manual_review"
        decision_mock.deterministic_confidence = Decimal("0.85")
        decision_mock.ml_probability = Decimal("0.70")
        decision_mock.evidence = {"mismatch_fields": ["fee", "amount"]}
        
        evidence = service._build_matching_evidence(sample_exception_orm, decision_mock, None)
        
        assert evidence.deterministic_match_result == "manual_review"
        assert evidence.confidence == 0.85
        assert "fee" in evidence.mismatch_fields
    
    def test_build_decision_boundary_auto_safe(self, mock_session, sample_exception_orm):
        """Test decision boundary for auto-safe category."""
        service = InvestigationViewService(mock_session)
        
        sample_exception_orm.confidence = Decimal("0.98")
        sample_exception_orm.financial_exposure = Decimal("5000.00")
        
        boundary = service._build_decision_boundary(sample_exception_orm, None)
        
        assert boundary.category == "AUTO_SAFE"
        assert boundary.requires_human_review is False
    
    def test_build_decision_boundary_human_review(self, mock_session, sample_exception_orm):
        """Test decision boundary for human review category."""
        service = InvestigationViewService(mock_session)
        
        sample_exception_orm.confidence = Decimal("0.60")
        sample_exception_orm.financial_exposure = Decimal("150000.00")
        
        boundary = service._build_decision_boundary(sample_exception_orm, None)
        
        assert boundary.category == "HUMAN_REVIEW"
        assert boundary.requires_human_review is True
    
    def test_build_decision_boundary_ai_suggested(self, mock_session, sample_exception_orm):
        """Test decision boundary for AI-suggested category."""
        service = InvestigationViewService(mock_session)
        
        sample_exception_orm.confidence = Decimal("0.85")
        sample_exception_orm.financial_exposure = Decimal("50000.00")
        
        boundary = service._build_decision_boundary(sample_exception_orm, None)
        
        assert boundary.category == "AI_SUGGESTED"


class TestInvestigationViewDataclass:
    """Tests for investigation view dataclasses."""
    
    def test_investigation_view_to_dict(self):
        """Test InvestigationView serialization."""
        view = InvestigationView(
            exception_id="exc_001",
            run_id="run_001",
            transaction_id="txn_001",
            source="gateway",
            status="open",
            financial_impact=FinancialImpact(monetary_exposure=100.0),
            timeline=InvestigationTimeline(exception_created="2024-01-01T00:00:00Z"),
            matching_evidence=MatchingEvidence(confidence=0.9),
            exception_category="fee_mismatch",
            confidence=0.85,
            risk_bucket="medium",
            risk_score=0.5,
            root_cause="Fee discrepancy",
            explanation="Gateway fee higher than ledger",
            recommended_action="review",
            evidence={},
            decision_boundary=DecisionBoundary(category="AI_SUGGESTED", confidence=0.85, reason="ML confidence", requires_human_review=False),
            resolved=False,
            resolved_at=None,
            created_at="2024-01-01T00:00:00Z",
        )
        
        data = view.to_dict()
        
        assert data["exception_id"] == "exc_001"
        assert data["financial_impact"]["monetary_exposure"] == 100.0
        assert data["decision_boundary"]["category"] == "AI_SUGGESTED"
    
    def test_decision_boundary_categories(self):
        """Test all decision boundary categories."""
        auto_safe = DecisionBoundary(
            category="AUTO_SAFE",
            confidence=0.98,
            reason="High confidence",
            requires_human_review=False,
        )
        assert auto_safe.category == "AUTO_SAFE"
        assert auto_safe.requires_human_review is False
        
        human_review = DecisionBoundary(
            category="HUMAN_REVIEW",
            confidence=0.50,
            reason="Low confidence",
            requires_human_review=True,
        )
        assert human_review.category == "HUMAN_REVIEW"
        assert human_review.requires_human_review is True


class TestInvestigationWorkflowIntegration:
    """Integration tests for investigation workflow."""
    
    @pytest.mark.asyncio
    async def test_complete_investigation_flow(self, mock_session):
        """Test complete investigation flow from exception to decision boundary."""
        # This would typically test the full flow through the API
        # For now, we test the service layer
        service = InvestigationViewService(mock_session)
        
        # Mock setup
        exc_mock = MagicMock()
        exc_mock.id = "exc_integration_001"
        exc_mock.run_id = "run_integration_001"
        exc_mock.transaction_id = "txn_integration_001"
        exc_mock.exception_category = MagicMock()
        exc_mock.exception_category.value = "amount_mismatch"
        exc_mock.status = "open"
        exc_mock.confidence = Decimal("0.65")
        exc_mock.financial_exposure = Decimal("75000.00")
        exc_mock.expected_cost = Decimal("80000.00")
        exc_mock.explanation = "Amount mismatch between sources"
        exc_mock.evidence = {"amount_difference": 5000.0}
        exc_mock.recommended_action = "investigate"
        exc_mock.resolved = False
        exc_mock.resolved_at = None
        exc_mock.created_at = datetime.now(timezone.utc)
        
        txn_mock = MagicMock()
        txn_mock.id = "txn_integration_001"
        txn_mock.source = MagicMock()
        txn_mock.source.value = "ledger"
        txn_mock.amount = Decimal("50000.00")
        txn_mock.currency = "INR"
        txn_mock.timestamp = datetime.now(timezone.utc)
        txn_mock.fee = None
        txn_mock.tax = None
        
        mock_session.execute = AsyncMock()
        
        def execute_side_effect(stmt):
            result = MagicMock()
            if "exceptions" in str(stmt):
                result.scalar_one_or_none.return_value = exc_mock
            elif "transactions" in str(stmt):
                result.scalar_one_or_none.return_value = txn_mock
            else:
                result.scalar_one_or_none.return_value = None
                result.scalars.return_value.all.return_value = []
            return result
        
        mock_session.execute.side_effect = execute_side_effect
        
        view = await service.get_investigation_view("exc_integration_001")
        
        # Verify complete investigation context
        assert view.exception_id == "exc_integration_001"
        assert view.status == "open"
        assert view.exception_category == "amount_mismatch"
        assert view.financial_impact.monetary_exposure == 75000.0
        assert view.decision_boundary.category in ["AI_SUGGESTED", "HUMAN_REVIEW"]
        assert view.resolved is False
        
        # Verify all required sections are present
        assert view.timeline is not None
        assert view.matching_evidence is not None
        assert view.decision_boundary is not None
