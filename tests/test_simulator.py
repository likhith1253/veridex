import json
import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from simulator.generator import DataGenerator, GeneratorConfig, generate_default
from simulator.ground_truth import GroundTruth, GroundTruthRecord
from simulator.scenarios import (
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


def test_deterministic_generation_with_same_seed():
    config1 = GeneratorConfig(num_transactions=50, seed=42)
    config2 = GeneratorConfig(num_transactions=50, seed=42)

    gen1 = DataGenerator(config1)
    gateway1, ledger1, bank1, gt1 = gen1.generate()

    gen2 = DataGenerator(config2)
    gateway2, ledger2, bank2, gt2 = gen2.generate()

    assert len(gateway1) == len(gateway2)
    assert len(ledger1) == len(ledger2)
    assert len(bank1) == len(bank2)

    for g1, g2 in zip(gateway1, gateway2):
        assert g1.transaction_id == g2.transaction_id
        assert g1.gross_amount == g2.gross_amount
        assert g1.settlement_date == g2.settlement_date


def test_requested_transaction_count():
    config = GeneratorConfig(num_transactions=100, seed=42)
    generator = DataGenerator(config)
    gateway, ledger, bank, gt = generator.generate()

    assert len(gateway) == 100
    assert len(ledger) == 100
    assert len(bank) == 100
    assert len(gt.records) == 100


def test_all_three_source_files_generated():
    config = GeneratorConfig(num_transactions=10, seed=42)
    generator = DataGenerator(config)
    gateway, ledger, bank, gt = generator.generate()

    assert len(gateway) > 0
    assert len(ledger) > 0
    assert len(bank) > 0


def test_ground_truth_generated():
    config = GeneratorConfig(num_transactions=10, seed=42)
    generator = DataGenerator(config)
    gateway, ledger, bank, gt = generator.generate()

    assert len(gt.records) > 0
    assert all(isinstance(rec, GroundTruthRecord) for rec in gt.records.values())


def test_scenario_distribution_approximates_config():
    config = GeneratorConfig(num_transactions=200, seed=42)
    generator = DataGenerator(config)
    gateway, ledger, bank, gt = generator.generate()

    exception_counts = {}
    for rec in gt.records.values():
        if rec.true_exception:
            exception_counts[rec.true_exception] = exception_counts.get(rec.true_exception, 0) + 1

    normal_count = sum(1 for rec in gt.records.values() if rec.true_exception is None)
    total = len(gt.records)

    assert normal_count / total > 0.70


def test_each_scenario_function_works():
    date = datetime.now()
    amount = Decimal("1000")

    gateway, ledger, bank, gt = generate_normal("TXN00000001", "STL00000001", "ORD00000001", "BANK00000001", amount, date, "INR")
    assert gt.true_exception is None
    assert gt.true_match is True

    gateway, ledger, bank, gt = generate_delayed_settlement("TXN00000002", "STL00000002", "ORD00000002", "BANK00000002", amount, date, "INR")
    assert gt.true_exception is not None

    gateway, ledger, bank, gt = generate_fee_mismatch("TXN00000003", "STL00000003", "ORD00000003", "BANK00000003", amount, date, "INR")
    assert gt.true_exception is not None

    gateway, ledger, bank, gt = generate_partial_refund("TXN00000004", "STL00000004", "ORD00000004", "BANK00000004", amount, date, "INR")
    assert gt.true_refund is not None

    gateway, ledger, bank, gt = generate_duplicate("TXN00000005", "STL00000005", "ORD00000005", "BANK00000005", amount, date, "INR")
    assert gt.true_match is False

    gateway, ledger, bank, gt = generate_rounding("TXN00000006", "STL00000006", "ORD00000006", "BANK00000006", amount, date, "INR")
    assert gt.true_exception is not None

    gateway, ledger, bank, gt = generate_wrong_reference("TXN00000007", "STL00000007", "ORD00000007", "BANK00000007", amount, date, "INR")
    assert gt.true_exception is not None

    gateway, ledger, bank, gt = generate_ambiguous("TXN00000008", "STL00000008", "ORD00000008", "BANK00000008", amount, date, "INR")
    assert gt.true_exception is not None

    gateway, ledger, bank, gt = generate_unexplained("TXN00000009", "STL00000009", "ORD00000009", "BANK00000009", amount, date, "INR")
    assert gt.true_exception is not None


def test_partial_refund_arithmetic_consistency():
    date = datetime.now()
    amount = Decimal("1000")

    gateway, ledger, bank, gt = generate_partial_refund("TXN00000001", "STL00000001", "ORD00000001", "BANK00000001", amount, date, "INR")

    assert ledger.refund_amount > Decimal("0")
    assert ledger.refund_amount < amount
    assert gateway.net_amount == amount - ledger.refund_amount
    assert bank.credit_amount == amount - ledger.refund_amount


def test_delayed_settlement_date_consistency():
    date = datetime.now()
    amount = Decimal("1000")

    gateway, ledger, bank, gt = generate_delayed_settlement("TXN00000001", "STL00000001", "ORD00000001", "BANK00000001", amount, date, "INR")

    assert gateway.settlement_date > date
    assert bank.value_date > date
    assert gateway.settlement_date == bank.value_date


def test_duplicate_creates_actual_duplication():
    date = datetime.now()
    amount = Decimal("1000")

    gateway, ledger, bank, gt = generate_duplicate("TXN00000001", "STL00000001", "ORD00000001", "BANK00000001", amount, date, "INR")

    assert gt.true_match is False
    assert gt.true_exception is not None


def test_wrong_reference_differs_from_true_reference():
    date = datetime.now()
    amount = Decimal("1000")

    gateway, ledger, bank, gt = generate_wrong_reference("TXN00000001", "STL00000001", "ORD00000001", "BANK00000001", amount, date, "INR")

    assert ledger.internal_reference != "TXN00000001"


def test_financial_values_valid():
    config = GeneratorConfig(num_transactions=50, seed=42)
    generator = DataGenerator(config)
    gateway, ledger, bank, gt = generator.generate()

    for rec in gt.records.values():
        if rec.true_exception is None:
            assert rec.true_amount > Decimal("0")
            assert rec.financial_exposure == Decimal("0")


def test_same_seed_produces_reproducible_output():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir)

        config = GeneratorConfig(num_transactions=10, seed=42)
        gen1 = DataGenerator(config)
        gen1.generate()
        gen1.write_csvs(output_path / "run1")
        gen1.write_ground_truth(output_path / "run1" / "ground_truth.json")

        gen2 = DataGenerator(config)
        gen2.generate()
        gen2.write_csvs(output_path / "run2")
        gen2.write_ground_truth(output_path / "run2" / "ground_truth.json")

        with open(output_path / "run1" / "ground_truth.json") as f1:
            gt1 = json.load(f1)
        with open(output_path / "run2" / "ground_truth.json") as f2:
            gt2 = json.load(f2)

        assert gt1 == gt2


