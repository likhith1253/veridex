"""
Razorpay Settlement Intelligence API Routes for Project Sentinel.

Provides endpoints for:
- Settlement financial breakdown
- Settlement → transaction linking
- Bank reconciliation status
- Settlement exception dossiers
- "Explain this settlement" capability
- Settlement dashboard metrics
- Time-based settlement filtering
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_db_session
from app.api.schemas.settlement_intelligence import (
    SettlementDashboardSummary,
    SettlementExceptionDossierResponse,
    SettlementExplanationResponse,
    SettlementFinancialBreakdownResponse,
    SettlementListFilter,
    SettlementListItem,
    SettlementListResponse,
    SettlementStatusFilter,
    SettlementTaxAuditResponse,
    SettlementTransactionLinkageResponse,
    SettlementVarianceType,
    TaxAuditStatus,
)
from app.database.models import Transaction as TransactionORM
from app.integrations.razorpay.schemas import RazorpaySettlementState
from app.models.transaction import TransactionSource
from app.services.razorpay_settlement_intelligence_service import (
    RazorpaySettlementIntelligenceService,
    SettlementVarianceType as ServiceVarianceType,
)

router = APIRouter(prefix="/api/v1/settlements", tags=["Settlement Intelligence"])


@router.get("/{settlement_id}/financial-breakdown", response_model=SettlementFinancialBreakdownResponse)
async def get_settlement_financial_breakdown(
    settlement_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> SettlementFinancialBreakdownResponse:
    """Get financial decomposition (gross, fees, taxes, expected net, bank received, variance) for a settlement."""
    try:
        service = RazorpaySettlementIntelligenceService(session)
        breakdown = await service.get_settlement_financial_breakdown(settlement_id)
        return SettlementFinancialBreakdownResponse(
            settlement_id=breakdown.settlement_id,
            gross_amount=str(breakdown.gross_amount),
            fee_amount=str(breakdown.fee_amount),
            tax_amount=str(breakdown.tax_amount),
            adjustment_amount=str(breakdown.adjustment_amount),
            expected_net_amount=str(breakdown.expected_net_amount),
            bank_received_amount=str(breakdown.bank_received_amount),
            bank_matched=breakdown.bank_matched,
            variance=str(breakdown.variance),
            currency=breakdown.currency,
            variance_type=SettlementVarianceType(breakdown.variance_type.value),
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get financial breakdown: {str(e)}")


@router.get("/{settlement_id}/tax-audit", response_model=SettlementTaxAuditResponse)
async def audit_settlement_tax(
    settlement_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> SettlementTaxAuditResponse:
    """Audit Razorpay settlement tax lines against authoritative expected tax."""
    try:
        service = RazorpaySettlementIntelligenceService(session)
        audit_res = await service.audit_settlement_tax(settlement_id)
        return SettlementTaxAuditResponse(
            settlement_id=audit_res.settlement_id,
            gross_amount=str(audit_res.gross_amount),
            reported_tax=str(audit_res.reported_tax) if audit_res.reported_tax is not None else None,
            expected_tax=str(audit_res.expected_tax) if audit_res.expected_tax is not None else None,
            tax_variance=str(audit_res.tax_variance) if audit_res.tax_variance is not None else None,
            status=audit_res.status,
            explanation=audit_res.explanation,
            evidence_ids=audit_res.evidence_ids,
            currency=audit_res.currency,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to audit settlement tax: {str(e)}")


@router.get("/{settlement_id}/transaction-linkage", response_model=SettlementTransactionLinkageResponse)
async def get_settlement_transaction_linkage(
    settlement_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> SettlementTransactionLinkageResponse:
    """Get which transactions belong to a settlement and their match status."""
    try:
        service = RazorpaySettlementIntelligenceService(session)
        linkage = await service.get_settlement_transaction_linkage(settlement_id)
        return SettlementTransactionLinkageResponse(
            settlement_id=linkage.settlement_id,
            linked_transaction_count=linkage.linked_transaction_count,
            matched_transaction_count=linkage.matched_transaction_count,
            unmatched_transaction_count=linkage.unmatched_transaction_count,
            linked_transaction_ids=linkage.linked_transaction_ids,
            matched_transaction_ids=linkage.matched_transaction_ids,
            unmatched_transaction_ids=linkage.unmatched_transaction_ids,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get transaction linkage: {str(e)}")


@router.get("/{settlement_id}/bank-reconciliation")
async def get_settlement_bank_reconciliation(
    settlement_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Get bank reconciliation state for a settlement."""
    try:
        service = RazorpaySettlementIntelligenceService(session)
        recon = await service.get_settlement_bank_reconciliation(settlement_id)
        return recon.to_dict()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get bank reconciliation: {str(e)}")


