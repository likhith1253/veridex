"""
Exception Management & Aging Service for Project Sentinel.

Provides:
- Exception querying with multi-criteria filtering (status, category, risk, amount, age, source, transaction_id)
- Pagination support (page, page_size)
- Single exception detail retrieval with full structured evidence
- Exception aging analysis (<1d, 1-3d, 3-7d, 7-30d, 30+d) with counts and financial exposure
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    Exception as ExceptionORM,
    Investigation as InvestigationORM,
    Transaction as TransactionORM,
)


@dataclass
class ExceptionDetail:
    """Complete detail of an exception record for investigation screens."""
    exception_id: str
    run_id: str
    transaction_id: Optional[str]
    category: str
    status: str
    confidence: float
    financial_exposure_inr: float
    expected_cost_inr: float
    explanation: str
    evidence: dict[str, Any]
    recommended_action: str
    resolved: bool
    created_at: Optional[str]
    investigation_conclusion: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExceptionAgingBucket:
    """Aging bucket breakdown."""
    bucket: str  # "<1 day", "1-3 days", "3-7 days", "7-30 days", "30+ days"
    count: int = 0
    financial_exposure_inr: float = 0.0


@dataclass
class ExceptionAgingReport:
    """Consolidated exception aging report."""
    total_open_exceptions: int = 0
    total_aging_exposure_inr: float = 0.0
    buckets: list[dict[str, Any]] = field(default_factory=list)
    as_of: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ExceptionManagementService:
    """Service providing exception filtering, single-view, and aging analytics."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_exceptions(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        min_exposure: Optional[Decimal] = None,
        max_exposure: Optional[Decimal] = None,
        transaction_id: Optional[str] = None,
        run_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[dict[str, Any]], int]:
        """Query exceptions with filtering and pagination."""
        stmt = select(ExceptionORM)
        conditions = []

        if status:
            conditions.append(ExceptionORM.status == status)
        if category:
            conditions.append(ExceptionORM.exception_category == category)
        if min_exposure is not None:
            conditions.append(ExceptionORM.financial_exposure >= min_exposure)
        if max_exposure is not None:
            conditions.append(ExceptionORM.financial_exposure <= max_exposure)
        if transaction_id:
            conditions.append(ExceptionORM.transaction_id == transaction_id)
        if run_id:
            conditions.append(ExceptionORM.run_id == run_id)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_res = await self.session.execute(count_stmt)
        total_count = count_res.scalar_one() or 0

        # Paginate
        stmt = stmt.order_by(ExceptionORM.financial_exposure.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        res = await self.session.execute(stmt)
        excs = res.scalars().all()

        results = []
        for e in excs:
            raw_cat = getattr(e, "exception_category", getattr(e, "category", "unknown"))
            cat_str = raw_cat.value if hasattr(raw_cat, "value") else str(raw_cat)

            results.append({
                "exception_id": e.id,
                "run_id": e.run_id,
                "transaction_id": e.transaction_id,
                "category": cat_str,
                "status": e.status,
                "confidence": float(e.confidence or 0.0),
                "financial_exposure_inr": float(e.financial_exposure or 0.0),
                "expected_cost_inr": float(e.expected_cost or 0.0),
                "explanation": e.explanation,
                "recommended_action": e.recommended_action or "escalate_manual",
                "resolved": e.resolved,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            })

        return results, total_count

    async def get_exception_detail(self, exception_id: str) -> ExceptionDetail:
        """Fetch complete detail of an exception including evidence and investigation."""
        stmt = select(ExceptionORM).where(ExceptionORM.id == exception_id)
        res = await self.session.execute(stmt)
        e = res.scalar_one_or_none()

        if not e:
            raise ValueError(f"Exception not found: {exception_id}")

        raw_cat = getattr(e, "exception_category", getattr(e, "category", "unknown"))
        cat_str = raw_cat.value if hasattr(raw_cat, "value") else str(raw_cat)

        # Check for investigation conclusion
        inv_stmt = select(InvestigationORM).where(InvestigationORM.exception_id == exception_id)
        inv_res = await self.session.execute(inv_stmt)
        inv = inv_res.scalar_one_or_none()

        inv_data = None
        if inv:
            inv_data = {
                "investigation_id": inv.id,
                "method": inv.method,
                "root_cause": inv.root_cause,
                "confidence": float(inv.confidence or 0.0),
                "explanation": (inv.evidence or {}).get("explanation", inv.root_cause),
                "recommended_action": inv.recommended_action,
                "requires_human_review": inv.requires_human_review,
                "created_at": inv.created_at.isoformat() if inv.created_at else None,
            }

        return ExceptionDetail(
            exception_id=e.id,
            run_id=e.run_id,
            transaction_id=e.transaction_id,
            category=cat_str,
            status=e.status,
            confidence=float(e.confidence or 0.0),
            financial_exposure_inr=float(e.financial_exposure or 0.0),
            expected_cost_inr=float(e.expected_cost or 0.0),
            explanation=e.explanation,
            evidence=e.evidence or {},
            recommended_action=e.recommended_action or "escalate_manual",
            resolved=e.resolved,
            created_at=e.created_at.isoformat() if e.created_at else None,
            investigation_conclusion=inv_data,
        )

    async def calculate_exception_aging(self, run_id: Optional[str] = None) -> ExceptionAgingReport:
        """Calculate exception aging distribution across standard treasury time buckets."""
        stmt = select(ExceptionORM).where(ExceptionORM.resolved == False)
        if run_id:
            stmt = stmt.where(ExceptionORM.run_id == run_id)
        res = await self.session.execute(stmt)
        open_excs = res.scalars().all()

        now = datetime.now(timezone.utc)
        buckets_map = {
            "<1 day": ExceptionAgingBucket(bucket="<1 day"),
            "1-3 days": ExceptionAgingBucket(bucket="1-3 days"),
            "3-7 days": ExceptionAgingBucket(bucket="3-7 days"),
            "7-30 days": ExceptionAgingBucket(bucket="7-30 days"),
            "30+ days": ExceptionAgingBucket(bucket="30+ days"),
        }

        total_exp = 0.0
        for e in open_excs:
            exp = float(e.financial_exposure or 0.0)
            total_exp += exp

            created = e.created_at
            if created:
                # Ensure UTC tz
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                age_days = (now - created).total_seconds() / 86400.0
            else:
                age_days = 0.0

            if age_days < 1.0:
                b = buckets_map["<1 day"]
            elif age_days < 3.0:
                b = buckets_map["1-3 days"]
            elif age_days < 7.0:
                b = buckets_map["3-7 days"]
            elif age_days < 30.0:
                b = buckets_map["7-30 days"]
            else:
                b = buckets_map["30+ days"]

            b.count += 1
            b.financial_exposure_inr += exp

        return ExceptionAgingReport(
            total_open_exceptions=len(open_excs),
            total_aging_exposure_inr=round(total_exp, 2),
            buckets=[asdict(b) for b in buckets_map.values()],
        )
