"""
Comprehensive Exception Investigation View Service for Project Sentinel.

Provides complete investigation context for a single exception:
- Identity information
- Financial impact
- Timeline events
- Matching evidence
- Intelligence classification
- Decision boundary determination
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    AuditEvent as AuditEventORM,
    Decision as DecisionORM,
    Exception as ExceptionORM,
    Investigation as InvestigationORM,
    Match as MatchORM,
    Transaction as TransactionORM,
)
from app.risk.calculator import RiskCalculator
from app.risk.interface import RiskInput


@dataclass
class InvestigationTimeline:
    """Timeline of events for this exception."""
    exception_created: Optional[str] = None
    investigation_started: Optional[str] = None
    investigation_completed: Optional[str] = None
    human_decision: Optional[str] = None
    resolved: Optional[str] = None


@dataclass
class MatchingEvidence:
    """Evidence from the matching process."""
    deterministic_match_result: Optional[str] = None
    ml_match_result: Optional[str] = None
    confidence: float = 0.0
    candidate_matches: list[dict[str, Any]] = field(default_factory=list)
    mismatch_fields: list[str] = field(default_factory=list)


@dataclass
class FinancialImpact:
    """Financial impact of the exception."""
    transaction_amount: Optional[float] = None
    currency: Optional[str] = None
    monetary_exposure: float = 0.0
    fee_difference: Optional[float] = None
    tax_difference: Optional[float] = None
    refund_impact: Optional[float] = None
    settlement_impact: Optional[float] = None


@dataclass
class DecisionBoundary:
    """Classification of where this exception falls in the decision boundary."""
    category: str = "UNKNOWN"  # AUTO_SAFE, AI_SUGGESTED, HUMAN_REVIEW
    confidence: float = 0.0
    reason: str = ""
    requires_human_review: bool = False


@dataclass
class InvestigationView:
    """Complete investigation view for a single exception."""
    
    # Identity
    exception_id: str
    run_id: str
    transaction_id: Optional[str]
    source: Optional[str]
    status: str
    
    # Financial Impact
    financial_impact: FinancialImpact
    
    # Timeline
    timeline: InvestigationTimeline
    
    # Matching Evidence
    matching_evidence: MatchingEvidence
    
    # Intelligence
    exception_category: str
    confidence: float
    risk_bucket: str
    risk_score: float
    root_cause: str
    explanation: str
    recommended_action: str
    evidence: dict[str, Any]
    
    # Decision Boundary
    decision_boundary: DecisionBoundary
    
    # Resolution
    resolved: bool
    resolved_at: Optional[str]
    
    created_at: Optional[str]
    
    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["financial_impact"] = asdict(self.financial_impact)
        data["timeline"] = asdict(self.timeline)
        data["matching_evidence"] = asdict(self.matching_evidence)
        data["decision_boundary"] = asdict(self.decision_boundary)
        return data


class InvestigationViewService:
    """Service providing comprehensive investigation view for exceptions."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_investigation_view(self, exception_id: str) -> InvestigationView:
        """Fetch complete investigation view for a single exception."""
        
        # Fetch exception
        exc_stmt = select(ExceptionORM).where(ExceptionORM.id == exception_id)
        exc_res = await self.session.execute(exc_stmt)
        exc = exc_res.scalar_one_or_none()
        
        if not exc:
            raise ValueError(f"Exception not found: {exception_id}")
        
        # Fetch transaction if available
        txn = None
        if exc.transaction_id:
            txn_stmt = select(TransactionORM).where(TransactionORM.id == exc.transaction_id)
            txn_res = await self.session.execute(txn_stmt)
            txn = txn_res.scalar_one_or_none()
        
        # Fetch investigation
        inv_stmt = select(InvestigationORM).where(InvestigationORM.exception_id == exception_id)
        inv_res = await self.session.execute(inv_stmt)
        inv = inv_res.scalar_one_or_none()
        
        # Fetch audit events for timeline
        audit_stmt = select(AuditEventORM).where(
            AuditEventORM.transaction_id == exc.transaction_id
        ).order_by(AuditEventORM.timestamp)
        audit_res = await self.session.execute(audit_stmt)
        audit_events = audit_res.scalars().all()
        
        # Fetch decision if available
        decision = None
        if exc.transaction_id:
            dec_stmt = select(DecisionORM).where(
                DecisionORM.run_id == exc.run_id
            ).order_by(DecisionORM.created_at.desc()).limit(1)
            dec_res = await self.session.execute(dec_stmt)
            decision = dec_res.scalar_one_or_none()
        
        # Build timeline
        timeline = self._build_timeline(exc, inv, audit_events)
        
        # Build financial impact
        financial_impact = self._build_financial_impact(exc, txn)
        
        # Build matching evidence
        matching_evidence = self._build_matching_evidence(exc, decision, inv)
        
        # Build decision boundary
        decision_boundary = self._build_decision_boundary(exc, inv)
        
        # Normalize category
        raw_cat = getattr(exc, "exception_category", "unknown")
        category_str = raw_cat.value if hasattr(raw_cat, "value") else str(raw_cat)
        
        # Calculate risk
        from app.models.exception_record import ExceptionCategory as DomainExceptionCategory
        try:
            domain_cat = DomainExceptionCategory(category_str)
        except ValueError:
            domain_cat = DomainExceptionCategory.UNEXPLAINED
        
        risk_output = RiskCalculator.calculate(
            RiskInput(
                category=domain_cat,
                financial_exposure=Decimal(str(exc.financial_exposure or Decimal("0"))),
                confidence=Decimal(str(exc.confidence or Decimal("0"))),
                is_duplicate=category_str == "duplicate_record",
            )
        )
        
        return InvestigationView(
            exception_id=exc.id,
            run_id=exc.run_id,
            transaction_id=exc.transaction_id,
            source=txn.source.value if txn and hasattr(txn.source, "value") else (str(txn.source) if txn else None),
            status=exc.status,
            financial_impact=financial_impact,
            timeline=timeline,
            matching_evidence=matching_evidence,
            exception_category=category_str,
            confidence=float(exc.confidence or 0.0),
            risk_bucket=risk_output.risk_bucket.value,
            risk_score=float(risk_output.risk_score),
            root_cause=inv.root_cause if inv else exc.explanation,
            explanation=exc.explanation,
            recommended_action=exc.recommended_action or (inv.recommended_action if inv else "escalate_manual"),
            evidence=exc.evidence or {},
            decision_boundary=decision_boundary,
            resolved=exc.resolved,
            resolved_at=exc.resolved_at.isoformat() if exc.resolved_at else None,
            created_at=exc.created_at.isoformat() if exc.created_at else None,
        )
    
    def _build_timeline(
        self, 
        exc: ExceptionORM, 
        inv: Optional[InvestigationORM], 
        audit_events: list[AuditEventORM]
    ) -> InvestigationTimeline:
        """Build timeline from exception, investigation, and audit events."""
        timeline = InvestigationTimeline(
            exception_created=exc.created_at.isoformat() if exc.created_at else None,
            investigation_started=inv.created_at.isoformat() if inv and inv.created_at else None,
            investigation_completed=None,
            human_decision=None,
            resolved=exc.resolved_at.isoformat() if exc.resolved_at else None,
        )
        
        # Extract timeline from audit events
        for event in audit_events:
            if event.event_type == "INVESTIGATION_COMPLETED":
                timeline.investigation_completed = event.timestamp.isoformat() if event.timestamp else None
            elif event.event_type.startswith("HUMAN_DECISION"):
                timeline.human_decision = event.timestamp.isoformat() if event.timestamp else None
        
        return timeline
    
    def _build_financial_impact(
        self, 
        exc: ExceptionORM, 
        txn: Optional[TransactionORM]
    ) -> FinancialImpact:
        """Build financial impact from exception and transaction."""
        impact = FinancialImpact(
            monetary_exposure=float(exc.financial_exposure or 0.0),
        )
        
        if txn:
            impact.transaction_amount = float(txn.amount)
            impact.currency = txn.currency
            impact.fee_difference = float(txn.fee) if txn.fee else None
            impact.tax_difference = float(txn.tax) if txn.tax else None
        
        # Extract from evidence if available
        evidence = exc.evidence or {}
        if "fee_difference" in evidence:
            impact.fee_difference = float(evidence["fee_difference"])
        if "tax_difference" in evidence:
            impact.tax_difference = float(evidence["tax_difference"])
        if "refund_impact" in evidence:
            impact.refund_impact = float(evidence["refund_impact"])
        if "settlement_impact" in evidence:
            impact.settlement_impact = float(evidence["settlement_impact"])
        
        return impact
    
    def _build_matching_evidence(
        self, 
        exc: ExceptionORM, 
        decision: Optional[DecisionORM],
        inv: Optional[InvestigationORM]
    ) -> MatchingEvidence:
        """Build matching evidence from decision and investigation."""
        evidence = MatchingEvidence(
            confidence=float(exc.confidence or 0.0),
        )
        
        if decision:
            evidence.deterministic_match_result = decision.decision_action.value if hasattr(decision.decision_action, "value") else str(decision.decision_action)
            evidence.ml_match_result = decision.reason if decision.reason else None
            if decision.deterministic_confidence:
                evidence.confidence = float(decision.deterministic_confidence)
            if decision.ml_probability:
                evidence.confidence = max(evidence.confidence, float(decision.ml_probability))
            
            # Extract evidence from decision
            dec_evidence = decision.evidence or {}
            if "candidate_matches" in dec_evidence:
                evidence.candidate_matches = dec_evidence["candidate_matches"]
            if "mismatch_fields" in dec_evidence:
                evidence.mismatch_fields = dec_evidence["mismatch_fields"]
        
        if inv and inv.evidence:
            inv_evidence = inv.evidence
            if "candidate_matches" in inv_evidence:
                evidence.candidate_matches = inv_evidence["candidate_matches"]
            if "mismatch_fields" in inv_evidence:
                evidence.mismatch_fields = inv_evidence["mismatch_fields"]
        
        return evidence
    
    def _build_decision_boundary(
        self, 
        exc: ExceptionORM, 
        inv: Optional[InvestigationORM]
    ) -> DecisionBoundary:
        """Determine decision boundary category based on confidence and risk."""
        confidence = float(exc.confidence or 0.0)
        exposure = float(exc.financial_exposure or 0.0)
        
        # Check if investigation requires human review
        requires_human_review = False
        if inv and inv.requires_human_review:
            requires_human_review = True
        
        # Decision boundary logic
        if confidence >= 0.95 and exposure < 10000:
            return DecisionBoundary(
                category="AUTO_SAFE",
                confidence=confidence,
                reason="High confidence deterministic match with low financial exposure",
                requires_human_review=False,
            )
        elif confidence >= 0.80:
            return DecisionBoundary(
                category="AI_SUGGESTED",
                confidence=confidence,
                reason="ML-suggested match with moderate confidence",
                requires_human_review=requires_human_review,
            )
        else:
            return DecisionBoundary(
                category="HUMAN_REVIEW",
                confidence=confidence,
                reason="Low confidence or high financial exposure requires human review",
                requires_human_review=True,
            )