@router.get("/{settlement_id}/exception-dossier", response_model=SettlementExceptionDossierResponse)
async def get_settlement_exception_dossier(
    settlement_id: str,
    exception_type: str = Query(..., description="Type of settlement exception"),
    confidence: str = Query("0.95", description="Confidence score for the exception"),
    session: AsyncSession = Depends(get_db_session),
) -> SettlementExceptionDossierResponse:
    """Create structured investigation object for settlement exceptions."""
    try:
        service = RazorpaySettlementIntelligenceService(session)
        confidence_decimal = Decimal(confidence)
        dossier = await service.create_settlement_exception_dossier(
            settlement_id=settlement_id,
            exception_type=exception_type,
            confidence=confidence_decimal,
        )
        return SettlementExceptionDossierResponse(
            settlement_id=dossier.settlement_id,
            settlement_status=dossier.settlement_status,
            settlement_period=dossier.settlement_period,
            gross_amount=str(dossier.gross_amount),
            fee_amount=str(dossier.fee_amount),
            tax_amount=str(dossier.tax_amount),
            expected_net_amount=str(dossier.expected_net_amount),
            bank_received_amount=str(dossier.bank_received_amount),
            variance=str(dossier.variance),
            linked_transaction_count=dossier.linked_transaction_count,
            matched_transaction_count=dossier.matched_transaction_count,
            unmatched_transaction_count=dossier.unmatched_transaction_count,
            exception_type=dossier.exception_type,
            confidence=str(dossier.confidence),
            evidence=dossier.evidence,
            root_cause_candidates=dossier.root_cause_candidates,
            recommended_next_action=dossier.recommended_next_action,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create exception dossier: {str(e)}")


@router.get("/{settlement_id}/explain", response_model=SettlementExplanationResponse)
async def explain_settlement(
    settlement_id: str,
    session: AsyncSession = Depends(get_db_session),
) -> SettlementExplanationResponse:
    """Provide complete explanation of a settlement for finance operators."""
    try:
        service = RazorpaySettlementIntelligenceService(session)
        explanation = await service.explain_settlement(settlement_id)
        return SettlementExplanationResponse(
            settlement_id=explanation.settlement_id,
            settlement_status=explanation.settlement_status,
            expected_amount=str(explanation.expected_amount),
            bank_amount=str(explanation.bank_amount) if explanation.bank_amount else None,
            variance=str(explanation.variance),
            gross_amount=str(explanation.gross_amount),
            fee_amount=str(explanation.fee_amount),
            tax_amount=str(explanation.tax_amount),
            adjustment_amount=str(explanation.adjustment_amount),
            net_amount=str(explanation.net_amount),
            linked_transaction_count=explanation.linked_transaction_count,
            matched_transaction_count=explanation.matched_transaction_count,
            unmatched_transaction_count=explanation.unmatched_transaction_count,
            transaction_ids=explanation.transaction_ids,
            utr=explanation.utr,
            bank_matched=explanation.bank_matched,
            bank_transaction_id=explanation.bank_transaction_id,
            bank_date=explanation.bank_date.isoformat() if explanation.bank_date else None,
            variance_type=SettlementVarianceType(explanation.variance_type.value),
            root_cause=explanation.root_cause,
            recommended_action=explanation.recommended_action,
            evidence=explanation.evidence,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to explain settlement: {str(e)}")


@router.get("/dashboard/summary", response_model=SettlementDashboardSummary)
async def get_settlement_dashboard_summary(
    session: AsyncSession = Depends(get_db_session),
) -> SettlementDashboardSummary:
    """Get summary metrics for the settlement dashboard."""
    try:
        # Get all settlement transactions
        stmt = select(TransactionORM).where(
            and_(
                TransactionORM.source == TransactionSource.GATEWAY.value,
                TransactionORM.meta_data["type"].astext == "settlement"
            )
        )
        result = await session.execute(stmt)
        settlements = result.scalars().all()
        
        total_settlements = len(settlements)
        
        # Calculate status counts
        processed_count = 0
        bank_confirmed_count = 0
        pending_bank_credit = 0
        matched_count = 0
        exception_count = 0
        
        total_gross = Decimal("0")
        total_fees = Decimal("0")
        total_taxes = Decimal("0")
        total_expected_net = Decimal("0")
        total_bank_received = Decimal("0")
        total_variance = Decimal("0")
        
        for settlement in settlements:
            # Determine status from metadata
            lifecycle_state = settlement.meta_data.get("lifecycle_state", "RAZORPAY_PROCESSED") if settlement.meta_data else "RAZORPAY_PROCESSED"
            
            if lifecycle_state == "RAZORPAY_PROCESSED":
                processed_count += 1
            elif lifecycle_state == "BANK_CREDIT_CONFIRMED":
                bank_confirmed_count += 1
                matched_count += 1
            elif lifecycle_state == "BANK_CREDIT_PENDING":
                pending_bank_credit += 1
                processed_count += 1
            
            # Check if settlement has an exception
            # This would typically be done via exception table, but for now we use variance
            if settlement.amount and settlement.fee and settlement.tax:
                expected_net = settlement.amount - settlement.fee - settlement.tax
                # If variance is significant, count as exception
                # For now, we'll estimate based on whether bank match exists
                # This is a simplification - real implementation would query exception table
            
            # Aggregate financial values
            total_gross += settlement.amount or Decimal("0")
            total_fees += settlement.fee or Decimal("0")
            total_taxes += settlement.tax or Decimal("0")
            expected_net = (settlement.amount or Decimal("0")) - (settlement.fee or Decimal("0")) - (settlement.tax or Decimal("0"))
            total_expected_net += expected_net
            
            # Bank received is harder to determine without matching
            # For now, we'll estimate based on bank-confirmed settlements
            if lifecycle_state == "BANK_CREDIT_CONFIRMED":
                total_bank_received += expected_net
                total_variance += Decimal("0")  # No variance if confirmed
            else:
                # For pending settlements, variance is the full expected amount
                total_variance += expected_net
        
        return SettlementDashboardSummary(
            total_settlements=total_settlements,
            processed_settlements=processed_count,
            bank_confirmed_settlements=bank_confirmed_count,
            pending_bank_credit=pending_bank_credit,
            matched_settlements=matched_count,
            exception_settlements=exception_count,
            total_gross=str(total_gross.quantize(Decimal("0.01"))),
            total_fees=str(total_fees.quantize(Decimal("0.01"))),
            total_taxes=str(total_taxes.quantize(Decimal("0.01"))),
            total_expected_net=str(total_expected_net.quantize(Decimal("0.01"))),
            total_bank_received=str(total_bank_received.quantize(Decimal("0.01"))),
            total_variance=str(total_variance.quantize(Decimal("0.01"))),
            currency="INR",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard summary: {str(e)}")


@router.get("/list", response_model=SettlementListResponse)
async def list_settlements(
    from_date: Optional[datetime] = Query(None, description="Start date for settlement period"),
    to_date: Optional[datetime] = Query(None, description="End date for settlement period"),
    status_filter: SettlementStatusFilter = Query(SettlementStatusFilter.ALL, description="Filter by settlement status"),
    exception_type: Optional[str] = Query(None, description="Filter by exception type"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of settlements to return"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    session: AsyncSession = Depends(get_db_session),
) -> SettlementListResponse:
    """List settlements with filtering by date range, status, and exception type."""
    try:
        # Build base query
        stmt = select(TransactionORM).where(
            and_(
                TransactionORM.source == TransactionSource.GATEWAY.value,
                TransactionORM.meta_data["type"].astext == "settlement"
            )
        )
        
        # Apply date filter
        if from_date:
            stmt = stmt.where(TransactionORM.timestamp >= from_date)
        if to_date:
            stmt = stmt.where(TransactionORM.timestamp <= to_date)
        
        # Apply status filter
        if status_filter != SettlementStatusFilter.ALL:
            stmt = stmt.where(
                TransactionORM.meta_data["lifecycle_state"].astext == status_filter.value
            )
        
        # Get total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_result = await session.execute(count_stmt)
        total_count = count_result.scalar() or 0
        
        # Apply pagination and ordering
        stmt = stmt.order_by(TransactionORM.timestamp.desc()).offset(offset).limit(limit)
        
        result = await session.execute(stmt)
        settlements = result.scalars().all()
        
        # Build response items
        items = []
        for settlement in settlements:
            # Calculate financial values
            gross = settlement.amount or Decimal("0")
            fee = settlement.fee or Decimal("0")
            tax = settlement.tax or Decimal("0")
            expected_net = gross - fee - tax
            
            # Determine status
            lifecycle_state = settlement.meta_data.get("lifecycle_state", "RAZORPAY_PROCESSED") if settlement.meta_data else "RAZORPAY_PROCESSED"
            
            # Determine variance type (simplified)
            if lifecycle_state == "BANK_CREDIT_CONFIRMED":
                variance_type = SettlementVarianceType.NO_VARIANCE
                bank_received = str(expected_net)
                variance = "0.00"
            else:
                variance_type = SettlementVarianceType.MISSING_BANK_CREDIT
                bank_received = None
                variance = str(expected_net)
            
            # Transaction count (simplified - would need actual linkage query)
            transaction_count = 0  # Placeholder
            
            items.append(SettlementListItem(
                settlement_id=settlement.domain_transaction_id,
                settlement_date=settlement.timestamp.isoformat(),
                status=lifecycle_state,
                gross_amount=str(gross.quantize(Decimal("0.01"))),
                expected_net_amount=str(expected_net.quantize(Decimal("0.01"))),
                bank_received_amount=bank_received,
                variance=variance,
                variance_type=variance_type,
                transaction_count=transaction_count,
                has_exception=False,  # Would need exception table query
            ))
        
        filter_applied = {
            "from_date": from_date.isoformat() if from_date else None,
            "to_date": to_date.isoformat() if to_date else None,
            "status_filter": status_filter.value,
            "exception_type": exception_type,
        }
        
        return SettlementListResponse(
            settlements=items,
            total_count=total_count,
            filter_applied=filter_applied,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list settlements: {str(e)}")
