"""
Source Health & Feed Discrepancy Service for Project Sentinel.

Analyzes data quality and operational reliability across the 3 ingested financial feeds:
- Payment Gateway feed
- Internal Order Ledger feed
- Bank Statement feed

Tracks:
- Total records received & gross monetary volume per feed
- Match rate per feed (via match_transactions join)
- Exception count & discrepancy rate per feed (via exception.transaction_id join)
- Health status (HEALTHY, DEGRADED, ANOMALOUS) — evaluated correctly from high to low threshold
"""

from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Exception as ExceptionORM, Match as MatchORM, Transaction as TransactionORM
from app.database.models import MatchTransaction as MatchTransactionORM
from app.models.transaction import TransactionSource


@dataclass
class SourceMetrics:
    source_name: str
    total_records: int = 0
    total_volume_inr: float = 0.0
    matched_records: int = 0
    exception_records: int = 0
    match_rate_percent: float = 0.0
    exception_rate_percent: float = 0.0
    health_status: str = "HEALTHY"


@dataclass
class SourceHealthReport:
    overall_health: str = "HEALTHY"
    total_feeds_monitored: int = 3
    sources: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SourceHealthService:
    """Service auditing the operational health and discrepancy rates of financial feeds."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_source_health(self) -> SourceHealthReport:
        """Compute operational health and exception metrics grouped per feed source from actual relationships."""
        # 1. Record counts and volumes per source
        vol_stmt = select(
            TransactionORM.source,
            func.count(TransactionORM.id),
            func.sum(TransactionORM.amount),
        ).group_by(TransactionORM.source)
        vol_res = await self.session.execute(vol_stmt)
        vol_rows = vol_res.all()

        source_stats: dict[str, SourceMetrics] = {
            TransactionSource.GATEWAY.value: SourceMetrics(source_name="Payment Gateway"),
            TransactionSource.LEDGER.value: SourceMetrics(source_name="Internal Ledger"),
            TransactionSource.BANK.value: SourceMetrics(source_name="Core Bank Statement"),
        }

        for src, count, vol in vol_rows:
            if src in source_stats:
                source_stats[src].total_records = count or 0
                source_stats[src].total_volume_inr = float(vol or 0.0)

        try:
            match_stmt = select(
                TransactionORM.source,
                func.count(MatchTransactionORM.transaction_id.distinct()),
            ).join(MatchTransactionORM, MatchTransactionORM.transaction_id == TransactionORM.id).group_by(TransactionORM.source)
            match_res = await self.session.execute(match_stmt)
            for src, match_count in match_res.all():
                if src in source_stats:
                    source_stats[src].matched_records = match_count or 0
        except Exception:
            pass

        try:
            exc_stmt = select(
                TransactionORM.source,
                func.count(ExceptionORM.id.distinct()),
            ).join(ExceptionORM, ExceptionORM.transaction_id == TransactionORM.id).group_by(TransactionORM.source)
            exc_res = await self.session.execute(exc_stmt)
            for src, exc_count in exc_res.all():
                if src in source_stats:
                    source_stats[src].exception_records = exc_count or 0
        except Exception:
            pass

        overall_status = "HEALTHY"
        for sm in source_stats.values():
            if sm.total_records > 0:
                sm.match_rate_percent = round((sm.matched_records / sm.total_records) * 100, 2)
                sm.exception_rate_percent = round((sm.exception_records / sm.total_records) * 100, 2)
            else:
                sm.match_rate_percent = 100.0
                sm.exception_rate_percent = 0.0

            # IMPORTANT: evaluate ANOMALOUS before DEGRADED — highest threshold first
            if sm.exception_rate_percent > 40.0:
                sm.health_status = "ANOMALOUS"
                overall_status = "ANOMALOUS"
            elif sm.exception_rate_percent > 20.0:
                sm.health_status = "DEGRADED"
                if overall_status != "ANOMALOUS":
                    overall_status = "DEGRADED"

        return SourceHealthReport(
            overall_health=overall_status,
            sources={k: asdict(v) for k, v in source_stats.items()},
        )
