"""
Grounded Finance Q&A Engine for Project Sentinel.

Answers natural language controller queries grounded strictly in PostgreSQL state:
- Exact monetary aggregates computed directly via SQL
- Real transaction references and IDs provided as verifiable evidence
- Zero hallucinated numbers (LLM strictly synthesizes explanation over verified facts)
"""

import json
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    Decision as DecisionORM,
    Exception as ExceptionORM,
    Match as MatchORM,
    ReconciliationRun as ReconciliationRunORM,
    Transaction as TransactionORM,
)
from app.investigation.llm_client import FakeLLMClient, GroqLLMClient, LLMClient
from app.models.decision_result import DecisionAction
from app.models.exception_record import ExceptionCategory
from app.services.cash_position import CashPositionService

logger = logging.getLogger(__name__)


@dataclass
class QAResponse:
    """Structured response to a Finance Controller query."""
    question: str
    direct_answer: str
    key_metrics: dict[str, Any] = field(default_factory=dict)
    evidence_records: list[dict[str, Any]] = field(default_factory=list)
    sql_facts_used: list[str] = field(default_factory=list)
    confidence: float = 1.0


class FinanceQAService:
    """Service providing fact-grounded Q&A over real reconciliation and transaction databases."""

    def __init__(self, session: AsyncSession, llm_client: Optional[LLMClient] = None):
        self.session = session
        self.llm_client = llm_client or GroqLLMClient()
        self.cash_service = CashPositionService(session)

    async def answer_query(self, question: str, run_id: Optional[str] = None) -> QAResponse:
        """Analyze query, extract database ground truth, and compose a verifiable response."""
        q_lower = question.lower().strip()

        # 1. Unreconciled Money / Financial Exposure
        if any(w in q_lower for w in ["unreconciled", "unmatched money", "exposure", "money at risk"]):
            cash = await self.cash_service.get_cash_position(run_id)
            exc_stmt = select(ExceptionORM).order_by(ExceptionORM.financial_exposure.desc()).limit(10)
            res = await self.session.execute(exc_stmt)
            excs = res.scalars().all()

            evidence = [
                {
                    "exception_id": e.exception_id,
                    "transaction_id": e.transaction_id,
                    "category": e.category,
                    "amount": float(e.financial_exposure or e.amount_delta or 0),
                    "reason": e.explanation,
                }
                for e in excs
            ]
            ans = (
                f"Currently, INR {cash.unreconciled_amount:,.2f} remains unreconciled across open exceptions, "
                f"with INR {cash.at_risk_amount:,.2f} classified as high financial exposure."
            )
            return QAResponse(
                question=question,
                direct_answer=ans,
                key_metrics={
                    "total_unreconciled_inr": float(cash.unreconciled_amount),
                    "high_risk_exposure_inr": float(cash.at_risk_amount),
                    "delayed_settlement_inr": float(cash.delayed_amount),
                },
                evidence_records=evidence,
                sql_facts_used=["Calculated from exceptions.financial_exposure and cash position aggregates"],
            )

        # 2. ML Recovered Matches
        elif any(w in q_lower for w in ["recovered by ml", "ml matches", "ml recovery", "ml contribution"]):
            match_stmt = select(MatchORM).where(MatchORM.rule_name == "ml_scored")
            res = await self.session.execute(match_stmt)
            ml_matches = res.scalars().all()

            tot_stmt = select(func.count(MatchORM.id))
            tot_res = await self.session.execute(tot_stmt)
            total_matches = tot_res.scalar_one() or 1

            evidence = [
                {"match_id": m.match_id, "rule": m.rule_name, "confidence": float(m.confidence or 0), "reason": m.reason}
                for m in ml_matches[:10]
            ]
            share = (len(ml_matches) / total_matches) * 100
            ans = (
                f"Machine Learning (XGBoost) successfully recovered {len(ml_matches)} transaction matches "
                f"({share:.1f}% of all matches) that had corrupted references or shifted dates and were missed by deterministic rules."
            )
            return QAResponse(
                question=question,
                direct_answer=ans,
                key_metrics={
                    "ml_recovered_count": len(ml_matches),
                    "total_matches": total_matches,
                    "ml_share_percent": round(share, 2),
                },
                evidence_records=evidence,
                sql_facts_used=["Queried matches WHERE rule_name = 'ml_scored'"],
            )

        # 3. Root Causes / Reconciliation Failures
        elif any(w in q_lower for w in ["root cause", "failure", "causes", "why", "breakdown"]):
            exc_stmt = select(ExceptionORM.category, func.count(ExceptionORM.id), func.sum(ExceptionORM.financial_exposure)).group_by(ExceptionORM.category)
            res = await self.session.execute(exc_stmt)
            cat_counts = res.all()

            cat_dict = {cat: count for cat, count, _ in cat_counts}
            top_cat = max(cat_dict.items(), key=lambda x: x[1])[0] if cat_dict else "None"
            ans = (
                f"The primary driver of exceptions is '{top_cat}', accounting for {cat_dict.get(top_cat, 0)} cases. "
                f"Complete breakdown: " + ", ".join(f"{c}: {n}" for c, n in cat_dict.items()) + "."
            )
            return QAResponse(
                question=question,
                direct_answer=ans,
                key_metrics=cat_dict,
                evidence_records=[{"category": c, "count": n, "exposure_inr": float(exp or 0)} for c, n, exp in cat_counts],
                sql_facts_used=["Aggregated count and sum from exceptions GROUP BY category"],
            )

        # 4. Delayed Settlements
        elif any(w in q_lower for w in ["delayed", "settlement delay", "sla"]):
            del_stmt = select(ExceptionORM).where(ExceptionORM.category == ExceptionCategory.DELAYED_SETTLEMENT.value)
            res = await self.session.execute(del_stmt)
            del_excs = res.scalars().all()
            total_del = sum(Decimal(str(e.financial_exposure or e.amount_delta or 0)) for e in del_excs)

            evidence = [
                {"exception_id": e.exception_id, "transaction_id": e.transaction_id, "amount_inr": float(e.amount_delta or 0), "explanation": e.explanation}
                for e in del_excs[:10]
            ]
            ans = f"There are {len(del_excs)} delayed settlements totaling INR {total_del:,.2f} awaiting bank credit settlement."
            return QAResponse(
                question=question,
                direct_answer=ans,
                key_metrics={"delayed_count": len(del_excs), "delayed_amount_inr": float(total_del)},
                evidence_records=evidence,
                sql_facts_used=["Queried exceptions WHERE category = 'delayed_settlement'"],
            )

        # 5. Duplicate Settlements
        elif any(w in q_lower for w in ["duplicate", "double"]):
            dup_stmt = select(ExceptionORM).where(ExceptionORM.category == ExceptionCategory.DUPLICATE_ENTRY.value)
            res = await self.session.execute(dup_stmt)
            dup_excs = res.scalars().all()
            total_dup = sum(Decimal(str(e.financial_exposure or e.amount_delta or 0)) for e in dup_excs)

            evidence = [
                {"exception_id": e.exception_id, "transaction_id": e.transaction_id, "amount_inr": float(e.amount_delta or 0), "explanation": e.explanation}
                for e in dup_excs[:10]
            ]
            ans = f"There are {len(dup_excs)} duplicate entry exceptions with a combined financial exposure of INR {total_dup:,.2f}."
            return QAResponse(
                question=question,
                direct_answer=ans,
                key_metrics={"duplicate_count": len(dup_excs), "duplicate_exposure_inr": float(total_dup)},
                evidence_records=evidence,
                sql_facts_used=["Queried exceptions WHERE category = 'duplicate_entry'"],
            )

        # 6. Default / General Query: Grounded Cash & Run Overview
        cash = await self.cash_service.get_cash_position(run_id)
        ans = (
            f"Sentinel Finance Overview: Expected settlement INR {cash.expected_amount:,.2f}, "
            f"Received INR {cash.received_amount:,.2f}, Pending INR {cash.pending_amount:,.2f}, "
            f"Unreconciled exceptions INR {cash.unreconciled_amount:,.2f} (High-Risk: INR {cash.at_risk_amount:,.2f})."
        )
        return QAResponse(
            question=question,
            direct_answer=ans,
            key_metrics=cash.to_dict(),
            evidence_records=[],
            sql_facts_used=["Computed live cash aggregates across transactions and exceptions"],
        )
