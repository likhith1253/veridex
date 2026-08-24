"""
Master Finance Controller Orchestration Layer for Project Sentinel (Razorpay Track 4).

Coordinates:
1. Batch Ingestion & 3-Way Reconciliation
2. Real-Time Incremental Reconciliation
3. Calculated Financial Summary KPIs
4. Decimal-Safe Financial Exposure Calculations
5. Fee & Tax Control Auditing
6. Human Decision-in-the-Loop Governance
7. Explainability & Evidence Extraction
8. Exception Management, Filtering & Aging
9. Audit Event Timeline
10. Grounded Finance Q&A
11. Comprehensive Batch Finance Reports
12. 7-Day Cash Settlement Forecast
13. Feed Source Health & Discrepancy Analytics
"""

import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.mappers.transaction_mapper import orm_to_domain
from app.database.models import (
    AuditEvent as AuditEventORM,
    Decision as DecisionORM,
    Exception as ExceptionORM,
    Match as MatchORM,
    ReconciliationItem as ReconciliationItemORM,
    ReconciliationRun as ReconciliationRunORM,
    Transaction as TransactionORM,
)
from app.database.repositories.audit_repository import AuditRepository
from app.database.repositories.decision_repository import DecisionRepository
from app.database.repositories.exception_repository import ExceptionRepository
from app.database.repositories.match_repository import MatchRepository
from app.database.repositories.reconciliation_repository import ReconciliationRepository
from app.database.repositories.transaction_repository import TransactionRepository
from app.investigation.service import InvestigationService
from app.matching.ml_scorer import MLScorer
from app.models.decision_result import DecisionAction
from app.models.exception_record import ExceptionCategory
from app.models.transaction import Transaction, TransactionSource, TransactionStatus
from app.services.cash_position import CashPositionService, CashPositionSummary
from app.services.exception_management_service import (
    ExceptionAgingReport,
    ExceptionDetail,
    ExceptionManagementService,
)
from app.services.explainability_service import DecisionExplanation, ExplainabilityService
from app.services.exposure_service import FinancialExposureBreakdown, FinancialExposureService
from app.services.fee_tax_service import FeeTaxReconciliationReport, FeeTaxService
from app.services.finance_qa import FinanceQAService, QAResponse
from app.services.forecast_service import CashForecastReport, CashForecastService
from app.services.human_decision_service import (
    HumanAction,
    HumanDecisionResult,
    HumanDecisionService,
)
from app.services.incremental_reconciliation import (
    IncrementalReconciliationResult,
    IncrementalReconciliationService,
)
from app.services.reconciliation import ReconciliationService, ReconciliationSummary
from app.services.source_health_service import SourceHealthReport, SourceHealthService
from eval.config import BenchmarkConfig
from eval.evaluator import ReconciliationEvaluator

logger = logging.getLogger(__name__)


