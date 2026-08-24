import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.models.transaction import Transaction, TransactionSource
from app.services.normalization import NormalizationService
from eval.config import BenchmarkConfig
from simulator.generator import DataGenerator, GeneratorConfig
from simulator.ground_truth import GroundTruth


@dataclass
class BenchmarkDataset:
    """Container for benchmark transactions, ground truth, and metadata."""
    name: str
    config: BenchmarkConfig
    transactions_by_source: dict[TransactionSource, list[Transaction]]
    ground_truth: GroundTruth
    total_transactions: int
    gateway_count: int
    ledger_count: int
    bank_count: int

    @property
    def all_transactions(self) -> list[Transaction]:
        """Flattened list of all transactions across all sources."""
        all_txns = []
        for txns in self.transactions_by_source.values():
            all_txns.extend(txns)
        return all_txns


def generate_benchmark_dataset(config: Optional[BenchmarkConfig] = None) -> BenchmarkDataset:
    """Generate a reproducible benchmark dataset using the simulator and normalization service.

    Args:
        config: Benchmark configuration with seed, transaction count, and scenario distribution.

    Returns:
        BenchmarkDataset ready for evaluation.
    """
    cfg = config or BenchmarkConfig()

    sim_config = GeneratorConfig(
        num_transactions=cfg.num_transactions,
        seed=cfg.seed,
        scenario_distribution=cfg.scenario_distribution,
        currency=cfg.currency,
        date_range_days=cfg.date_range_days,
        min_amount=int(cfg.min_amount),
        max_amount=int(cfg.max_amount),
    )

    generator = DataGenerator(sim_config)
    generator.generate()

    # Use a temporary directory to serialize and normalize through the official NormalizationService
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        generator.write_csvs(tmp_path)
        generator.write_ground_truth(tmp_path / "ground_truth.json")

        transactions_by_source = NormalizationService.load_all(
            gateway_path=tmp_path / "gateway.csv",
            ledger_path=tmp_path / "ledger.csv",
            bank_path=tmp_path / "bank.csv",
        )

    # If an output directory is configured, also persist the dataset files there
    if cfg.output_dir:
        out_path = Path(cfg.output_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        generator.write_csvs(out_path)
        generator.write_ground_truth(out_path / "ground_truth.json")

    gw_count = len(transactions_by_source.get(TransactionSource.GATEWAY, []))
    ld_count = len(transactions_by_source.get(TransactionSource.LEDGER, []))
    bk_count = len(transactions_by_source.get(TransactionSource.BANK, []))
    total_count = gw_count + ld_count + bk_count

    return BenchmarkDataset(
        name=f"benchmark_seed_{cfg.seed}_n_{cfg.num_transactions}",
        config=cfg,
        transactions_by_source=transactions_by_source,
        ground_truth=generator.ground_truth,
        total_transactions=total_count,
        gateway_count=gw_count,
        ledger_count=ld_count,
        bank_count=bk_count,
    )
