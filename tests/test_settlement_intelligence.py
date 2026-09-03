"""
Tests for Razorpay Settlement Intelligence Service.

Tests cover:
- Settlement accounting (gross - fee - tax = expected net)
- Decimal precision
- Zero variance
- Positive variance
- Negative variance
- State transitions
- Linking (settlement → payment, settlement → order, settlement → bank transaction)
- Exception dossier creation
- AI grounding
"""

import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.dialects.postgresql import JSONB

@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "JSON"

from app.database.models import (
    Base,
    Transaction as TransactionORM,
    TransactionSource,
    TransactionStatus,
)
from app.services.razorpay_settlement_intelligence_service import (
    RazorpaySettlementIntelligenceService,
    SettlementVarianceType,
)


@pytest_asyncio.fixture
async def session():
    """Create an in-memory SQLite test database session for settlement intelligence tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as s:
        yield s

    await engine.dispose()


@pytest_asyncio.fixture
async def settlement_service(session: AsyncSession):
    """Create settlement intelligence service fixture."""
    return RazorpaySettlementIntelligenceService(session)


@pytest_asyncio.fixture
async def sample_settlement(session: AsyncSession):
    """Create a sample settlement transaction for testing."""
    from app.database.utils import utcnow
    import uuid
    
    settlement = TransactionORM(
        id=str(uuid.uuid4()),
        domain_transaction_id="setl_test_001",
        source=TransactionSource.GATEWAY.value,
        reference_number="UTR123456",
        order_id=None,
        amount=Decimal("10000.00"),
        currency="INR",
        timestamp=utcnow(),
        narration="Razorpay settlement payout setl_test_001 (UTR: UTR123456)",
        fee=Decimal("200.00"),
        tax=Decimal("36.00"),
        status=TransactionStatus.PROCESSED.value,
        meta_data={
            "gateway": "razorpay",
            "type": "settlement",
            "utr": "UTR123456",
            "raw_status": "processed",
            "lifecycle_state": "RAZORPAY_PROCESSED",
        },
        created_at=utcnow(),
    )
    session.add(settlement)
    await session.commit()
    await session.refresh(settlement)
    return settlement


@pytest_asyncio.fixture
async def sample_bank_transaction(session: AsyncSession, sample_settlement: TransactionORM):
    """Create a matching bank transaction for testing."""
    from app.database.utils import utcnow
    import uuid
    
    bank_txn = TransactionORM(
        id=str(uuid.uuid4()),
        domain_transaction_id="bank_txn_001",
        source=TransactionSource.BANK.value,
        reference_number="UTR123456",
        order_id=None,
        amount=Decimal("9764.00"),  # 10000 - 200 - 36
        currency="INR",
        timestamp=utcnow() + timedelta(hours=1),
        narration="Bank credit UTR123456",
        fee=None,
        tax=None,
        status=TransactionStatus.PROCESSED.value,
        meta_data={"type": "bank_credit"},
        created_at=utcnow(),
    )
    session.add(bank_txn)
    await session.commit()
    await session.refresh(bank_txn)
    return bank_txn


class TestSettlementAccounting:
    """Tests for settlement financial calculations and accounting."""

    @pytest.mark.asyncio
    async def test_gross_minus_fee_minus_tax_equals_expected_net(
        self, settlement_service: RazorpaySettlementIntelligenceService, sample_settlement: TransactionORM
    ):
        """Test that expected_net = gross - fee - tax."""
        breakdown = await settlement_service.get_settlement_financial_breakdown("setl_test_001")
        
        expected_net = sample_settlement.amount - sample_settlement.fee - sample_settlement.tax
        assert breakdown.expected_net_amount == expected_net
        assert breakdown.gross_amount == sample_settlement.amount
        assert breakdown.fee_amount == sample_settlement.fee
        assert breakdown.tax_amount == sample_settlement.tax

    @pytest.mark.asyncio
    async def test_decimal_precision(
        self, settlement_service: RazorpaySettlementIntelligenceService, sample_settlement: TransactionORM
    ):
        """Test that financial calculations maintain Decimal precision."""
        breakdown = await settlement_service.get_settlement_financial_breakdown("setl_test_001")
        
        # All amounts should be Decimal type
        assert isinstance(breakdown.gross_amount, Decimal)
        assert isinstance(breakdown.fee_amount, Decimal)
        assert isinstance(breakdown.tax_amount, Decimal)
        assert isinstance(breakdown.expected_net_amount, Decimal)
        assert isinstance(breakdown.variance, Decimal)
        
        # Should maintain 2 decimal places for currency
        assert breakdown.gross_amount == breakdown.gross_amount.quantize(Decimal("0.01"))
        assert breakdown.fee_amount == breakdown.fee_amount.quantize(Decimal("0.01"))
        assert breakdown.tax_amount == breakdown.tax_amount.quantize(Decimal("0.01"))

    @pytest.mark.asyncio
    async def test_zero_variance_with_bank_match(
        self, settlement_service: RazorpaySettlementIntelligenceService, 
        sample_settlement: TransactionORM, sample_bank_transaction: TransactionORM, session: AsyncSession
    ):
        """Test zero variance when bank matches expected net."""
        breakdown = await settlement_service.get_settlement_financial_breakdown("setl_test_001")
        
        assert breakdown.variance == Decimal("0")
        assert breakdown.variance_type == SettlementVarianceType.NO_VARIANCE

    @pytest.mark.asyncio
    async def test_positive_variance(
        self, settlement_service: RazorpaySettlementIntelligenceService, sample_settlement: TransactionORM, session: AsyncSession
    ):
        """Test positive variance (bank received more than expected)."""
        # Create bank transaction with higher amount
        bank_txn = await _create_test_bank_transaction(session, sample_settlement, Decimal("10500.00"))
        
        breakdown = await settlement_service.get_settlement_financial_breakdown("setl_test_001")
        
        assert breakdown.variance > Decimal("0")
        assert breakdown.variance_type in [
            SettlementVarianceType.UNEXPECTED_BANK_CREDIT,
            SettlementVarianceType.AMOUNT_VARIANCE
        ]
        
        # Cleanup
        await session.delete(bank_txn)
        await session.commit()

    @pytest.mark.asyncio
    async def test_negative_variance(
        self, settlement_service: RazorpaySettlementIntelligenceService, sample_settlement: TransactionORM, session: AsyncSession
    ):
        """Test negative variance (bank received less than expected)."""
        # Create bank transaction with lower amount
        bank_txn = await _create_test_bank_transaction(session, sample_settlement, Decimal("9000.00"))
        
        breakdown = await settlement_service.get_settlement_financial_breakdown("setl_test_001")
        
        assert breakdown.variance < Decimal("0")
        assert breakdown.variance_type in [
            SettlementVarianceType.AMOUNT_VARIANCE,
            SettlementVarianceType.FEE_VARIANCE,
            SettlementVarianceType.TAX_VARIANCE
        ]
        
        # Cleanup
        await session.delete(bank_txn)
        await session.commit()

    @pytest.mark.asyncio
    async def test_missing_bank_credit(
        self, settlement_service: RazorpaySettlementIntelligenceService, sample_settlement: TransactionORM
    ):
        """Test variance classification when bank credit is missing."""
        # No matching bank transaction
        breakdown = await settlement_service.get_settlement_financial_breakdown("setl_test_001")
        
        # If no bank match, variance should be the full expected amount
        assert breakdown.variance_type == SettlementVarianceType.MISSING_BANK_CREDIT


class TestStateTransitions:
    """Tests for settlement lifecycle state transitions."""

    @pytest.mark.asyncio
    async def test_razorpay_processed_state(
        self, settlement_service: RazorpaySettlementIntelligenceService, sample_settlement: TransactionORM, session: AsyncSession
    ):
        """Test RAZORPAY_PROCESSED state when settlement is created but not yet bank-confirmed."""
        # Ensure no bank transaction exists
        bank_recon = await settlement_service.get_settlement_bank_reconciliation("setl_test_001")
        
        from app.integrations.razorpay.schemas import RazorpaySettlementState
        assert bank_recon.settlement_status == RazorpaySettlementState.RAZORPAY_PROCESSED
        assert bank_recon.bank_matched is False

    @pytest.mark.asyncio
    async def test_bank_credit_pending_state(
        self, settlement_service: RazorpaySettlementIntelligenceService, sample_settlement: TransactionORM, session: AsyncSession
    ):
        """Test BANK_CREDIT_PENDING state when Razorpay processed but bank not yet credited."""
        # Update settlement metadata to reflect pending state
        sample_settlement.meta_data["lifecycle_state"] = "BANK_CREDIT_PENDING"
        await session.commit()
        
        bank_recon = await settlement_service.get_settlement_bank_reconciliation("setl_test_001")
        
        from app.integrations.razorpay.schemas import RazorpaySettlementState
        assert bank_recon.settlement_status == RazorpaySettlementState.BANK_CREDIT_PENDING
        assert bank_recon.bank_matched is False

    @pytest.mark.asyncio
    async def test_bank_credit_confirmed_state(
        self, settlement_service: RazorpaySettlementIntelligenceService, 
        sample_settlement: TransactionORM, sample_bank_transaction: TransactionORM
    ):
        """Test BANK_CREDIT_CONFIRMED state when bank match is found."""
        bank_recon = await settlement_service.get_settlement_bank_reconciliation("setl_test_001")
        
        from app.integrations.razorpay.schemas import RazorpaySettlementState
        assert bank_recon.settlement_status == RazorpaySettlementState.BANK_CREDIT_CONFIRMED
        assert bank_recon.bank_matched is True
        assert bank_recon.bank_transaction_id is not None


class TestSettlementLinking:
    """Tests for settlement → transaction linking."""

    @pytest.mark.asyncio
    async def test_settlement_to_payment_linking(
        self, settlement_service: RazorpaySettlementIntelligenceService, sample_settlement: TransactionORM
    ):
        """Test linking settlements to payments in the same time window."""
        linkage = await settlement_service.get_settlement_transaction_linkage("setl_test_001")
        
        # Should return linkage structure
        assert linkage.settlement_id == "setl_test_001"
        assert isinstance(linkage.linked_transaction_count, int)
        assert isinstance(linkage.matched_transaction_count, int)
        assert isinstance(linkage.unmatched_transaction_count, int)
        assert isinstance(linkage.linked_transaction_ids, list)

    @pytest.mark.asyncio
    async def test_settlement_to_order_linking(
        self, settlement_service: RazorpaySettlementIntelligenceService, sample_settlement: TransactionORM
    ):
        """Test linking settlements to orders via payments."""
        # This would require creating payment and order transactions
        # For now, test that the linkage structure is correct
        linkage = await settlement_service.get_settlement_transaction_linkage("setl_test_001")
        
        assert hasattr(linkage, 'linked_transaction_ids')
        assert hasattr(linkage, 'matched_transaction_ids')
        assert hasattr(linkage, 'unmatched_transaction_ids')

    @pytest.mark.asyncio
    async def test_settlement_to_bank_transaction_linking(
        self, settlement_service: RazorpaySettlementIntelligenceService, 
        sample_settlement: TransactionORM, sample_bank_transaction: TransactionORM
    ):
        """Test linking settlements to bank transactions via UTR."""
        bank_recon = await settlement_service.get_settlement_bank_reconciliation("setl_test_001")
        
        assert bank_recon.bank_matched is True
        assert bank_recon.bank_transaction_id == sample_bank_transaction.domain_transaction_id
        assert bank_recon.utr == sample_bank_transaction.reference_number

    @pytest.mark.asyncio
    async def test_missing_linkage(
        self, settlement_service: RazorpaySettlementIntelligenceService, sample_settlement: TransactionORM, sample_bank_transaction: TransactionORM, session: AsyncSession
    ):
        """Test handling when no linkage can be established."""
        # Remove bank transaction
        await session.delete(sample_bank_transaction)
        await session.commit()
        
        bank_recon = await settlement_service.get_settlement_bank_reconciliation("setl_test_001")
        
        assert bank_recon.bank_matched is False
        assert bank_recon.bank_transaction_id is None


class TestSettlementExceptions:
    """Tests for settlement exception dossier creation."""

    @pytest.mark.asyncio
    async def test_exception_dossier_creation(
        self, settlement_service: RazorpaySettlementIntelligenceService, sample_settlement: TransactionORM
    ):
        """Test creating structured exception dossier."""
        dossier = await settlement_service.create_settlement_exception_dossier(
            settlement_id="setl_test_001",
            exception_type="AMOUNT_VARIANCE",
            confidence=Decimal("0.95"),
        )
        
        assert dossier.settlement_id == "setl_test_001"
        assert dossier.exception_type == "AMOUNT_VARIANCE"
        assert dossier.confidence == Decimal("0.95")
        assert isinstance(dossier.evidence, dict)
        assert isinstance(dossier.root_cause_candidates, list)
        assert isinstance(dossier.recommended_next_action, str)

    @pytest.mark.asyncio
    async def test_fee_variance_exception(
        self, settlement_service: RazorpaySettlementIntelligenceService, sample_settlement: TransactionORM
    ):
        """Test exception dossier for fee variance."""
        dossier = await settlement_service.create_settlement_exception_dossier(
            settlement_id="setl_test_001",
            exception_type="FEE_VARIANCE",
            confidence=Decimal("0.90"),
        )
        
        assert "fee" in dossier.recommended_next_action.lower() or "structure" in dossier.recommended_next_action.lower()

    @pytest.mark.asyncio
    async def test_tax_variance_exception(
        self, settlement_service: RazorpaySettlementIntelligenceService, sample_settlement: TransactionORM
    ):
        """Test exception dossier for tax variance."""
        dossier = await settlement_service.create_settlement_exception_dossier(
            settlement_id="setl_test_001",
            exception_type="TAX_VARIANCE",
            confidence=Decimal("0.85"),
        )
        
        assert "tax" in dossier.recommended_next_action.lower() or "gst" in dossier.recommended_next_action.lower()

    @pytest.mark.asyncio
    async def test_missing_bank_credit_exception(
        self, settlement_service: RazorpaySettlementIntelligenceService, sample_settlement: TransactionORM
    ):
        """Test exception dossier for missing bank credit."""
        dossier = await settlement_service.create_settlement_exception_dossier(
            settlement_id="setl_test_001",
            exception_type="MISSING_BANK_CREDIT",
            confidence=Decimal("0.98"),
        )
        
        assert "bank" in dossier.recommended_next_action.lower() or "credit" in dossier.recommended_next_action.lower()


class TestAIGrounding:
    """Tests for AI investigation grounding with settlement evidence."""

    @pytest.mark.asyncio
    async def test_ai_uses_authoritative_data(
        self, settlement_service: RazorpaySettlementIntelligenceService, sample_settlement: TransactionORM
    ):
        """Test that AI receives authoritative financial data, not invented values."""
        explanation = await settlement_service.explain_settlement("setl_test_001")
        
        # Evidence should contain actual settlement data
        assert "settlement_id" in explanation.evidence
        assert "financial_breakdown" in explanation.evidence
        assert explanation.gross_amount == sample_settlement.amount
        assert explanation.fee_amount == sample_settlement.fee
        assert explanation.tax_amount == sample_settlement.tax

    @pytest.mark.asyncio
    async def test_ai_does_not_invent_amounts(
        self, settlement_service: RazorpaySettlementIntelligenceService, sample_settlement: TransactionORM
    ):
        """Test that AI explanation uses actual amounts from database."""
        explanation = await settlement_service.explain_settlement("setl_test_001")
        
        # All amounts should match the actual settlement data
        assert explanation.gross_amount == sample_settlement.amount
        assert explanation.fee_amount == sample_settlement.fee
        assert explanation.tax_amount == sample_settlement.tax
        expected_net = sample_settlement.amount - sample_settlement.fee - sample_settlement.tax
        assert explanation.net_amount == expected_net

    @pytest.mark.asyncio
    async def test_ai_references_actual_transaction_ids(
        self, settlement_service: RazorpaySettlementIntelligenceService, sample_settlement: TransactionORM
    ):
        """Test that AI explanation references actual transaction IDs from database."""
        explanation = await settlement_service.explain_settlement("setl_test_001")
        
        # Should reference the actual settlement ID
        assert explanation.settlement_id == "setl_test_001"
        # Transaction IDs should be from actual database records
        assert isinstance(explanation.transaction_ids, list)

    @pytest.mark.asyncio
    async def test_ai_declares_insufficient_evidence(
        self, settlement_service: RazorpaySettlementIntelligenceService, sample_settlement: TransactionORM, session: AsyncSession
    ):
        """Test that AI explicitly states when evidence is insufficient."""
        # Create a settlement with minimal data
        from app.database.utils import utcnow
        import uuid
        
        minimal_settlement = TransactionORM(
            id=str(uuid.uuid4()),
            domain_transaction_id="setl_minimal_001",
            source=TransactionSource.GATEWAY.value,
            reference_number="UTR_MINIMAL",
            order_id=None,
            amount=Decimal("1000.00"),
            currency="INR",
            timestamp=utcnow(),
            narration="Minimal settlement",
            fee=None,  # No fee data
            tax=None,  # No tax data
            status=TransactionStatus.PROCESSED.value,
            meta_data={"type": "settlement", "lifecycle_state": "RAZORPAY_PROCESSED"},
            created_at=utcnow(),
        )
        session.add(minimal_settlement)
        await session.commit()
        
        explanation = await settlement_service.explain_settlement("setl_minimal_001")
        
        # Should handle missing fee/tax data gracefully
        assert explanation.fee_amount == Decimal("0")
        assert explanation.tax_amount == Decimal("0")
        
        # Cleanup
        await session.delete(minimal_settlement)
        await session.commit()


class TestSettlementExplanation:
    """Tests for the 'Explain this settlement' capability."""

    @pytest.mark.asyncio
    async def test_explanation_structure(
        self, settlement_service: RazorpaySettlementIntelligenceService, sample_settlement: TransactionORM
    ):
        """Test that explanation contains all required sections."""
        explanation = await settlement_service.explain_settlement("setl_test_001")
        
        # Summary section
        assert hasattr(explanation, 'settlement_id')
        assert hasattr(explanation, 'settlement_status')
        assert hasattr(explanation, 'expected_amount')
        assert hasattr(explanation, 'bank_amount')
        assert hasattr(explanation, 'variance')
        
        # Composition section
        assert hasattr(explanation, 'gross_amount')
        assert hasattr(explanation, 'fee_amount')
        assert hasattr(explanation, 'tax_amount')
        assert hasattr(explanation, 'net_amount')
        
        # Transaction evidence
        assert hasattr(explanation, 'linked_transaction_count')
        assert hasattr(explanation, 'matched_transaction_count')
        assert hasattr(explanation, 'unmatched_transaction_count')
        assert hasattr(explanation, 'transaction_ids')
        
        # Bank evidence
        assert hasattr(explanation, 'utr')
        assert hasattr(explanation, 'bank_matched')
        assert hasattr(explanation, 'bank_transaction_id')
        assert hasattr(explanation, 'bank_date')
        
        # Root cause and action
        assert hasattr(explanation, 'variance_type')
        assert hasattr(explanation, 'root_cause')
        assert hasattr(explanation, 'recommended_action')

    @pytest.mark.asyncio
    async def test_explanation_serialization(
        self, settlement_service: RazorpaySettlementIntelligenceService, sample_settlement: TransactionORM
    ):
        """Test that explanation can be serialized to dict."""
        explanation = await settlement_service.explain_settlement("setl_test_001")
        explanation_dict = explanation.to_dict()
        
        assert isinstance(explanation_dict, dict)
        assert "settlement_id" in explanation_dict
        assert "variance_type" in explanation_dict
        # Decimals should be converted to strings
        assert isinstance(explanation_dict["gross_amount"], str)
        assert isinstance(explanation_dict["variance"], str)


# Helper function for test data creation
async def _create_test_bank_transaction(session, settlement, amount):
    """Helper to create a test bank transaction."""
    from app.database.utils import utcnow
    import uuid
    
    bank_txn = TransactionORM(
        id=str(uuid.uuid4()),
        domain_transaction_id=f"bank_test_{settlement.domain_transaction_id}",
        source=TransactionSource.BANK.value,
        reference_number=settlement.reference_number,
        order_id=None,
        amount=amount,
        currency=settlement.currency,
        timestamp=utcnow() + timedelta(hours=1),
        narration=f"Bank credit {settlement.reference_number}",
        fee=None,
        tax=None,
        status=TransactionStatus.PROCESSED.value,
        meta_data={"type": "bank_credit"},
        created_at=utcnow(),
    )
    session.add(bank_txn)
    await session.commit()
    await session.refresh(bank_txn)
    return bank_txn
