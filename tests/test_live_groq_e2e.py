"""Live End-to-End Verification Test with REAL Groq API Key and PostgreSQL Database.

This test connects to the real Groq API using the GROQ_API_KEY from .env,
runs an ambiguous/high-value reconciliation exception through the full LangGraph
investigation workflow, verifies LLM reasoning, validates output against Pydantic schemas,
and checks PostgreSQL persistence and audit trail.
"""

import asyncio
import os
import sys
import time
import uuid

sys.path.insert(0, r"d:\sentinel")
from datetime import datetime, timezone
from decimal import Decimal
from dotenv import load_dotenv

load_dotenv(r"d:\sentinel\.env")

from app.database.session import async_session_maker
from app.database.repositories import (
    AuditRepository,
    ExceptionRepository,
    InvestigationRepository,
    ReconciliationRepository,
    TransactionRepository,
)
from app.graph.investigation_graph import InvestigationGraphRunner
from app.investigation.llm_client import GroqLLMClient
from app.investigation.service import InvestigationService
from app.models.decision_result import DecisionAction, DecisionResult
from app.models.exception_record import ExceptionCategory, ExceptionRecord
from app.models.investigation_result import InvestigationConclusion, InvestigationMethod
from app.models.reconciliation_run import ReconciliationRun, RunStatus
from app.models.transaction import Transaction, TransactionSource, TransactionStatus


