from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Exception as ExceptionORM, Investigation as InvestigationORM
from app.models.exception_record import ExceptionCategory
from app.risk.calculator import RiskCalculator
from app.risk.interface import RiskInput


CATEGORY_MAP = {
    "missing_record": ExceptionCategory.UNEXPLAINED,
    "amount_mismatch": ExceptionCategory.UNEXPLAINED,
    "timing_mismatch": ExceptionCategory.DELAYED_SETTLEMENT,
    "duplicate_record": ExceptionCategory.DUPLICATE_ENTRY,
    "data_quality": ExceptionCategory.UNEXPLAINED,
    "unknown": ExceptionCategory.UNEXPLAINED,
    "currency_rounding": ExceptionCategory.CURRENCY_ROUNDING,
    "partial_refund": ExceptionCategory.PARTIAL_REFUND,
    "delayed_settlement": ExceptionCategory.DELAYED_SETTLEMENT,
    "duplicate_entry": ExceptionCategory.DUPLICATE_ENTRY,
    "fee_mismatch": ExceptionCategory.FEE_MISMATCH,
    "wrong_reference": ExceptionCategory.WRONG_REFERENCE,
    "ambiguous_match": ExceptionCategory.AMBIGUOUS_MATCH,
    "unexplained": ExceptionCategory.UNEXPLAINED,
}


@dataclass
class ExceptionIntelligence:
    """Structured explanation for an exception: why, risk, evidence, and next steps."""

    exception_id: str
    run_id: str
    transaction_id: Optional[str]
    category: str
    status: str
    confidence: float
    financial_exposure_inr: float
    expected_cost_inr: float
    risk_bucket: str
    risk_score: float
    root_cause: str
    explanation: str
    recommended_action: str
    evidence: dict[str, Any] = field(default_factory=dict)
    supporting_facts: list[dict[str, Any]] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)
    created_at: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["why_it_happened"] = self.root_cause
        data["how_serious"] = {
            "risk_bucket": self.risk_bucket,
            "risk_score": self.risk_score,
            "financial_exposure_inr": self.financial_exposure_inr,
            "expected_cost_inr": self.expected_cost_inr,
        }
        data["what_evidence_supports_this"] = self.supporting_facts
        data["what_should_the_operator_do_next"] = self.next_steps
        return data


