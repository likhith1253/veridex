from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from app.models.decision_result import DecisionResult
from app.models.exception_record import ExceptionRecord
from app.models.transaction import Transaction, TransactionSource


@dataclass
class TransactionSnapshot:
    """Immutable view of a single transaction for investigation context."""
    txn_id: str
    source: TransactionSource
    amount: Decimal
    currency: str
    timestamp: datetime
    reference_number: Optional[str] = None
    order_id: Optional[str] = None
    narration: Optional[str] = None
    fee: Optional[Decimal] = None
    tax: Optional[Decimal] = None

    @classmethod
    def from_transaction(cls, txn: Transaction) -> "TransactionSnapshot":
        return cls(
            txn_id=txn.txn_id,
            source=txn.source,
            amount=txn.amount,
            currency=txn.currency,
            timestamp=txn.timestamp,
            reference_number=txn.reference_number,
            order_id=txn.order_id,
            narration=txn.narration,
            fee=txn.fee,
            tax=txn.tax,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "txn_id": self.txn_id,
            "source": self.source.value,
            "amount": str(self.amount),
            "currency": self.currency,
            "timestamp": self.timestamp.isoformat(),
            "reference_number": self.reference_number,
            "order_id": self.order_id,
            "narration": self.narration,
            "fee": str(self.fee) if self.fee is not None else None,
            "tax": str(self.tax) if self.tax is not None else None,
        }


@dataclass
class InvestigationEvidence:
    """Structured evidence package derived deterministically from involved transactions."""
    gateway_snapshots: list[TransactionSnapshot] = field(default_factory=list)
    ledger_snapshots: list[TransactionSnapshot] = field(default_factory=list)
    bank_snapshots: list[TransactionSnapshot] = field(default_factory=list)

    # Derived factual fields
    unique_amounts: list[Decimal] = field(default_factory=list)
    unique_references: list[str] = field(default_factory=list)
    unique_orders: list[str] = field(default_factory=list)
    currencies: list[str] = field(default_factory=list)
    time_span_seconds: float = 0.0

    # Discrepancy flags
    has_amount_difference: bool = False
    max_amount_delta: Decimal = Decimal("0")
    has_duplicate_identifiers: bool = False
    has_reference_mismatch: bool = False
    has_fee_difference: bool = False
    expected_bank_amount: Optional[Decimal] = None
    actual_bank_amount: Optional[Decimal] = None
    fee_discrepancy: Optional[Decimal] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "gateway_transactions": [t.to_dict() for t in self.gateway_snapshots],
            "ledger_transactions": [t.to_dict() for t in self.ledger_snapshots],
            "bank_transactions": [t.to_dict() for t in self.bank_snapshots],
            "unique_amounts": [str(a) for a in self.unique_amounts],
            "unique_references": self.unique_references,
            "unique_orders": self.unique_orders,
            "currencies": self.currencies,
            "time_span_seconds": self.time_span_seconds,
            "has_amount_difference": self.has_amount_difference,
            "max_amount_delta": str(self.max_amount_delta),
            "has_duplicate_identifiers": self.has_duplicate_identifiers,
            "has_reference_mismatch": self.has_reference_mismatch,
            "has_fee_difference": self.has_fee_difference,
            "expected_bank_amount": str(self.expected_bank_amount) if self.expected_bank_amount is not None else None,
            "actual_bank_amount": str(self.actual_bank_amount) if self.actual_bank_amount is not None else None,
            "fee_discrepancy": str(self.fee_discrepancy) if self.fee_discrepancy is not None else None,
        }

    def to_llm_context(self) -> dict[str, Any]:
        """Compact serialized dictionary formatted for LLM prompts."""
        return self.to_dict()


@dataclass
class InvestigationContext:
    """Full structured context assembled for an investigation."""
    exception_id: str
    run_id: str
    decision: Optional[DecisionResult]
    transactions: list[Transaction]
    evidence: InvestigationEvidence
    raw_decision_evidence: dict[str, Any] = field(default_factory=dict)
    historical_cases: list[dict[str, Any]] = field(default_factory=list)


