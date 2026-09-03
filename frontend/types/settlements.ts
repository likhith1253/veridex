/**
 * Type definitions for Settlement Intelligence, Financial Breakdown & Tax Audit.
 */

export interface SettlementListItem {
  settlement_id: string;
  amount: string;
  currency: string;
  fees?: string | null;
  tax?: string | null;
  utr?: string | null;
  status: string;
  created_at?: string | null;
  reconciliation_state?: string | null;
}

export interface SettlementListResponse {
  total_count: number;
  settlements: SettlementListItem[];
}

export interface SettlementFinancialBreakdown {
  settlement_id: string;
  gross_amount: string;
  fee_amount: string;
  tax_amount: string;
  adjustment_amount: string;
  expected_net_amount: string;
  bank_received_amount: string;
  variance: string;
  currency: string;
  variance_type: "NO_VARIANCE" | "FEE_VARIANCE" | "TAX_VARIANCE" | "TIMING_DELAY" | "UNMATCHED_BANK_CREDIT" | "COMPLEX_VARIANCE" | string;
}

export interface SettlementTaxAudit {
  settlement_id: string;
  gross_amount: string;
  reported_tax?: string | null;
  expected_tax?: string | null;
  tax_variance?: string | null;
  status: "MATCHED" | "VARIANCE" | "INSUFFICIENT_EVIDENCE" | string;
  explanation: string;
  evidence_ids?: string[] | null;
  currency: string;
}

export interface SettlementTransactionLinkage {
  settlement_id: string;
  utr: string;
  total_payments_count: number;
  total_payments_volume_inr: string;
  payments: Array<{
    payment_id: string;
    order_id?: string | null;
    amount: string;
    fee?: string | null;
    tax?: string | null;
    method?: string | null;
    status: string;
    timestamp?: string | null;
  }>;
}
