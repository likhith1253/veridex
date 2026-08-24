from decimal import Decimal
from typing import Optional

from app.models.exception_record import ExceptionCategory
from app.risk.interface import RiskBucket, RiskInput, RiskOutput


class RiskCalculator:
    """Deterministic risk calculator for financial reconciliation exceptions."""

    # Risk thresholds in INR
    LOW_THRESHOLD = Decimal("10000")
    MEDIUM_THRESHOLD = Decimal("50000")
    HIGH_THRESHOLD = Decimal("200000")

    # Base category risk coefficients
    CATEGORY_COEFFICIENTS: dict[ExceptionCategory, Decimal] = {
        ExceptionCategory.DUPLICATE_ENTRY: Decimal("0.95"),
        ExceptionCategory.AMBIGUOUS_MATCH: Decimal("0.75"),
        ExceptionCategory.UNEXPLAINED: Decimal("0.80"),
        ExceptionCategory.FEE_MISMATCH: Decimal("0.40"),
        ExceptionCategory.PARTIAL_REFUND: Decimal("0.50"),
        ExceptionCategory.WRONG_REFERENCE: Decimal("0.35"),
        ExceptionCategory.DELAYED_SETTLEMENT: Decimal("0.15"),
        ExceptionCategory.CURRENCY_ROUNDING: Decimal("0.05"),
    }

    @classmethod
    def calculate(cls, inp: RiskInput) -> RiskOutput:
        """Calculate risk deterministically based on financial exposure, category, and flags."""
        exposure = max(Decimal("0"), inp.financial_exposure)

        # 1. Determine risk bucket
        if exposure < cls.LOW_THRESHOLD:
            bucket = RiskBucket.LOW
        elif exposure < cls.MEDIUM_THRESHOLD:
            bucket = RiskBucket.MEDIUM
        elif exposure < cls.HIGH_THRESHOLD:
            bucket = RiskBucket.HIGH
        else:
            bucket = RiskBucket.CRITICAL

        # 2. Determine base coefficient
        base_coeff = cls.CATEGORY_COEFFICIENTS.get(inp.category, Decimal("0.50"))

        # 3. Adjust for duplicates or uncertainty
        coeff = base_coeff
        if inp.is_duplicate:
            coeff = max(coeff, Decimal("0.90"))

        # Inverse confidence penalty: lower confidence -> higher risk multiplier
        confidence_val = max(Decimal("0.1"), min(Decimal("1.0"), inp.confidence))
        uncertainty_penalty = (Decimal("1.0") - confidence_val) * Decimal("0.20")
        final_risk_score = min(Decimal("1.0"), coeff + uncertainty_penalty)

        # 4. Expected cost calculation
        expected_cost = (exposure * final_risk_score).quantize(Decimal("0.01"))

        # 5. Immediate review requirement
        requires_immediate_review = (
            bucket == RiskBucket.CRITICAL
            or (bucket == RiskBucket.HIGH and inp.is_duplicate)
            or (inp.category == ExceptionCategory.UNEXPLAINED and exposure >= cls.MEDIUM_THRESHOLD)
        )

        summary = (
            f"Exposure: INR {exposure:,.2f} ({bucket.value.upper()}) | "
            f"Category: {inp.category.value} | Risk Score: {final_risk_score:.2f} | "
            f"Expected Cost: INR {expected_cost:,.2f}"
        )

        return RiskOutput(
            risk_score=final_risk_score.quantize(Decimal("0.0001")),
            expected_cost=expected_cost,
            risk_bucket=bucket,
            requires_immediate_review=requires_immediate_review,
            risk_summary=summary,
        )
