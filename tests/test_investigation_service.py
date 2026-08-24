import os
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from dotenv import load_dotenv
import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

load_dotenv()

from app.database.models import (
    Exception as ExceptionORM,
    ExceptionCategory as ExceptionCategoryORM,
    ReconciliationRun as ReconciliationRunORM,
    ReconciliationRunStatus,
)
from app.database.repositories.audit_repository import AuditRepository
from app.database.repositories.investigation_repository import InvestigationRepository
from app.database.session import create_app_engine
from app.graph.investigation_graph import InvestigationGraphRunner
from app.graph.state import InvestigationState
from app.investigation.llm_client import FakeLLMClient
from app.investigation.service import InvestigationService
from app.models.audit_event import AuditEvent
from app.models.decision_result import DecisionAction, DecisionResult
from app.models.exception_record import ExceptionCategory
from app.models.investigation_result import (
    InvestigationConclusion,
    InvestigationMethod,
    InvestigationStatus,
)
from app.models.transaction import Transaction, TransactionSource, TransactionStatus


# -------------------------------------------------------------------------
# Fixtures & Helpers
# -------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db_session():
    database_url = os.getenv("TEST_DATABASE_URL", "postgresql://sentinel:test123@localhost:5432/sentinel_test")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL not set")

    engine = create_app_engine(database_url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.execute(text(
            "TRUNCATE TABLE investigations, audit_events, exception_transactions, match_transactions, "
            "decisions, exceptions, matches, reconciliation_items, reconciliation_runs, transactions CASCADE;"
        ))

    async with session_factory() as session:
        yield session

    await engine.dispose()


def make_txn(
    txn_id: str,
    source: TransactionSource,
    amount: Decimal,
    order_id: str = "ORD_100",
    ref: str = "REF_100",
) -> Transaction:
    return Transaction(
        txn_id=txn_id,
        source=source,
        amount=amount,
        currency="INR",
        timestamp=datetime.utcnow(),
        order_id=order_id,
        reference_number=ref,
        status=TransactionStatus.COMPLETED,
    )


# -------------------------------------------------------------------------
# Unit Tests (Mocked Dependencies)
# -------------------------------------------------------------------------

class TestInvestigationServiceUnit:

    @pytest.mark.asyncio
    async def test_successful_investigation_flow_with_mocks(self):
        # 1. Arrange mock dependencies
        session = AsyncMock(spec=AsyncSession)
        investigation_repo = AsyncMock(spec=InvestigationRepository)
        audit_repo = AsyncMock(spec=AuditRepository)
        graph_runner = AsyncMock(spec=InvestigationGraphRunner)

        mock_conclusion = InvestigationConclusion(
            investigation_id="INV_UNIT_1",
            exception_id="EXC_1",
            run_id="RUN_1",
            method=InvestigationMethod.DETERMINISTIC,
            root_cause="Duplicate records detected",
            classification=ExceptionCategory.DUPLICATE_ENTRY,
            confidence=Decimal("0.95"),
            financial_exposure=Decimal("5000.00"),
            expected_cost=Decimal("4750.00"),
            recommended_action="flag_duplicate",
            requires_human_review=False,
            evidence={"duplicate_count": 2},
        )
        graph_runner.run.return_value = mock_conclusion
        investigation_repo.create.return_value = "db_id_123"
        audit_repo.create.return_value = "audit_id_123"

        service = InvestigationService(
            session=session,
            investigation_repo=investigation_repo,
            audit_repo=audit_repo,
            graph_runner=graph_runner,
        )

        t1 = make_txn("T1", TransactionSource.GATEWAY, Decimal("5000.00"))
        t2 = make_txn("T2", TransactionSource.GATEWAY, Decimal("5000.00"))

        # 2. Act
        result = await service.investigate(
            exception_id="EXC_1",
            run_id="RUN_1",
            transactions=[t1, t2],
            investigation_id="INV_UNIT_1",
        )

        # 3. Assert
        assert result == mock_conclusion
        graph_runner.run.assert_awaited_once()
        investigation_repo.create.assert_awaited_once_with(mock_conclusion)
        audit_repo.create.assert_awaited_once()

        # Verify audit event payload
        created_audit = audit_repo.create.call_args[0][0]
        assert isinstance(created_audit, AuditEvent)
        assert created_audit.run_id == "RUN_1"
        assert created_audit.stage == "investigation"
        assert created_audit.event == "investigation_completed"
        assert created_audit.evidence["investigation_id"] == "INV_UNIT_1"

    @pytest.mark.asyncio
    async def test_graph_failure_propagates_and_does_not_persist(self):
        session = AsyncMock(spec=AsyncSession)
        investigation_repo = AsyncMock(spec=InvestigationRepository)
        audit_repo = AsyncMock(spec=AuditRepository)
        graph_runner = AsyncMock(spec=InvestigationGraphRunner)

        graph_runner.run.side_effect = RuntimeError("Graph execution failed unexpectedly")

        service = InvestigationService(
            session=session,
            investigation_repo=investigation_repo,
            audit_repo=audit_repo,
            graph_runner=graph_runner,
        )

        t1 = make_txn("T1", TransactionSource.GATEWAY, Decimal("1000.00"))

        with pytest.raises(RuntimeError, match="Graph execution failed"):
            await service.investigate("EXC_FAIL", "RUN_1", [t1])

        # Ensure repository was NOT called after graph failure
        investigation_repo.create.assert_not_awaited()
        audit_repo.create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_persistence_failure_propagates(self):
        session = AsyncMock(spec=AsyncSession)
        investigation_repo = AsyncMock(spec=InvestigationRepository)
        audit_repo = AsyncMock(spec=AuditRepository)
        graph_runner = AsyncMock(spec=InvestigationGraphRunner)

        mock_conclusion = InvestigationConclusion(
            investigation_id="INV_ERR_1",
            exception_id="EXC_1",
            run_id="RUN_1",
            method=InvestigationMethod.DETERMINISTIC,
            root_cause="Rounding discrepancy",
            classification=ExceptionCategory.CURRENCY_ROUNDING,
            confidence=Decimal("0.98"),
            financial_exposure=Decimal("100.00"),
            expected_cost=Decimal("5.00"),
            recommended_action="write_off",
            requires_human_review=False,
        )
        graph_runner.run.return_value = mock_conclusion
        investigation_repo.create.side_effect = IOError("Database connection lost during write")

        service = InvestigationService(
            session=session,
            investigation_repo=investigation_repo,
            audit_repo=audit_repo,
            graph_runner=graph_runner,
        )

        t1 = make_txn("T1", TransactionSource.GATEWAY, Decimal("100.00"))

        with pytest.raises(IOError, match="Database connection lost"):
            await service.investigate("EXC_1", "RUN_1", [t1], investigation_id="INV_ERR_1")

        # Audit event should not be recorded if persistence failed
        audit_repo.create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_service_preserves_custom_investigation_id(self):
        session = AsyncMock(spec=AsyncSession)
        investigation_repo = AsyncMock(spec=InvestigationRepository)
        audit_repo = AsyncMock(spec=AuditRepository)
        graph_runner = AsyncMock(spec=InvestigationGraphRunner)

        custom_id = "CUSTOM_INV_999"

        async def fake_run(state: InvestigationState):
            return InvestigationConclusion(
                investigation_id=state.investigation_id,
                exception_id=state.exception_id,
                run_id=state.run_id,
                method=InvestigationMethod.DETERMINISTIC,
                root_cause="Fee mismatch",
                classification=ExceptionCategory.FEE_MISMATCH,
                confidence=Decimal("0.90"),
                financial_exposure=Decimal("1000.00"),
                expected_cost=Decimal("400.00"),
                recommended_action="request_credit_note",
                requires_human_review=False,
            )

        graph_runner.run.side_effect = fake_run

        service = InvestigationService(
            session=session,
            investigation_repo=investigation_repo,
            audit_repo=audit_repo,
            graph_runner=graph_runner,
        )

        t1 = make_txn("T1", TransactionSource.GATEWAY, Decimal("1000.00"))
        conclusion = await service.investigate(
            exception_id="EXC_CUSTOM",
            run_id="RUN_1",
            transactions=[t1],
            investigation_id=custom_id,
        )

        assert conclusion.investigation_id == custom_id
        # Verify passed to graph state
        passed_state = graph_runner.run.call_args[0][0]
        assert passed_state.investigation_id == custom_id

    @pytest.mark.asyncio
    async def test_service_does_not_contain_business_rules(self):
        """Verify service purely orchestrates by checking that graph output is forwarded unchanged."""
        session = AsyncMock(spec=AsyncSession)
        investigation_repo = AsyncMock(spec=InvestigationRepository)
        audit_repo = AsyncMock(spec=AuditRepository)
        graph_runner = AsyncMock(spec=InvestigationGraphRunner)

        arbitrary_conclusion = InvestigationConclusion(
            investigation_id="INV_ARB",
            exception_id="EXC_ARB",
            run_id="RUN_ARB",
            method=InvestigationMethod.LLM_ASSISTED,
            root_cause="Specialized root cause from graph",
            classification=ExceptionCategory.WRONG_REFERENCE,
            confidence=Decimal("0.8888"),
            financial_exposure=Decimal("1234.56"),
            expected_cost=Decimal("432.10"),
            recommended_action="investigate_further",
            requires_human_review=True,
            evidence={"arbitrary_key": "arbitrary_value"},
        )
        graph_runner.run.return_value = arbitrary_conclusion

        service = InvestigationService(
            session=session,
            investigation_repo=investigation_repo,
            audit_repo=audit_repo,
            graph_runner=graph_runner,
        )

        t1 = make_txn("T1", TransactionSource.GATEWAY, Decimal("1234.56"))
        result = await service.investigate("EXC_ARB", "RUN_ARB", [t1])

        # Exact passthrough
        assert result.root_cause == "Specialized root cause from graph"
        assert result.confidence == Decimal("0.8888")
        assert result.evidence == {"arbitrary_key": "arbitrary_value"}


# -------------------------------------------------------------------------
# Integration Tests (Real Database + Real Graph with Fake LLM)
# -------------------------------------------------------------------------

class TestInvestigationServiceIntegration:

    @pytest.mark.asyncio
    async def test_end_to_end_service_with_database(self, db_session):
        # 1. Create prerequisite Run and Exception in PostgreSQL
        run_orm = ReconciliationRunORM(
            id="RUN_SVC_1",
            run_id="RUN_SVC_1",
            status=ReconciliationRunStatus.COMPLETED,
            gateway_count=2,
            ledger_count=1,
            bank_count=1,
            match_count=0,
            exception_count=1,
            created_at=datetime.utcnow(),
        )
        db_session.add(run_orm)
        await db_session.flush()

        exc_orm = ExceptionORM(
            id="EXC_SVC_1",
            run_id="RUN_SVC_1",
            exception_category=ExceptionCategoryORM.DUPLICATE_RECORD,
            status="open",
            confidence=Decimal("0.95"),
            financial_exposure=Decimal("10000.00"),
            expected_cost=Decimal("9500.00"),
            explanation="Duplicate entry",
            evidence={},
            resolved=False,
            created_at=datetime.utcnow(),
        )
        db_session.add(exc_orm)
        await db_session.flush()

        # 2. Instantiate real repositories and service with FakeLLM runner
        investigation_repo = InvestigationRepository(db_session)
        audit_repo = AuditRepository(db_session)
        graph_runner = InvestigationGraphRunner(llm_client=FakeLLMClient())

        service = InvestigationService(
            session=db_session,
            investigation_repo=investigation_repo,
            audit_repo=audit_repo,
            graph_runner=graph_runner,
        )

        t1 = make_txn("T1", TransactionSource.GATEWAY, Decimal("10000.00"), order_id="ORD_DUP", ref="REF_DUP")
        t2 = make_txn("T2", TransactionSource.GATEWAY, Decimal("10000.00"), order_id="ORD_DUP", ref="REF_DUP")

        # 3. Act: Investigate
        conclusion = await service.investigate(
            exception_id="EXC_SVC_1",
            run_id="RUN_SVC_1",
            transactions=[t1, t2],
            investigation_id="INV_SVC_1",
        )

        # 4. Assert conclusion returned
        assert conclusion.investigation_id == "INV_SVC_1"
        assert conclusion.classification == ExceptionCategory.DUPLICATE_ENTRY
        assert conclusion.method == InvestigationMethod.DETERMINISTIC

        # 5. Verify database persistence
        persisted = await service.get_investigation("INV_SVC_1")
        assert persisted is not None
        assert persisted.investigation_id == "INV_SVC_1"
        assert persisted.root_cause == conclusion.root_cause

        # 6. Verify audit event persistence
        audit_events = await audit_repo.get_by_run_id("RUN_SVC_1")
        assert len(audit_events) >= 1
        inv_audits = [a for a in audit_events if a.stage == "investigation"]
        assert len(inv_audits) == 1
        assert inv_audits[0].event == "investigation_completed"
        assert inv_audits[0].evidence["investigation_id"] == "INV_SVC_1"