async def run_live_groq_investigation():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY not found in environment/.env!")

    print(f"1. Initializing GroqLLMClient with real API key (starts with {api_key[:8]}...)...")
    real_llm = GroqLLMClient(api_key=api_key)
    graph_runner = InvestigationGraphRunner(llm_client=real_llm)

    async with async_session_maker() as session:
        txn_repo = TransactionRepository(session)
        rec_repo = ReconciliationRepository(session)
        exc_repo = ExceptionRepository(session)
        inv_repo = InvestigationRepository(session)
        audit_repo = AuditRepository(session)

        service = InvestigationService(
            session=session,
            investigation_repo=inv_repo,
            audit_repo=audit_repo,
            graph_runner=graph_runner,
        )

        timestamp_suffix = int(time.time())
        run_domain = ReconciliationRun(
            run_id=f"live_groq_run_{timestamp_suffix}",
            status=RunStatus.RUNNING,
            started_at=datetime.now(timezone.utc),
            gateway_count=1,
            ledger_count=1,
            bank_count=1,
            match_count=0,
            exception_count=1,
        )
        run_orm_id = await rec_repo.create_run(run_domain)
        print(f"2. Created ReconciliationRun in PostgreSQL: ORM ID = {run_orm_id}")

        # High value transaction with fee discrepancy requiring LLM escalation
        gw_txn = Transaction(
            txn_id=f"GW_LIVE_{timestamp_suffix}",
            source=TransactionSource.GATEWAY,
            reference_number=f"UTR_LIVE_{timestamp_suffix}",
            amount=Decimal("75000.00"),
            currency="INR",
            timestamp=datetime.now(timezone.utc),
            narration="High-value merchant settlement batch",
            fee=Decimal("1500.00"),
            tax=Decimal("270.00"),
            status=TransactionStatus.COMPLETED,
            order_id=f"ORD_LIVE_{timestamp_suffix}",
            metadata={"merchant_id": "M_9988", "gateway_provider": "Razorpay"},
        )
        ld_txn = Transaction(
            txn_id=f"LD_LIVE_{timestamp_suffix}",
            source=TransactionSource.LEDGER,
            reference_number=f"UTR_LIVE_{timestamp_suffix}",
            amount=Decimal("75000.00"),
            currency="INR",
            timestamp=datetime.now(timezone.utc),
            narration="Expected gross order collection",
            fee=Decimal("0.00"),
            tax=None,
            status=TransactionStatus.COMPLETED,
            order_id=f"ORD_LIVE_{timestamp_suffix}",
            metadata={"merchant_id": "M_9988"},
        )

        gw_orm_id = await txn_repo.create(gw_txn)
        ld_orm_id = await txn_repo.create(ld_txn)
        print(f"3. Persisted Transactions in DB: GW = {gw_orm_id}, LD = {ld_orm_id}")

        exc_record = ExceptionRecord(
            transaction_id=gw_orm_id,
            category=ExceptionCategory.FEE_MISMATCH,
            confidence=Decimal("0.85"),
            financial_exposure=Decimal("1770.00"),
            expected_cost=Decimal("250.00"),
            explanation="Gateway deducted INR 1,770 fee/tax not recognized on internal ledger for high-value order",
            evidence={
                "gateway_fee": "1500.00",
                "gateway_tax": "270.00",
                "ledger_fee": "0.00",
                "order_value": "75000.00"
            },
            recommended_action=None,
        )
        exc_orm_id = await exc_repo.create(exc_record, run_orm_id, gw_orm_id)
        print(f"4. Created Exception record in DB: Exception ID = {exc_orm_id}")

        decision = DecisionResult(
            transaction_ids=[gw_txn.txn_id, ld_txn.txn_id],
            action=DecisionAction.MANUAL_REVIEW,
            confidence=Decimal("0.75"),
            evidence={"amount_match": True, "fee_discrepancy": "1770.00"},
            reason="High-value settlement with unrecorded gateway fee deduction",
        )

        print("\n5. Launching LangGraph Investigation with REAL GROQ API...")
        inv_id = f"inv_live_{timestamp_suffix}"
        start_time = time.time()
        conclusion = await service.investigate(
            exception_id=exc_orm_id,
            run_id=run_orm_id,
            transactions=[gw_txn, ld_txn],
            decision=decision,
            investigation_id=inv_id,
        )
        elapsed = time.time() - start_time

        print(f"   -> Investigation completed in {elapsed:.2f} seconds!")
        print("\n=== REAL GROQ LLM INVESTIGATION CONCLUSION ===")
        print(f"Investigation ID:       {conclusion.investigation_id}")
        print(f"Exception ID:           {conclusion.exception_id}")
        print(f"Method Used:            {conclusion.method.value}")
        print(f"LLM Invoked:            {conclusion.llm_invoked}")
        print(f"Root Cause:             {conclusion.root_cause}")
        print(f"Classification:         {conclusion.classification.value}")
        print(f"Confidence:             {conclusion.confidence}")
        print(f"Financial Exposure:     INR {conclusion.financial_exposure}")
        print(f"Recommended Action:     {conclusion.recommended_action}")
        print(f"Requires Human Review:  {conclusion.requires_human_review}")
        print(f"Reasoning / Summary:    {conclusion.evidence.get('explanation') or conclusion.root_cause}")
        print("===============================================")

        # Assertions to verify correctness
        assert conclusion.investigation_id == inv_id
        assert conclusion.exception_id == exc_orm_id
        assert conclusion.llm_invoked is True
        assert conclusion.method == InvestigationMethod.LLM_ASSISTED
        assert isinstance(conclusion.classification, ExceptionCategory)
        assert conclusion.confidence > 0

        # Commit session to persist in PostgreSQL
        await session.commit()

        # Verification of DB persistence
        persisted_inv = await inv_repo.get_by_investigation_id(inv_id)
        assert persisted_inv is not None
        print("\n6. Verified Investigation conclusion persisted in PostgreSQL table 'investigations'.")

        persisted_audits = await audit_repo.get_by_run_id(run_orm_id)
        assert len(persisted_audits) >= 1
        print(f"7. Verified {len(persisted_audits)} audit event(s) logged in PostgreSQL table 'audit_events'.")

        print("\n>>> LIVE GROQ API + POSTGRESQL END-TO-END TEST PASSED! <<<\n")


if __name__ == "__main__":
    asyncio.run(run_live_groq_investigation())
