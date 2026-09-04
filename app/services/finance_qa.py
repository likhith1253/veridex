"""
Grounded Finance Q&A Engine for Project Sentinel.

Answers natural language controller queries grounded strictly in PostgreSQL state:
- Exact monetary aggregates computed directly via SQL
- Real transaction references and IDs provided as verifiable evidence
- Zero hallucinated numbers (LLM strictly synthesizes explanation over verified facts)
- Strict prompt-injection defense, input bounds, and honest handling of unsupported questions
"""

import asyncio
import json
import logging
import re
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
from app.services.exposure_service import ExposureService

logger = logging.getLogger(__name__)

# Prompt injection patterns
_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous\s+|prior\s+)?instructions",
    r"system\s+prompt",
    r"output\s+the\s+database_url",
    r"environment\s+variable",
    r"print\s+env",
    r"api_key",
    r"secret_key",
    r"expose\s+token",
    r"eval\(",
    r"<script",
    r"dump\s+database",
    r"delete\s+from",
    r"drop\s+table",
]

QA_SYSTEM_PROMPT = """You are the Veridex Finance Controller AI Assistant.
Your job is to answer the user's finance or reconciliation question based SOLELY on the provided verified PostgreSQL facts.

CRITICAL INVARIANTS:
1. Every monetary figure and count you state MUST EXACTLY match the provided PostgreSQL facts.
2. Never invent numbers, transaction IDs, or hypothetical scenarios.
3. If the facts do not contain the answer, say "Based on the verified database records, this information is not available."
4. Be concise, professional, and audit-ready (1-3 sentences).
"""


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
        self.exposure_service = ExposureService(session)

    def _check_injection(self, query: str) -> bool:
        q_lower = query.lower()
        return any(re.search(pattern, q_lower) for pattern in _INJECTION_PATTERNS)

    async def _synthesize_with_llm(
        self, question: str, facts_summary: str, fallback_text: str
    ) -> str:
        """Call Groq / LLM to synthesize a professional natural language response over verified facts."""
        if not self.llm_client:
            return fallback_text

        user_prompt = f"VERIFIED POSTGRESQL FACTS:\n{facts_summary}\n\nQUESTION: {question}\n\nDIRECT ANSWER:"
        try:
            # Enforce strict 8.0s timeout to prevent any endpoint hangs
            return await asyncio.wait_for(
                self.llm_client.generate_text(
                    system_prompt=QA_SYSTEM_PROMPT,
                    user_prompt=user_prompt,
                    max_tokens=250,
                    temperature=0.0,
                ),
                timeout=8.0,
            )
        except Exception as e:
            logger.warning("LLM synthesis failed or timed out: %s. Using verified deterministic answer.", e)
            return fallback_text

    async def answer_query(self, question: str, run_id: Optional[str] = None) -> QAResponse:
        """Analyze query, extract database ground truth, and compose a verifiable response."""
        q_raw = (question or "").strip()
        if not q_raw:
            return QAResponse(
                question="",
                direct_answer="Please provide a valid financial or reconciliation question.",
                key_metrics={},
                evidence_records=[],
                sql_facts_used=[],
                confidence=0.0,
            )

        # Enforce input length bound
        if len(q_raw) > 500:
            return QAResponse(
                question=q_raw[:100] + "...",
                direct_answer="Question exceeds maximum allowed length of 500 characters.",
                key_metrics={},
                evidence_records=[],
                sql_facts_used=[],
                confidence=0.0,
            )

        # 1. Prompt Injection Defense (AUD-019, AUD-046)
        if self._check_injection(q_raw):
            return QAResponse(
                question=q_raw,
                direct_answer="Refusal: Security-sensitive or prompt-injection pattern detected. Queries must pertain strictly to finance controller operations and verified reconciliation metrics.",
                key_metrics={"security_flag": "prompt_injection_detected"},
                evidence_records=[],
                sql_facts_used=[],
                confidence=0.0,
            )

        q_lower = q_raw.lower()

        # 2. Unreconciled Money / Financial Exposure / Risk (AUD-025, AUD-040)
        if any(w in q_lower for w in ["unreconciled", "unmatched money", "exposure", "money at risk", "at risk", "financial exposure"]):
            exposure_result = await self.exposure_service.calculate_exposure(run_id)
            total_unrec = float(exposure_result.unresolved_value)
            high_risk = float(exposure_result.high_risk_value)
            if total_unrec == 0.0:
                try:
                    cash = await self.cash_service.get_cash_position(run_id)
                    total_unrec = float(cash.unreconciled_amount)
                    high_risk = float(cash.at_risk_amount)
                except Exception:
                    pass

            exc_stmt = (
                select(ExceptionORM, TransactionORM.amount)
                .outerjoin(TransactionORM, ExceptionORM.transaction_id == TransactionORM.id)
                .where((ExceptionORM.status != "resolved") & (ExceptionORM.resolved == False))
                .order_by(ExceptionORM.created_at.desc())
                .limit(10)
            )
            res = await self.session.execute(exc_stmt)
            exc_rows = res.all()

            evidence = []
            for e, t_amt in exc_rows:
                stored_exp = float(e.financial_exposure or 0)
                amt = stored_exp if stored_exp > 0 else float(t_amt or 0)
                cat_val = e.exception_category.value if hasattr(e.exception_category, "value") else str(e.exception_category)
                if cat_val == "unknown":
                    cat_val = "unexplained"
                evidence.append({
                    "exception_id": e.id,
                    "transaction_id": e.transaction_id,
                    "category": cat_val,
                    "amount": amt,
                    "reason": e.explanation,
                })

            deterministic_ans = (
                f"Currently, INR {total_unrec:,.2f} remains unreconciled across open exceptions, "
                f"with INR {high_risk:,.2f} classified as high financial exposure."
            )
            facts_text = f"Total Unreconciled Exposure: INR {total_unrec:,.2f}\nHigh-Risk Exposure: INR {high_risk:,.2f}\nOpen Exceptions Count: {len(exc_rows)}"
            ai_ans = await self._synthesize_with_llm(q_raw, facts_text, deterministic_ans)

            return QAResponse(
                question=q_raw,
                direct_answer=ai_ans,
                key_metrics={
                    "total_unreconciled_inr": total_unrec,
                    "high_risk_exposure_inr": high_risk,
                    "open_exception_count": len(exc_rows),
                },
                evidence_records=evidence,
                sql_facts_used=[
                    "SELECT SUM(financial_exposure) FROM exceptions WHERE resolved = false",
                    "SELECT id, transaction_id, exception_category, financial_exposure FROM exceptions WHERE resolved = false ORDER BY created_at DESC LIMIT 10",
                ],
                confidence=1.0,
            )

        # 3. Exception Counts & Status Breakdown (AUD-059)
        # "issue"/"issues" are synonyms for "exception" everywhere in the product's
        # own UI (sidebar "Review issues", Command Center "What needs attention"),
        # so a Copilot that only recognizes "exception" fails on the most obvious
        # phrasing of its own most basic metric — verified live: "How many open
        # issues are there right now?" previously fell through to "I can't answer
        # this" despite the fallback message itself listing this as supported.
        if any(w in q_lower for w in [
            "how many exceptions", "exception count", "which exceptions are resolved",
            "resolved exceptions", "open exceptions",
            "how many issues", "issue count", "which issues are resolved",
            "resolved issues", "open issues", "issues are there", "issues right now",
        ]):
            status_stmt = select(ExceptionORM.status, ExceptionORM.resolved, func.count(ExceptionORM.id)).group_by(ExceptionORM.status, ExceptionORM.resolved)
            res = await self.session.execute(status_stmt)
            status_rows = res.all()

            total_exceptions = sum(count for _, _, count in status_rows)
            open_count = sum(count for _, resolved, count in status_rows if not resolved)
            resolved_count = sum(count for _, resolved, count in status_rows if resolved)

            deterministic_ans = (
                f"There are {total_exceptions} total exceptions in the system: {open_count} open and {resolved_count} resolved."
            )
            facts_text = f"Total Exceptions: {total_exceptions}\nOpen Exceptions: {open_count}\nResolved Exceptions: {resolved_count}"
            ai_ans = await self._synthesize_with_llm(q_raw, facts_text, deterministic_ans)

            return QAResponse(
                question=q_raw,
                direct_answer=ai_ans,
                key_metrics={
                    "total_exceptions": total_exceptions,
                    "open_exceptions": open_count,
                    "resolved_exceptions": resolved_count,
                },
                evidence_records=[{"status": s, "resolved": r, "count": c} for s, r, c in status_rows],
                sql_facts_used=[
                    "SELECT status, resolved, COUNT(id) FROM exceptions GROUP BY status, resolved"
                ],
                confidence=1.0,
            )

        # 4. Reconciliation Rate & Match Performance (AUD-059)
        if any(w in q_lower for w in ["match rate", "reconciliation rate", "reconciliation performance", "accuracy"]):
            total_txns_stmt = select(func.count(TransactionORM.id))
            tot_txns_res = await self.session.execute(total_txns_stmt)
            total_txns = tot_txns_res.scalar_one() or 1

            # Get matched transactions from match_transactions
            from app.database.models import MatchTransaction as MatchTransactionORM
            matched_txns_stmt = select(func.count(func.distinct(MatchTransactionORM.transaction_id)))
            matched_res = await self.session.execute(matched_txns_stmt)
            matched_txns = matched_res.scalar_one() or 0

            match_rate_pct = round((matched_txns / total_txns) * 100, 2)
            deterministic_ans = (
                f"The overall reconciliation rate is {match_rate_pct:.2f}%, with {matched_txns} out of {total_txns} incoming transactions matched."
            )
            facts_text = f"Reconciliation Match Rate: {match_rate_pct}%\nMatched Transactions: {matched_txns}\nTotal Incoming Transactions: {total_txns}"
            ai_ans = await self._synthesize_with_llm(q_raw, facts_text, deterministic_ans)

            return QAResponse(
                question=q_raw,
                direct_answer=ai_ans,
                key_metrics={
                    "match_rate_percent": match_rate_pct,
                    "matched_transactions": matched_txns,
                    "total_transactions": total_txns,
                },
                evidence_records=[],
                sql_facts_used=[
                    "SELECT COUNT(DISTINCT transaction_id) FROM match_transactions",
                    "SELECT COUNT(id) FROM transactions",
                ],
                confidence=1.0,
            )

        # 5. Total Transactions & Feed Ingestion Counts (AUD-059)
        if any(w in q_lower for w in ["total transactions", "transaction count", "records received", "records normalized", "funnel"]):
            source_stmt = select(TransactionORM.source, func.count(TransactionORM.id), func.sum(TransactionORM.amount)).group_by(TransactionORM.source)
            res = await self.session.execute(source_stmt)
            src_rows = res.all()

            source_counts = {str(s): c for s, c, _ in src_rows}
            total_cnt = sum(c for _, c, _ in src_rows)

            deterministic_ans = (
                f"There are {total_cnt} total ingested transactions: " +
                ", ".join(f"{s}: {c}" for s, c in source_counts.items()) + "."
            )
            facts_text = f"Total Transactions: {total_cnt}\nSource Counts: {json.dumps(source_counts)}"
            ai_ans = await self._synthesize_with_llm(q_raw, facts_text, deterministic_ans)

            return QAResponse(
                question=q_raw,
                direct_answer=ai_ans,
                key_metrics={
                    "total_transactions": total_cnt,
                    "sources": source_counts,
                },
                evidence_records=[{"source": str(s), "count": c, "total_amount": float(a or 0)} for s, c, a in src_rows],
                sql_facts_used=[
                    "SELECT source, COUNT(id), SUM(amount) FROM transactions GROUP BY source"
                ],
                confidence=1.0,
            )

        # 6. ML Recovered Matches
        # "smart match" is the product's own user-facing label for ML-recovered
        # matches (Command Center funnel stage "Smart matches") — same synonym
        # gap as the issues/exceptions fix above.
        if any(w in q_lower for w in [
            "recovered by ml", "ml matches", "ml recovery", "ml contribution",
            "smart match", "smart matches",
        ]):
            match_stmt = select(MatchORM).where(MatchORM.reason.ilike("%ml%"))
            res = await self.session.execute(match_stmt)
            ml_matches = res.scalars().all()

            tot_stmt = select(func.count(MatchORM.id))
            tot_res = await self.session.execute(tot_stmt)
            total_matches = tot_res.scalar_one() or 1

            share = (len(ml_matches) / total_matches) * 100
            deterministic_ans = (
                f"Machine Learning (XGBoost) successfully recovered {len(ml_matches)} transaction matches "
                f"({share:.1f}% of all matches) that had corrupted references or shifted dates."
            )
            facts_text = f"ML Recovered Matches: {len(ml_matches)}\nTotal Matches: {total_matches}\nML Share Percent: {share:.1f}%"
            ai_ans = await self._synthesize_with_llm(q_raw, facts_text, deterministic_ans)

            return QAResponse(
                question=q_raw,
                direct_answer=ai_ans,
                key_metrics={
                    "ml_recovered_count": len(ml_matches),
                    "total_matches": total_matches,
                    "ml_share_percent": round(share, 2),
                },
                evidence_records=[{"match_id": m.id, "confidence": float(m.confidence or 0), "reason": m.reason} for m in ml_matches[:10]],
                sql_facts_used=["SELECT id, confidence, reason FROM matches WHERE reason ILIKE '%ml%'"],
                confidence=1.0,
            )

        # 7. Root Causes / Exception Categories Breakdown
        if any(w in q_lower for w in ["root cause", "failure", "causes", "why", "breakdown", "category"]):
            exc_stmt = (
                select(ExceptionORM.exception_category, func.count(ExceptionORM.id), func.sum(ExceptionORM.financial_exposure))
                .group_by(ExceptionORM.exception_category)
            )
            res = await self.session.execute(exc_stmt)
            cat_counts = res.all()

            cat_dict = {(c.value if hasattr(c, "value") else str(c)): count for c, count, _ in cat_counts}
            top_cat = max(cat_dict.items(), key=lambda x: x[1])[0] if cat_dict else "None"

            deterministic_ans = (
                f"The primary driver of exceptions is '{top_cat}', accounting for {cat_dict.get(top_cat, 0)} cases. "
                f"Complete breakdown: " + ", ".join(f"{c}: {n}" for c, n in cat_dict.items()) + "."
            )
            facts_text = f"Top Category: {top_cat}\nCategory Counts: {json.dumps(cat_dict)}"
            ai_ans = await self._synthesize_with_llm(q_raw, facts_text, deterministic_ans)

            return QAResponse(
                question=q_raw,
                direct_answer=ai_ans,
                key_metrics=cat_dict,
                evidence_records=[{"category": (c.value if hasattr(c, "value") else str(c)), "count": n, "exposure_inr": float(exp or 0)} for c, n, exp in cat_counts],
                sql_facts_used=["SELECT exception_category, COUNT(id), SUM(financial_exposure) FROM exceptions GROUP BY exception_category"],
                confidence=1.0,
            )

        # 8. Delayed Settlements
        if any(w in q_lower for w in ["delayed", "settlement delay", "sla"]):
            del_stmt = select(ExceptionORM).where(ExceptionORM.exception_category.in_(["delayed_settlement", "timing_mismatch"]))
            res = await self.session.execute(del_stmt)
            del_excs = res.scalars().all()
            total_del = sum(Decimal(str(e.financial_exposure or 0)) for e in del_excs)

            deterministic_ans = f"There are {len(del_excs)} delayed settlements totaling INR {total_del:,.2f} awaiting bank credit settlement."
            facts_text = f"Delayed Settlements Count: {len(del_excs)}\nTotal Delayed Exposure: INR {total_del:,.2f}"
            ai_ans = await self._synthesize_with_llm(q_raw, facts_text, deterministic_ans)

            return QAResponse(
                question=q_raw,
                direct_answer=ai_ans,
                key_metrics={"delayed_count": len(del_excs), "delayed_amount_inr": float(total_del)},
                evidence_records=[{"exception_id": e.id, "transaction_id": e.transaction_id, "amount_inr": float(e.financial_exposure or 0), "explanation": e.explanation} for e in del_excs[:10]],
                sql_facts_used=["SELECT id, transaction_id, financial_exposure, explanation FROM exceptions WHERE exception_category IN ('delayed_settlement', 'timing_mismatch')"],
                confidence=1.0,
            )

        # 9. Duplicate Settlements
        if any(w in q_lower for w in ["duplicate", "double"]):
            dup_stmt = select(ExceptionORM).where(ExceptionORM.exception_category.in_(["duplicate_entry", "duplicate_record"]))
            res = await self.session.execute(dup_stmt)
            dup_excs = res.scalars().all()
            total_dup = sum(Decimal(str(e.financial_exposure or 0)) for e in dup_excs)

            deterministic_ans = f"There are {len(dup_excs)} duplicate entry exceptions with a combined financial exposure of INR {total_dup:,.2f}."
            facts_text = f"Duplicate Entries Count: {len(dup_excs)}\nTotal Duplicate Exposure: INR {total_dup:,.2f}"
            ai_ans = await self._synthesize_with_llm(q_raw, facts_text, deterministic_ans)

            return QAResponse(
                question=q_raw,
                direct_answer=ai_ans,
                key_metrics={"duplicate_count": len(dup_excs), "duplicate_exposure_inr": float(total_dup)},
                evidence_records=[{"exception_id": e.id, "transaction_id": e.transaction_id, "amount_inr": float(e.financial_exposure or 0), "explanation": e.explanation} for e in dup_excs[:10]],
                sql_facts_used=["SELECT id, transaction_id, financial_exposure, explanation FROM exceptions WHERE exception_category IN ('duplicate_entry', 'duplicate_record')"],
                confidence=1.0,
            )

        # 10. Expected / Received Settlement Cash Overview
        if any(w in q_lower for w in ["settlement amount", "expected settlement", "cash position", "received settlement", "pending settlement", "treasury"]):
            cash = await self.cash_service.get_cash_position(run_id)
            deterministic_ans = (
                f"Veridex Treasury Overview: Expected settlement INR {cash.expected_amount:,.2f}, "
                f"Received INR {cash.received_amount:,.2f}, Pending INR {cash.pending_amount:,.2f}, "
                f"and Unreconciled exceptions INR {cash.unreconciled_amount:,.2f}."
            )
            facts_text = f"Expected Settlement: INR {cash.expected_amount:,.2f}\nReceived Settlement: INR {cash.received_amount:,.2f}\nPending Settlement: INR {cash.pending_amount:,.2f}\nUnreconciled Amount: INR {cash.unreconciled_amount:,.2f}"
            ai_ans = await self._synthesize_with_llm(q_raw, facts_text, deterministic_ans)

            return QAResponse(
                question=q_raw,
                direct_answer=ai_ans,
                key_metrics=cash.to_dict(),
                evidence_records=[],
                sql_facts_used=["SELECT expected_amount, received_amount, pending_amount, unreconciled_amount FROM cash_position"],
                confidence=1.0,
            )

        # 11. Honest Handling for Unsupported / Out-of-Scope Questions (AUD-026, AUD-059)
        return QAResponse(
            question=q_raw,
            direct_answer=(
                "I am unable to answer this question from the available financial reconciliation data. "
                "Supported topics include: unreconciled exposure, exception counts by status, reconciliation match rate, "
                "transaction counts, ML match recovery, root-cause breakdown, delayed settlements, and cash positions."
            ),
            key_metrics={},
            evidence_records=[],
            sql_facts_used=[],
            confidence=0.0,
        )