class ExceptionIntelligenceService:
    """Build explainable, risk-scored intelligence around a finance exception."""

    def __init__(self, session: AsyncSession):
        self.session = session

    @staticmethod
    def _normalize_category(value: Any) -> str:
        if value is None:
            return "unknown"
        if hasattr(value, "value"):
            value = value.value
        return str(value)

    @staticmethod
    def _map_risk_category(category_value: str) -> ExceptionCategory:
        return CATEGORY_MAP.get(category_value, ExceptionCategory.UNEXPLAINED)

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_text(value: Any, default: str = "No supporting detail available") -> str:
        if value is None:
            return default
        return str(value)

    @staticmethod
    def _default_next_steps(category: str, recommended_action: str, risk_bucket: str) -> list[str]:
        steps = [
            recommended_action or "review_exception",
        ]

        if risk_bucket in {"high", "critical"}:
            steps.extend([
                "Escalate to the finance lead and confirm the exposure against the bank statement.",
                "Validate whether a settlement adjustment, credit note, or refund is required.",
            ])
        elif category == "duplicate_record":
            steps.extend([
                "Check whether the duplicate was already settled or partially reversed.",
                "Freeze the duplicate from downstream reconciliation until confirmed.",
            ])
        elif category in {"amount_mismatch", "fee_mismatch"}:
            steps.extend([
                "Compare fee/tax or amount lines against the original payment record.",
                "Resolve the variance with the gateway or ledger team before settlement closes.",
            ])
        elif category == "timing_mismatch":
            steps.extend([
                "Review the settlement timeline and confirm whether the delay is operational or bank-side.",
                "Monitor the settlement window until the transfer clears or a correction is booked.",
            ])
        else:
            steps.extend([
                "Review the exception evidence and confirm whether the mismatch is operational or data-entry related.",
                "Escalate only if the discrepancy remains unexplained after the standard verification step.",
            ])

        return steps

    @staticmethod
    def _supporting_facts(exception_data: dict[str, Any], investigation_data: Optional[dict[str, Any]]) -> list[dict[str, Any]]:
        facts: list[dict[str, Any]] = []

        if exception_data.get("evidence"):
            for key, value in exception_data["evidence"].items():
                if key in {"details", "metadata", "meta_data"}:
                    continue
                facts.append({"label": key.replace("_", " ").title(), "value": value})

        if investigation_data:
            facts.append({"label": "Investigation method", "value": investigation_data.get("method", "deterministic")})
            facts.append({"label": "Investigation confidence", "value": investigation_data.get("confidence", 0)})
            if investigation_data.get("evidence"):
                for key, value in investigation_data["evidence"].items():
                    if isinstance(value, (dict, list)):
                        continue
                    facts.append({"label": key.replace("_", " ").title(), "value": value})

        if not facts:
            facts.append({"label": "Exception explanation", "value": exception_data.get("explanation", "No structured evidence was stored.")})

        return facts[:8]

    async def _build_exception_intelligence(self, exception: Any, investigation: Any = None) -> ExceptionIntelligence:
        category_name = self._normalize_category(getattr(exception, "exception_category", "unknown"))
        risk_category = self._map_risk_category(category_name)
        exposure_value = getattr(exception, "financial_exposure", None)
        confidence_value = getattr(exception, "confidence", None)

        try:
            exposure = Decimal(str(exposure_value or Decimal("0")))
        except Exception:
            exposure = Decimal("0")

        try:
            confidence = Decimal(str(confidence_value or Decimal("0")))
        except Exception:
            confidence = Decimal("0")

        risk_output = RiskCalculator.calculate(
            RiskInput(
                category=risk_category,
                financial_exposure=exposure,
                confidence=confidence,
                is_duplicate=category_name == "duplicate_record",
            )
        )

        investigation_root = getattr(investigation, "root_cause", None) if investigation else None
        investigation_action = getattr(investigation, "recommended_action", None) if investigation else None
        investigation_method = getattr(investigation, "method", None) if investigation else None
        investigation_confidence = getattr(investigation, "confidence", None) if investigation else None

        root_cause = self._safe_text(investigation_root or getattr(exception, "explanation", None), "Exception evidence does not yet establish a root cause.")
        explanation = self._safe_text(
            getattr(exception, "explanation", None) or root_cause,
            root_cause,
        )
        recommended_action = self._safe_text(
            getattr(exception, "recommended_action", None) or investigation_action or "escalate_manual",
            "escalate_manual",
        )

        evidence = getattr(exception, "evidence", None) or {}
        if isinstance(evidence, str):
            evidence = {"details": evidence}

        supporting_facts = self._supporting_facts(
            {
                "explanation": explanation,
                "evidence": evidence,
            },
            {
                "method": investigation_method,
                "confidence": investigation_confidence,
                "evidence": getattr(investigation, "evidence", {}) if investigation else {},
            },
        )

        intelligence = ExceptionIntelligence(
            exception_id=getattr(exception, "id", "unknown"),
            run_id=getattr(exception, "run_id", "unknown"),
            transaction_id=getattr(exception, "transaction_id", None),
            category=category_name,
            status=getattr(exception, "status", "open"),
            confidence=self._to_float(getattr(exception, "confidence", 0) or investigation_confidence or 0.0),
            financial_exposure_inr=self._to_float(getattr(exception, "financial_exposure", 0) or 0.0),
            expected_cost_inr=self._to_float(getattr(exception, "expected_cost", 0) or risk_output.expected_cost or 0.0),
            risk_bucket=risk_output.risk_bucket.value,
            risk_score=float(risk_output.risk_score),
            root_cause=root_cause,
            explanation=explanation,
            recommended_action=recommended_action,
            evidence=evidence,
            supporting_facts=supporting_facts,
            next_steps=self._default_next_steps(category_name, recommended_action, risk_output.risk_bucket.value),
            created_at=getattr(exception, "created_at", datetime.now(timezone.utc)).isoformat() if getattr(exception, "created_at", None) else None,
        )
        return intelligence

    async def get_exception_intelligence(self, exception_id: str) -> ExceptionIntelligence:
        stmt = select(ExceptionORM).where(ExceptionORM.id == exception_id)
        result = await self.session.execute(stmt)
        exception = result.scalar_one_or_none()
        if not exception:
            raise ValueError(f"Exception not found: {exception_id}")

        investigation_stmt = select(InvestigationORM).where(InvestigationORM.exception_id == exception_id)
        inv_result = await self.session.execute(investigation_stmt)
        investigation = inv_result.scalar_one_or_none()

        return await self._build_exception_intelligence(exception, investigation)

    async def list_exception_intelligence(
        self,
        run_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        stmt = select(ExceptionORM)
        if run_id:
            stmt = stmt.where(ExceptionORM.run_id == run_id)
        stmt = stmt.order_by(ExceptionORM.financial_exposure.desc()).limit(limit)

        result = await self.session.execute(stmt)
        exceptions = result.scalars().all()

        items = []
        for exc in exceptions:
            investigation_stmt = select(InvestigationORM).where(InvestigationORM.exception_id == exc.id)
            inv_result = await self.session.execute(investigation_stmt)
            investigation = inv_result.scalar_one_or_none()
            items.append(await self._build_exception_intelligence(exc, investigation))

        items.sort(key=lambda item: item.risk_score, reverse=True)
        return [item.to_dict() for item in items]