def test_csv_files_are_written():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir)

        config = GeneratorConfig(num_transactions=10, seed=42)
        generator = DataGenerator(config)
        generator.generate()
        generator.write_csvs(output_path)

        assert (output_path / "gateway.csv").exists()
        assert (output_path / "ledger.csv").exists()
        assert (output_path / "bank.csv").exists()


def test_ground_truth_json_is_written():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir)

        config = GeneratorConfig(num_transactions=10, seed=42)
        generator = DataGenerator(config)
        generator.generate()
        generator.write_ground_truth(output_path / "ground_truth.json")

        assert (output_path / "ground_truth.json").exists()

        with open(output_path / "ground_truth.json") as f:
            data = json.load(f)
            assert isinstance(data, dict)
            assert len(data) > 0


def test_generate_default_function():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir)
        generate_default(output_path)

        assert (output_path / "gateway.csv").exists()
        assert (output_path / "ledger.csv").exists()
        assert (output_path / "bank.csv").exists()
        assert (output_path / "ground_truth.json").exists()


def test_ground_truth_to_dict():
    gt = GroundTruth()
    record = GroundTruthRecord(
        logical_transaction_id="TXN00000001",
        gateway_record_id="STL00000001",
        ledger_record_id="ORD00000001",
        bank_record_id="BANK00000001",
        true_match=True,
        true_exception=None,
        true_amount=Decimal("1000"),
        true_refund=None,
        true_settlement_date=datetime.now(),
        financial_exposure=Decimal("0"),
    )
    gt.add_record(record)

    gt_dict = gt.to_dict()
    assert "TXN00000001" in gt_dict
    assert gt_dict["TXN00000001"]["true_match"] is True
    assert gt_dict["TXN00000001"]["true_amount"] == "1000"
