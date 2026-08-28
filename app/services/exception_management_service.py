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

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.mappers.exception_mapper import _DOMAIN_TO_ORM_CATEGORY, _ORM_TO_DOMAIN_CATEGORY
from app.database.models import (
    Exception as ExceptionORM,
    Investigation as InvestigationORM,
    Transaction as TransactionORM,
)
from app.models.exception_record import ExceptionCategory as DomainExceptionCategory


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
        stmt = (
            select(ExceptionORM, TransactionORM.amount)
            .outerjoin(TransactionORM, ExceptionORM.transaction_id == TransactionORM.id)
        )
        conditions = []

        if status:
            conditions.append(ExceptionORM.status == status)
        if category:
            # Match both raw string and mapped domain/ORM representations
            cat_candidates = {category}
            for d_cat, o_cat in _DOMAIN_TO_ORM_CATEGORY.items():
                if d_cat.value == category or o_cat.value == category:
                    cat_candidates.add(d_cat.value)
                    cat_candidates.add(o_cat.value)
            conditions.append(ExceptionORM.exception_category.in_(list(cat_candidates)))

        if min_exposure is not None:
            conditions.append(
                or_(
                    ExceptionORM.financial_exposure >= min_exposure,
                    and_(
                        ExceptionORM.financial_exposure == Decimal("0"),
                        TransactionORM.amount >= min_exposure,
                    ),
                )
            )
        if max_exposure is not None:
            conditions.append(
                or_(
                    ExceptionORM.financial_exposure <= max_exposure,
                    and_(
                        ExceptionORM.financial_exposure == Decimal("0"),
                        TransactionORM.amount <= max_exposure,
                    ),
                )
            )
        if transaction_id:
            conditions.append(
                or_(
                    ExceptionORM.transaction_id == transaction_id,
                    TransactionORM.id == transaction_id,
                    TransactionORM.domain_transaction_id == transaction_id,
                )
            )
        if run_id:
            conditions.append(ExceptionORM.run_id == run_id)

        if conditions:
            stmt = stmt.where(and_(*conditions))

        # Count total
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_res = await self.session.execute(count_stmt)
        total_count = count_res.scalar_one() or 0

        # Paginate
        stmt = stmt.order_by(ExceptionORM.financial_exposure.desc(), ExceptionORM.created_at.desc())
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        res = await self.session.execute(stmt)
        exc_rows = res.all()

        results = []
        for e, txn_amt in exc_rows:
            raw_cat = getattr(e, "exception_category", getattr(e, "category", "unexplained"))
            cat_str = raw_cat.value if hasattr(raw_cat, "value") else str(raw_cat)
            if cat_str in ("unknown", "None", ""):
                cat_str = "unexplained"

            stored_exp = float(e.financial_exposure or 0.0)
            exp_amt = stored_exp if stored_exp > 0.0 else float(txn_amt or 0.0)
            stored_cost = float(e.expected_cost or 0.0)
            cost_amt = stored_cost if stored_cost > 0.0 else exp_amt

            action = e.recommended_action
            if not action or action == "escalate_manual":
                if cat_str in ("duplicate_record", "duplicate_entry"):
                    action = "flag_duplicate"
                elif cat_str in ("amount_mismatch", "fee_mismatch"):
                    action = "request_credit_note"
                elif cat_str in ("timing_mismatch", "delayed_settlement"):
                    action = "await_settlement_window"
                elif cat_str in ("missing_record", "ambiguous_match"):
                    action = "trace_missing_source"
                else:
                    action = "investigate"

            results.append({
                "exception_id": e.id,
                "run_id": e.run_id,
                "transaction_id": e.transaction_id,
                "category": cat_str,
                "status": e.status,
                "confidence": float(e.confidence or 0.0),
                "financial_exposure_inr": exp_amt,
                "expected_cost_inr": cost_amt,
                "explanation": e.explanation,
                "recommended_action": action,
                "resolved": e.resolved,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            })

        return results, total_count

    async def get_exception_detail(self, exception_id: str) -> ExceptionDetail:
        """Fetch complete detail of an exception including evidence and investigation."""
        stmt = (
            select(ExceptionORM, TransactionORM.amount)
            .outerjoin(TransactionORM, ExceptionORM.transaction_id == TransactionORM.id)
            .where(ExceptionORM.id == exception_id)
        )
        res = await self.session.execute(stmt)
        row = res.first()

        if not row:
            raise ValueError(f"Exception not found: {exception_id}")

        e, txn_amt = row
        raw_cat = getattr(e, "exception_category", getattr(e, "category", "unexplained"))
        cat_str = raw_cat.value if hasattr(raw_cat, "value") else str(raw_cat)
        if cat_str in ("unknown", "None", ""):
            cat_str = "unexplained"

        stored_exp = float(e.financial_exposure or 0.0)
        exp_amt = stored_exp if stored_exp > 0.0 else float(txn_amt or 0.0)
        stored_cost = float(e.expected_cost or 0.0)
        cost_amt = stored_cost if stored_cost > 0.0 else exp_amt

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

        action = e.recommended_action or (inv.recommended_action if inv else "investigate")

        return ExceptionDetail(
            exception_id=e.id,
            run_id=e.run_id,
            transaction_id=e.transaction_id,
            category=cat_str,
            status=e.status,
            confidence=float(e.confidence or 0.0),
            financial_exposure_inr=exp_amt,
            expected_cost_inr=cost_amt,
            explanation=e.explanation,
            evidence=e.evidence or {},
            recommended_action=action,
            resolved=e.resolved,
            created_at=e.created_at.isoformat() if e.created_at else None,
            investigation_conclusion=inv_data,
        )

    async def calculate_exception_aging(self, run_id: Optional[str] = None) -> ExceptionAgingReport:
        """Calculate exception aging distribution across standard treasury time buckets."""
        stmt = (
            select(ExceptionORM, TransactionORM.amount)
            .outerjoin(TransactionORM, ExceptionORM.transaction_id == TransactionORM.id)
            .where(ExceptionORM.resolved == False)
        )
        if run_id:
            stmt = stmt.where(ExceptionORM.run_id == run_id)
        res = await self.session.execute(stmt)
        open_excs = res.all()

        now = datetime.now(timezone.utc)
        buckets_map = {
            "<1 day": ExceptionAgingBucket(bucket="<1 day"),
            "1-3 days": ExceptionAgingBucket(bucket="1-3 days"),
            "3-7 days": ExceptionAgingBucket(bucket="3-7 days"),
            "7-30 days": ExceptionAgingBucket(bucket="7-30 days"),
            "30+ days": ExceptionAgingBucket(bucket="30+ days"),
        }

        total_exp = 0.0
        for e, txn_amt in open_excs:
            stored_exp = float(e.financial_exposure or 0.0)
            exp = stored_exp if stored_exp > 0.0 else float(txn_amt or 0.0)
            total_exp += exp

            created = e.created_at
            if created:
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