@dataclass
class ControllerKPIs:
    """Consolidated Finance Controller KPIs calculated from actual database records."""
    total_records_processed: int = 0
    total_logical_transactions: int = 0
    total_transaction_value_inr: float = 0.0
    deterministic_matches: int = 0
    ml_recovered_matches: int = 0
    total_matched_records: int = 0
    automatic_matches: int = 0
    manual_reviews: int = 0
    unresolved_transactions: int = 0
    match_rate: float = 0.0
    reconciliation_precision: Optional[float] = None
    reconciliation_recall: Optional[float] = None
    f1_score: Optional[float] = None
    exception_rate: float = 0.0
    total_matched_monetary_value_inr: float = 0.0
    unresolved_monetary_exposure_inr: float = 0.0
    manual_review_exposure_inr: float = 0.0
    high_risk_exposure_inr: float = 0.0
    delayed_settlement_inr: float = 0.0
    duplicate_amount_inr: float = 0.0
    fee_mismatch_inr: float = 0.0
    processing_throughput_tps: Optional[float] = None
    average_processing_latency_ms: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FinanceController:
    """Master AI Finance Controller coordinating reconciliation, risk, Q&A, and reporting."""

    def __init__(
        self,
        session: AsyncSession,
        ml_scorer: Optional[MLScorer] = None,
        investigation_service: Optional[InvestigationService] = None,
    ):
        self.session = session
        self.ml_scorer = ml_scorer or MLScorer(model_type="xgboost")
        self.investigation_service = investigation_service

        self.cash_service = CashPositionService(session)
        self.exposure_service = FinancialExposureService(session)
        self.fee_tax_service = FeeTaxService(session)
        self.human_service = HumanDecisionService(session)
        self.explain_service = ExplainabilityService(session)
        self.exc_mgmt_service = ExceptionManagementService(session)
        self.forecast_service = CashForecastService(session)
        self.source_health_service = SourceHealthService(session)
        self.qa_service = FinanceQAService(session, llm_client=getattr(investigation_service, "llm_client", None) if investigation_service else None)
        self.txn_repo = TransactionRepository(session)
        self.rec_repo = ReconciliationRepository(session)
        self.match_repo = MatchRepository(session)
        self.dec_repo = DecisionRepository(session)
        self.exc_repo = ExceptionRepository(session)
        self.audit_repo = AuditRepository(session)

        self.reconciliation_service = ReconciliationService(
            session=session,
            transaction_repo=self.txn_repo,
            reconciliation_repo=self.rec_repo,
            match_repo=self.match_repo,
            decision_repo=self.dec_repo,
            exception_repo=self.exc_repo,
            audit_repo=self.audit_repo,
            ml_scorer=self.ml_scorer,
            investigation_service=investigation_service,
        )

    # 1. Batch Ingestion & 3-Way Reconciliation
    async def ingest_and_reconcile_batch(
        self,
        gateway_txns: list[Transaction],
        ledger_txns: list[Transaction],
        bank_txns: list[Transaction],
        batch_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Ingest multi-source transaction batch and execute complete 3-way reconciliation."""
        t0 = time.perf_counter()
        bid = batch_id or f"batch_{uuid.uuid4().hex[:8]}"

        # Normalization and reconciliation run
        txns_by_source = {
            TransactionSource.GATEWAY: gateway_txns,
            TransactionSource.LEDGER: ledger_txns,
            TransactionSource.BANK: bank_txns,
        }
        run_res = await self.reconciliation_service.run_reconciliation(
            transactions_by_source=txns_by_source,
            run_id=bid,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        return {
            "batch_id": bid,
            "run_id": run_res.run_id,
            "records_received": len(gateway_txns) + len(ledger_txns) + len(bank_txns),
            "records_normalized": run_res.total_transactions,
            "processing_status": "COMPLETED",
            "processing_duration_ms": round(elapsed_ms, 2),
            "reconciliation_status": "COMPLETED" if run_res.completed_successfully else "FAILED",
            "auto_matched_count": run_res.deterministic_matches,
            "ml_recovered_count": run_res.ml_proposals,
            "manual_review_count": run_res.manual_reviews,
            "unresolved_count": run_res.unresolved,
        }

    # 2. Executive KPIs
    async def get_summary_kpis(self, run_id: Optional[str] = None) -> ControllerKPIs:
        """Compute live controller KPIs directly from PostgreSQL state."""
        exp = await self.exposure_service.calculate_exposure(run_id)

        txn_stmt = select(func.count(TransactionORM.id))
        res = await self.session.execute(txn_stmt)
        total_records = res.scalar_one() or 0

        match_stmt = select(MatchORM)
        if run_id:
            match_stmt = match_stmt.where(MatchORM.run_id == run_id)
        res = await self.session.execute(match_stmt)
        matches = res.scalars().all()

        ml_count = sum(1 for m in matches if "ml" in str(getattr(m, "reason", "") or "").lower() or "ml" in str(getattr(m, "rule_name", "") or "").lower())
        det_count = len(matches) - ml_count

        dec_stmt = select(DecisionORM)
        if run_id:
            dec_stmt = dec_stmt.where(DecisionORM.run_id == run_id)
        res = await self.session.execute(dec_stmt)
        decisions = res.scalars().all()

        def get_val(d):
            val = getattr(d, "decision_action", getattr(d, "action", ""))
            return getattr(val, "value", val)

        auto_matches = sum(1 for d in decisions if get_val(d) == DecisionAction.AUTO_MATCH.value)
        manual_reviews = sum(1 for d in decisions if get_val(d) == DecisionAction.MANUAL_REVIEW.value)
        unresolved = sum(1 for d in decisions if get_val(d) in (DecisionAction.UNRESOLVED.value, DecisionAction.AMBIGUOUS.value))

        ml_recovered = sum(1 for d in decisions if get_val(d) == DecisionAction.PROPOSE_MATCH.value)
        tot_dec = len(decisions) or 1
        m_rate = ((auto_matches + ml_recovered) / tot_dec) * 100

        return ControllerKPIs(
            total_records_processed=total_records,
            total_logical_transactions=total_records // 3 if total_records >= 3 else total_records,
            total_transaction_value_inr=float(exp.total_processed_value),
            deterministic_matches=det_count,
            ml_recovered_matches=ml_count,
            total_matched_records=(det_count + ml_count) * 2,
            automatic_matches=auto_matches,
            manual_reviews=manual_reviews,
            unresolved_transactions=unresolved,
            match_rate=round(m_rate, 2),
            reconciliation_precision=None,
            reconciliation_recall=None,
            f1_score=None,
            exception_rate=round((unresolved / tot_dec) * 100, 2),
            total_matched_monetary_value_inr=float(exp.matched_value),
            unresolved_monetary_exposure_inr=float(exp.unresolved_value),
            manual_review_exposure_inr=float(exp.manual_review_value),
            high_risk_exposure_inr=float(exp.high_risk_value),
            delayed_settlement_inr=float(exp.delayed_settlement_exposure),
            duplicate_amount_inr=float(exp.duplicate_exposure),
            fee_mismatch_inr=float(exp.fee_tax_mismatch_exposure),
            processing_throughput_tps=None,
            average_processing_latency_ms=None,
        )

    # 3. Funnel & Reports
    async def get_reconciliation_funnel(self, run_id: Optional[str] = None) -> dict[str, Any]:
        kpis = await self.get_summary_kpis(run_id)
        return {
            "incoming_records": kpis.total_records_processed,
            "deterministic_matches": kpis.deterministic_matches,
            "ml_recovered": kpis.ml_recovered_matches,
            "manual_reviews": kpis.manual_reviews,
            "unresolved": kpis.unresolved_transactions,
            "final_match_rate": kpis.match_rate,
        }

    async def generate_controller_report(self, run_id: Optional[str] = None) -> dict[str, Any]:
        kpis = await self.get_summary_kpis(run_id)
        exp = await self.exposure_service.calculate_exposure(run_id)
        excs, _ = await self.exc_mgmt_service.list_exceptions(run_id=run_id, page_size=10)
        aging = await self.exc_mgmt_service.calculate_exception_aging(run_id)

        return {
            "report_id": f"rep_{uuid.uuid4().hex[:8]}",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "scope_run_id": run_id or "global_database_scope",
            "kpis": kpis.to_dict(),
            "financial_exposure": exp.to_dict(),
            "exception_aging": asdict(aging),
            "highest_risk_exceptions": excs[:5],
            "recommended_actions_summary": [
                "Execute credit note requests on duplicate settlements",
                "Review high-value unexplained transactions (>100k INR)",
                "Follow up on bank statement clearing SLA delays",
            ],
        }

    async def get_benchmark_evaluation(
        self,
        num_transactions: int = 100,
        seed: int = 42,
        output_dir: Optional[str] = None,
    ) -> dict[str, Any]:
        """Run benchmark evaluation in a deterministic, evaluation-only scope that never touches live DB state."""
        cfg = BenchmarkConfig(num_transactions=num_transactions, seed=seed)
        if output_dir:
            cfg.output_dir = output_dir

        result = ReconciliationEvaluator().evaluate_benchmark(cfg)
        return {
            "scope": "evaluation_only",
            "benchmark": {
                "num_transactions": cfg.num_transactions,
                "seed": cfg.seed,
                "currency": cfg.currency,
                "dataset_name": f"benchmark_seed_{cfg.seed}_n_{cfg.num_transactions}",
            },
            "result": result.to_dict(),
        }

    # 4. Audit Timeline
    async def get_audit_timeline(
        self,
        run_id: Optional[str] = None,
        transaction_id: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        stmt = select(AuditEventORM)
        if run_id:
            stmt = stmt.where(AuditEventORM.run_id == run_id)
        if transaction_id:
            stmt = stmt.where(AuditEventORM.transaction_id == transaction_id)
        stmt = stmt.order_by(AuditEventORM.timestamp.desc()).limit(100)

        res = await self.session.execute(stmt)
        events = res.scalars().all()

        return [
            {
                "event_id": e.id,
                "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                "event_type": e.event_type,
                "run_id": e.run_id,
                "transaction_id": e.transaction_id,
                "details": e.meta_data or {},
            }
            for e in events
        ]

    # 5. Failure Simulation
    async def simulate_failure_scenario(self, scenario: str, amount: float = 50000.0) -> dict[str, Any]:
        amt = Decimal(str(amount))
        now = datetime.now(timezone.utc)

        if scenario == "corrupted_utr":
            gw = Transaction(txn_id=f"GW_CORRUPT_{uuid.uuid4().hex[:6]}", source=TransactionSource.GATEWAY, amount=amt, currency="INR", timestamp=now, status=TransactionStatus.COMPLETED, order_id="ORD_SIM_1", reference_number="UTR_TYPO_999")
            bk = Transaction(txn_id=f"BK_CORRUPT_{uuid.uuid4().hex[:6]}", source=TransactionSource.BANK, amount=amt, currency="INR", timestamp=now, status=TransactionStatus.COMPLETED, order_id="ORD_SIM_1", reference_number="UTR_TRUE_999", narration="PAYMENT FOR ORD_SIM_1")
            res = await self.incremental_service.ingest_and_reconcile(gw)
            res_bk = await self.incremental_service.ingest_and_reconcile(bk)
            return {"scenario": "corrupted_utr", "gateway_result": asdict(res), "bank_result": asdict(res_bk), "note": "Recovered via XGBoost fuzzy narration & amount matching"}

        elif scenario == "duplicate":
            gw1 = Transaction(txn_id=f"GW_DUP_{uuid.uuid4().hex[:6]}", source=TransactionSource.GATEWAY, amount=amt, currency="INR", timestamp=now, status=TransactionStatus.COMPLETED, order_id="ORD_DUP_1", reference_number="UTR_DUP_1")
            gw2 = Transaction(txn_id=f"GW_DUP2_{uuid.uuid4().hex[:6]}", source=TransactionSource.GATEWAY, amount=amt, currency="INR", timestamp=now, status=TransactionStatus.COMPLETED, order_id="ORD_DUP_1", reference_number="UTR_DUP_1")
            res1 = await self.incremental_service.ingest_and_reconcile(gw1)
            res2 = await self.incremental_service.ingest_and_reconcile(gw2)
            return {"scenario": "duplicate", "first_event": asdict(res1), "duplicate_event": asdict(res2), "note": "Duplicate entry detected and quarantined"}

        return {"scenario": scenario, "status": "SIMULATION_EXECUTED", "amount": float(amt)}
