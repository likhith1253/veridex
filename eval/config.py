from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Optional


@dataclass
class RiskBucketConfig:
    """Configuration for monetary value risk buckets."""
    low_threshold: Decimal = Decimal("10000")       # < 10,000
    medium_threshold: Decimal = Decimal("50000")    # 10,000 - 50,000
    high_threshold: Decimal = Decimal("200000")     # 50,000 - 200,000
    # > 200,000 is critical/very high


@dataclass
class BenchmarkConfig:
    """Configuration for benchmark dataset generation."""
    num_transactions: int = 500
    seed: int = 42
    currency: str = "INR"
    date_range_days: int = 30
    min_amount: int = 500
    max_amount: int = 500000
    scenario_distribution: dict[str, float] = field(
        default_factory=lambda: {
            "normal": 0.70,
            "delayed_settlement": 0.06,
            "fee_mismatch": 0.05,
            "partial_refund": 0.05,
            "duplicate": 0.04,
            "rounding": 0.03,
            "wrong_reference": 0.03,
            "ambiguous": 0.02,
            "unexplained": 0.02,
        }
    )
    output_dir: Optional[Path] = None


@dataclass
class EvaluationConfig:
    """Overall evaluation run configuration."""
    benchmark_config: BenchmarkConfig = field(default_factory=BenchmarkConfig)
    risk_config: RiskBucketConfig = field(default_factory=RiskBucketConfig)
    enable_ml_scoring: bool = False
    save_reports: bool = True
    report_output_dir: Path = field(default_factory=lambda: Path("data/eval_reports"))
