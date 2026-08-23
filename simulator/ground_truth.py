from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

from app.models.exception_record import ExceptionCategory


@dataclass
class GroundTruthRecord:
    logical_transaction_id: str
    gateway_record_id: str
    ledger_record_id: str
    bank_record_id: str
    true_match: bool
    true_exception: Optional[ExceptionCategory]
    true_amount: Decimal
    true_refund: Optional[Decimal]
    true_settlement_date: datetime
    financial_exposure: Decimal


@dataclass
class GroundTruth:
    records: dict[str, GroundTruthRecord] = field(default_factory=dict)

    def add_record(self, record: GroundTruthRecord) -> None:
        self.records[record.logical_transaction_id] = record

    def get_record(self, logical_transaction_id: str) -> Optional[GroundTruthRecord]:
        return self.records.get(logical_transaction_id)

    def to_dict(self) -> dict:
        return {
            logical_id: {
                "logical_transaction_id": rec.logical_transaction_id,
                "gateway_record_id": rec.gateway_record_id,
                "ledger_record_id": rec.ledger_record_id,
                "bank_record_id": rec.bank_record_id,
                "true_match": rec.true_match,
                "true_exception": rec.true_exception.value if rec.true_exception else None,
                "true_amount": str(rec.true_amount),
                "true_refund": str(rec.true_refund) if rec.true_refund else None,
                "true_settlement_date": rec.true_settlement_date.isoformat(),
                "financial_exposure": str(rec.financial_exposure),
            }
            for logical_id, rec in self.records.items()
        }
