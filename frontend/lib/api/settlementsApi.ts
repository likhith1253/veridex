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
  /** List settlement records */
  getSettlements: async (params?: {
    status?: string;
    limit?: number;
    offset?: number;
  }): Promise<SettlementListResponse> => {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.append("status", params.status);
    if (params?.limit) searchParams.append("limit", params.limit.toString());
    if (params?.offset) searchParams.append("offset", params.offset.toString());

    const qs = searchParams.toString();
    return apiClient<SettlementListResponse>(`/api/v1/settlements${qs ? `?${qs}` : ""}`);
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

  /** Get linked transaction list for a settlement payout UTR */
  getTransactionLinkage: async (settlementId: string): Promise<SettlementTransactionLinkage> => {
    return apiClient<SettlementTransactionLinkage>(
      `/api/v1/settlements/${encodeURIComponent(settlementId)}/transactions`
    );
  },
};
