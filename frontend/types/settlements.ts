/**
 * Type definitions for Settlement Intelligence, Financial Decomposition & Tax Audit.
 * Verified against FastAPI routes in app/api/routes/settlement_intelligence.py and app/api/schemas/settlement_intelligence.py.
 */

export interface SettlementListItem {
  settlement_id: string;
  settlement_date: string;
  status: string;
  gross_amount: string;
  expected_net_amount: string;
  bank_received_amount: string | null;
  variance: string;
  variance_type: "NO_VARIANCE" | "FEE_VARIANCE" | "TAX_VARIANCE" | "AMOUNT_VARIANCE" | "MISSING_BANK_CREDIT" | "UNEXPECTED_BANK_CREDIT" | "UNKNOWN_VARIANCE" | string;
  transaction_count: number;
  has_exception: boolean;

  // Optional presentation aliases
  amount?: string;
  currency?: string;
  fees?: string | null;
  tax?: string | null;
  utr?: string | null;
  created_at?: string | null;
  reconciliation_state?: string | null;
}

export interface SettlementListResponse {
  total_count: number;
  settlements: SettlementListItem[];
  filter_applied?: Record<string, unknown>;
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
  variance_type: "NO_VARIANCE" | "FEE_VARIANCE" | "TAX_VARIANCE" | "AMOUNT_VARIANCE" | "MISSING_BANK_CREDIT" | "UNEXPECTED_BANK_CREDIT" | "UNKNOWN_VARIANCE" | string;
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
  linked_transaction_count: number;
  matched_transaction_count: number;
  unmatched_transaction_count: number;
  linked_transaction_ids: string[];
  matched_transaction_ids: string[];
  unmatched_transaction_ids: string[];

  // Compatibility aliases
  utr?: string;
  total_payments_count?: number;
  total_payments_volume_inr?: string;
  payments?: Array<{
    payment_id: string;
    order_id?: string | null;
    amount?: string;
    fee?: string | null;
    tax?: string | null;
    method?: string | null;
    status?: string;
    timestamp?: string | null;
  }>;
}
