import csv
import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from simulator.ground_truth import GroundTruth, GroundTruthRecord
from simulator.scenarios import (
    BankRecord,
    GatewayRecord,
    LedgerRecord,
    generate_ambiguous,
    generate_delayed_settlement,
    generate_duplicate,
    generate_fee_mismatch,
    generate_normal,
    generate_partial_refund,
    generate_rounding,
    generate_unexplained,
    generate_wrong_reference,
)


@dataclass
class GeneratorConfig:
    num_transactions: int = 200
    seed: int = 42
    scenario_distribution: dict[str, float] = None
    currency: str = "INR"
    date_range_days: int = 30
    min_amount: int = 500
    max_amount: int = 500000

    def __post_init__(self):
        if self.scenario_distribution is None:
            self.scenario_distribution = {
                "normal": 0.75,
                "delayed_settlement": 0.05,
                "fee_mismatch": 0.05,
                "partial_refund": 0.04,
                "duplicate": 0.03,
                "rounding": 0.03,
                "wrong_reference": 0.02,
                "ambiguous": 0.02,
                "unexplained": 0.01,
            }


class DataGenerator:
    def __init__(self, config: GeneratorConfig):
        self.config = config
        random.seed(config.seed)
        self.ground_truth = GroundTruth()
        self.gateway_records: list[GatewayRecord] = []
        self.ledger_records: list[LedgerRecord] = []
        self.bank_records: list[BankRecord] = []

    def generate(self) -> tuple[list[GatewayRecord], list[LedgerRecord], list[BankRecord], GroundTruth]:
        scenarios = self._assign_scenarios()
        end_date = datetime(2024, 1, 1)
        start_date = end_date - timedelta(days=self.config.date_range_days)

        for i, scenario in enumerate(scenarios):
            logical_id = f"TXN{i + 1:08d}"
            gateway_id = f"STL{i + 1:08d}"
            ledger_id = f"ORD{i + 1:08d}"
            bank_id = f"BANK{i + 1:08d}"

            amount = Decimal(str(random.randint(self.config.min_amount, self.config.max_amount)))
            days_offset = random.randint(0, self.config.date_range_days)
            date = start_date + timedelta(days=days_offset)

            gateway, ledger, bank, gt_record = self._generate_scenario(
                scenario, logical_id, gateway_id, ledger_id, bank_id, amount, date
            )
            gt_record.scenario = scenario

            self.gateway_records.append(gateway)
            self.ledger_records.append(ledger)
            self.bank_records.append(bank)
            self.ground_truth.add_record(gt_record)

        return self.gateway_records, self.ledger_records, self.bank_records, self.ground_truth

    def _assign_scenarios(self) -> list[str]:
        scenarios = []
        distribution = self.config.scenario_distribution
        total = sum(distribution.values())

        for scenario, weight in distribution.items():
            count = int((weight / total) * self.config.num_transactions)
            scenarios.extend([scenario] * count)

        while len(scenarios) < self.config.num_transactions:
            scenarios.append("normal")

        random.shuffle(scenarios)
        return scenarios[: self.config.num_transactions]

    def _generate_scenario(
        self,
        scenario: str,
        logical_id: str,
        gateway_id: str,
        ledger_id: str,
        bank_id: str,
        amount: Decimal,
        date: datetime,
    ) -> tuple[GatewayRecord, LedgerRecord, BankRecord, GroundTruthRecord]:
        scenario_map = {
            "normal": generate_normal,
            "delayed_settlement": generate_delayed_settlement,
            "fee_mismatch": generate_fee_mismatch,
            "partial_refund": generate_partial_refund,
            "duplicate": generate_duplicate,
            "rounding": generate_rounding,
            "wrong_reference": generate_wrong_reference,
            "ambiguous": generate_ambiguous,
            "unexplained": generate_unexplained,
        }

        generator = scenario_map.get(scenario, generate_normal)
        return generator(logical_id, gateway_id, ledger_id, bank_id, amount, date, self.config.currency)

    def write_csvs(self, output_dir: Path) -> None:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        self._write_gateway_csv(output_dir / "gateway.csv")
        self._write_ledger_csv(output_dir / "ledger.csv")
        self._write_bank_csv(output_dir / "bank.csv")

    def _write_gateway_csv(self, filepath: Path) -> None:
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["settlement_id", "transaction_id", "order_id", "utr", "gross_amount", "fee", "tax", "net_amount", "settlement_date", "currency", "status"]
            )
            for rec in self.gateway_records:
                writer.writerow(
                    [
                        rec.settlement_id,
                        rec.transaction_id,
                        rec.order_id,
                        rec.utr,
                        str(rec.gross_amount),
                        str(rec.fee),
                        str(rec.tax),
                        str(rec.net_amount),
                        rec.settlement_date.isoformat(),
                        rec.currency,
                        rec.status,
                    ]
                )

    def _write_ledger_csv(self, filepath: Path) -> None:
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["order_id", "customer_id", "transaction_amount", "refund_amount", "order_date", "payment_status", "currency", "internal_reference"]
            )
            for rec in self.ledger_records:
                writer.writerow(
                    [
                        rec.order_id,
                        rec.customer_id,
                        str(rec.transaction_amount),
                        str(rec.refund_amount),
                        rec.order_date.isoformat(),
                        rec.payment_status,
                        rec.currency,
                        rec.internal_reference,
                    ]
                )

    def _write_bank_csv(self, filepath: Path) -> None:
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["bank_transaction_id", "utr", "credit_amount", "debit_amount", "value_date", "narration", "currency"])
            for rec in self.bank_records:
                writer.writerow(
                    [
                        rec.bank_transaction_id,
                        rec.utr,
                        str(rec.credit_amount),
                        str(rec.debit_amount),
                        rec.value_date.isoformat(),
                        rec.narration,
                        rec.currency,
                    ]
                )

    def write_ground_truth(self, filepath: Path) -> None:
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(self.ground_truth.to_dict(), f, indent=2)


def generate_default(output_dir: Path = Path("data/simulated")) -> None:
    config = GeneratorConfig()
    generator = DataGenerator(config)
    generator.generate()
    generator.write_csvs(output_dir)
    generator.write_ground_truth(output_dir / "ground_truth.json")
    print(f"Generated {config.num_transactions} transactions in {output_dir}")


if __name__ == "__main__":
    generate_default()