class InvestigationContextBuilder:
    """Deterministic builder constructing InvestigationContext from domain entities."""

    @staticmethod
    def build(
        exception_id: str,
        run_id: str,
        transactions: list[Transaction],
        decision: Optional[DecisionResult] = None,
        historical_cases: Optional[list[dict[str, Any]]] = None,
    ) -> InvestigationContext:
        """Construct the complete evidence and context deterministically."""
        gw_snaps: list[TransactionSnapshot] = []
        ld_snaps: list[TransactionSnapshot] = []
        bk_snaps: list[TransactionSnapshot] = []

        amounts: set[Decimal] = set()
        references: set[str] = set()
        orders: set[str] = set()
        currencies: set[str] = set()
        timestamps: list[datetime] = []

        for txn in transactions:
            snap = TransactionSnapshot.from_transaction(txn)
            if txn.source == TransactionSource.GATEWAY:
                gw_snaps.append(snap)
            elif txn.source == TransactionSource.LEDGER:
                ld_snaps.append(snap)
            elif txn.source == TransactionSource.BANK:
                bk_snaps.append(snap)

            amounts.add(txn.amount)
            if txn.reference_number:
                references.add(txn.reference_number)
            if txn.order_id:
                orders.add(txn.order_id)
            currencies.add(txn.currency)
            timestamps.append(txn.timestamp)

        # Time span
        time_span = 0.0
        if len(timestamps) >= 2:
            min_ts = min(timestamps)
            max_ts = max(timestamps)
            time_span = (max_ts - min_ts).total_seconds()

        # Amount delta
        max_delta = Decimal("0")
        has_amount_diff = len(amounts) > 1
        if has_amount_diff and amounts:
            max_delta = max(amounts) - min(amounts)

        # Reference consistency
        has_ref_mismatch = len(references) > 1

        # Duplicate checking across transactions of same source
        source_counts: dict[str, int] = {}
        for txn in transactions:
            key = f"{txn.source.value}:{txn.txn_id}"
            source_counts[key] = source_counts.get(key, 0) + 1
        has_dup = any(c > 1 for c in source_counts.values()) or len(gw_snaps) > 1 or len(ld_snaps) > 1 or len(bk_snaps) > 1

        # Fee analysis between gateway and bank
        has_fee_diff = False
        expected_bank = None
        actual_bank = None
        fee_disc = None

        if gw_snaps and bk_snaps:
            gw = gw_snaps[0]
            bk = bk_snaps[0]
            actual_bank = bk.amount
            fee = gw.fee or Decimal("0")
            tax = gw.tax or Decimal("0")
            if gw.fee is not None or gw.tax is not None:
                expected_bank = gw.amount - fee - tax
                if expected_bank != actual_bank:
                    has_fee_diff = True
                    fee_disc = abs(expected_bank - actual_bank)
            elif actual_bank < gw.amount and (gw.amount - actual_bank) <= (gw.amount * Decimal("0.15")) and not has_ref_mismatch:
                # Plausible fee deduction when bank < gateway by <= 15%
                expected_bank = actual_bank
                has_fee_diff = True
                fee_disc = gw.amount - actual_bank

        evidence = InvestigationEvidence(
            gateway_snapshots=gw_snaps,
            ledger_snapshots=ld_snaps,
            bank_snapshots=bk_snaps,
            unique_amounts=sorted(list(amounts)),
            unique_references=sorted(list(references)),
            unique_orders=sorted(list(orders)),
            currencies=sorted(list(currencies)),
            time_span_seconds=time_span,
            has_amount_difference=has_amount_diff,
            max_amount_delta=max_delta,
            has_duplicate_identifiers=has_dup,
            has_reference_mismatch=has_ref_mismatch,
            has_fee_difference=has_fee_diff,
            expected_bank_amount=expected_bank,
            actual_bank_amount=actual_bank,
            fee_discrepancy=fee_disc,
        )

        raw_decision_evidence = decision.evidence if decision and decision.evidence else {}

        return InvestigationContext(
            exception_id=exception_id,
            run_id=run_id,
            decision=decision,
            transactions=transactions,
            evidence=evidence,
            raw_decision_evidence=raw_decision_evidence,
            historical_cases=historical_cases or [],
        )
