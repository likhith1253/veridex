"""
Real-Time Transaction Stream Simulator for Project Sentinel (Razorpay Track 4).

Simulates asynchronous multi-source incoming financial streams:
- Gateway Events (settlement captured / failed)
- Ledger Events (internal order booking)
- Bank Statement Events (clearing & settlement credits)

Injects configurable operational realities:
- Clean deterministic transactions (50-60%)
- Delayed settlements (5-10%)
- Corrupted references / typos (10%)
- Corrupted order IDs (10%)
- Fee discrepancies (5%)
- Duplicate transactions (5-10%)
- Ambiguous candidate clusters (5-10%)
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import AsyncGenerator, Optional

from app.models.transaction import Transaction, TransactionSource, TransactionStatus
from simulator.generator import DataGenerator, GeneratorConfig


@dataclass
class StreamConfig:
    """Configuration for real-time transaction streaming."""
    batch_size: int = 50
    delay_between_events_sec: float = 0.05
    corruption_rate: float = 0.10
    duplicate_rate: float = 0.05
    delay_rate: float = 0.08
    seed: int = 42


class RealTimeStreamSimulator:
    """Simulates real-time asynchronous multi-source financial transaction events."""

    def __init__(self, config: Optional[StreamConfig] = None):
        self.config = config or StreamConfig()

    async def stream_events(self, num_transactions: Optional[int] = None) -> AsyncGenerator[Transaction, None]:
        """Yield canonical Transaction events simulating live multi-feed ingestion."""
        n = num_transactions or self.config.batch_size
        sim_cfg = GeneratorConfig(
            num_transactions=n,
            seed=self.config.seed,
            scenario_distribution={
                "normal": 0.55,
                "delayed_settlement": self.config.delay_rate,
                "fee_mismatch": 0.07,
                "wrong_reference": self.config.corruption_rate,
                "unexplained": self.config.corruption_rate,
                "ambiguous": 0.08,
                "duplicate": self.config.duplicate_rate,
            },
        )
        gen = DataGenerator(sim_cfg)
        gen.generate()

        # Interleave Gateway -> Ledger -> Bank events with slight delays
        records_pool = []
        for i in range(len(gen.gateway_records)):
            gw = gen.gateway_records[i]
            ld = gen.ledger_records[i]
            bk = gen.bank_records[i]

            # Convert to Transaction domain models
            t_gw = Transaction(
                txn_id=gw.transaction_id,
                source=TransactionSource.GATEWAY,
                amount=gw.gross_amount,
                currency=gw.currency,
                timestamp=gw.settlement_date,
                status=TransactionStatus.COMPLETED,
                order_id=gw.order_id,
                reference_number=gw.utr,
                narration=f"Gateway settlement {gw.settlement_id}",
                metadata={"settlement_id": gw.settlement_id, "fee": str(gw.fee), "tax": str(gw.tax)},
            )
            t_ld = Transaction(
                txn_id=ld.order_id,
                source=TransactionSource.LEDGER,
                amount=ld.transaction_amount,
                currency=ld.currency,
                timestamp=ld.order_date,
                status=TransactionStatus.COMPLETED,
                order_id=ld.order_id,
                reference_number=ld.internal_reference,
                narration=f"Ledger entry for {ld.order_id}",
            )
            t_bk = Transaction(
                txn_id=bk.bank_transaction_id,
                source=TransactionSource.BANK,
                amount=bk.credit_amount,
                currency=bk.currency,
                timestamp=bk.value_date,
                status=TransactionStatus.COMPLETED,
                order_id=ld.order_id if "PAYMENT FOR" in bk.narration else None,
                reference_number=bk.utr,
                narration=bk.narration,
            )
            records_pool.extend([t_gw, t_ld, t_bk])

        for txn in records_pool:
            if self.config.delay_between_events_sec > 0:
                await asyncio.sleep(self.config.delay_between_events_sec)
            yield txn
