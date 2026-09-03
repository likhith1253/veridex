/**
 * Settlement Intelligence, Financial Decomposition & Tax Audit API Service.
 * Verified against FastAPI routes in app/api/routes/settlement_intelligence.py.
 */

import { apiClient } from "./client";
import type {
  SettlementFinancialBreakdown,
  SettlementListResponse,
  SettlementTaxAudit,
  SettlementTransactionLinkage,
} from "@/types/settlements";

export const settlementsApi = {
  /** List settlement records from the verified /list endpoint */
  getSettlements: async (params?: {
    status_filter?: string;
    limit?: number;
    offset?: number;
    from_date?: string;
    to_date?: string;
    exception_type?: string;
  }): Promise<SettlementListResponse> => {
    const searchParams = new URLSearchParams();
    if (params?.status_filter) searchParams.append("status_filter", params.status_filter);
    if (params?.limit) searchParams.append("limit", params.limit.toString());
    if (params?.offset) searchParams.append("offset", params.offset.toString());
    if (params?.from_date) searchParams.append("from_date", params.from_date);
    if (params?.to_date) searchParams.append("to_date", params.to_date);
    if (params?.exception_type) searchParams.append("exception_type", params.exception_type);

    const qs = searchParams.toString();
    const res = await apiClient<SettlementListResponse>(`/api/v1/settlements/list${qs ? `?${qs}` : ""}`);
    
    // Clean normalization adapter
    return {
      total_count: res.total_count ?? (res.settlements ? res.settlements.length : 0),
      settlements: (res.settlements || []).map((s) => ({
        ...s,
        amount: s.gross_amount ?? s.amount,
        utr: s.utr ?? null,
      })),
      filter_applied: res.filter_applied || {},
    };
  },

  /** Get visual financial decomposition (Gross - Fees - Taxes = Expected Net vs Bank Received) */
  getFinancialBreakdown: async (settlementId: string): Promise<SettlementFinancialBreakdown> => {
    return apiClient<SettlementFinancialBreakdown>(
      `/api/v1/settlements/${encodeURIComponent(settlementId)}/financial-breakdown`
    );
  },

  /** Audit Razorpay settlement tax line items against authoritative expected tax */
  getTaxAudit: async (settlementId: string): Promise<SettlementTaxAudit> => {
    return apiClient<SettlementTaxAudit>(
      `/api/v1/settlements/${encodeURIComponent(settlementId)}/tax-audit`
    );
  },

  /** Get transaction linkage (which transactions belong to a settlement) */
  getTransactionLinkage: async (settlementId: string): Promise<SettlementTransactionLinkage> => {
    const res = await apiClient<SettlementTransactionLinkage>(
      `/api/v1/settlements/${encodeURIComponent(settlementId)}/transaction-linkage`
    );
    return {
      ...res,
      total_payments_count: res.linked_transaction_count ?? (res.linked_transaction_ids ? res.linked_transaction_ids.length : 0),
      total_payments_volume_inr: "—",
      payments: (res.linked_transaction_ids || []).map((tid) => ({
        payment_id: tid,
        amount: undefined,
        status: "LINKED",
      })),
    };
  },

  /** Explain settlement calculation and reconciliation state */
  explainSettlement: async (settlementId: string): Promise<Record<string, unknown>> => {
    return apiClient<Record<string, unknown>>(
      `/api/v1/settlements/${encodeURIComponent(settlementId)}/explain`
    );
  },

  /** Get dashboard summary metrics for settlements */
  getDashboardSummary: async (): Promise<Record<string, unknown>> => {
    return apiClient<Record<string, unknown>>("/api/v1/settlements/dashboard/summary");
  },
};
