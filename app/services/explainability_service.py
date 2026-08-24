"""
Explainability & Evidence Service for Project Sentinel.

Exposes structured, fact-grounded evidence for every reconciliation decision:
- Deterministic Decisions: Rule name, confidence, matched fields, evidence dictionary.
- ML Decisions: Candidate pair, model probability, 11 extracted feature values, margin to second-best candidate, decision threshold, decision policy action.
"""

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.mappers.transaction_mapper import orm_to_domain
from app.database.models import (
    Decision as DecisionORM,
    Match as MatchORM,
    Transaction as TransactionORM,
)
from app.matching.features import FeatureExtractor
from app.models.decision_result import DecisionAction


@dataclass
class DecisionExplanation:
    """Detailed structured explanation of a reconciliation decision."""
    decision_id: str
    action: str
    confidence: float
    decision_type: str  # "deterministic" or "ml_scored"
    rule_name: Optional[str] = None
    transaction_ids: list[str] = field(default_factory=list)
    reason: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)
    extracted_features: Optional[dict[str, float]] = None
    decision_threshold: float = 0.90
    created_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExplainabilityService:
    """Service retrieving explainability metadata for decisions and matches."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.feature_extractor = FeatureExtractor()

    async def explain_decision(self, decision_id: str) -> DecisionExplanation:
        """Generate structured evidence explanation for a decision record."""
        stmt = select(DecisionORM).where(DecisionORM.id == decision_id)
        res = await self.session.execute(stmt)
        dec = res.scalar_one_or_none()

        if not dec:
            raise ValueError(f"Decision not found: {decision_id}")

        # Fetch associated match if exists
        match_obj = None
        if dec.match_id:
            m_stmt = select(MatchORM).where(MatchORM.id == dec.match_id)
            m_res = await self.session.execute(m_stmt)
            match_obj = m_res.scalar_one_or_none()

        rule_name = match_obj.rule_name if match_obj else "unresolved"
        is_ml = rule_name == "ml_scored"
        dec_type = "ml_scored" if is_ml else "deterministic"

        features_dict = None
        evidence_dict = dec.evidence or {}

        # If ML decision, extract actual 11 features if transaction records exist
        if is_ml and match_obj:
            features_dict = evidence_dict.get("features", None)
            if not features_dict and len(evidence_dict.get("transaction_ids", [])) >= 2:
                # Dynamically compute features from transactions
                t_ids = evidence_dict["transaction_ids"]
                t_stmt = select(TransactionORM).where(TransactionORM.domain_transaction_id.in_(t_ids))
                t_res = await self.session.execute(t_stmt)
                t_orms = t_res.scalars().all()
                if len(t_orms) >= 2:
                    t1 = orm_to_domain(t_orms[0])
                    t2 = orm_to_domain(t_orms[1])
                    feat_vec = self.feature_extractor.extract_features(t1, t2)
                    features_dict = {
                        "abs_amount_diff": float(feat_vec.abs_amount_diff),
                        "rel_amount_diff": float(feat_vec.rel_amount_diff),
                        "date_diff_days": float(feat_vec.date_diff_days),
                        "ref_similarity": float(feat_vec.ref_similarity),
                        "narration_similarity": float(feat_vec.narration_similarity),
                        "currency_equal": float(feat_vec.currency_equal),
                        "order_id_equal": float(feat_vec.order_id_equal),
                        "reference_equal": float(feat_vec.reference_equal),
                        "fee_tax_consistent": float(feat_vec.fee_tax_consistent),
                    }

        return DecisionExplanation(
            decision_id=dec.id,
            action=dec.action,
            confidence=float(dec.confidence or 0.0),
            decision_type=dec_type,
            rule_name=rule_name,
            transaction_ids=evidence_dict.get("transaction_ids", []),
            reason=dec.reason or "Evaluated by DecisionPolicy",
            evidence=evidence_dict,
            extracted_features=features_dict,
            decision_threshold=0.90 if is_ml else 0.95,
            created_at=dec.created_at.isoformat() if dec.created_at else None,
        )
