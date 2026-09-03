/**
 * Type definitions for Policy-Gated Finance Actions (Human-in-the-Loop).
 */

export interface FinanceAction {
  id: string;
  entity_type: "exception" | "settlement" | "transaction" | string;
  entity_id: string;
  action_type: "POST_ADJUSTMENT" | "WRITE_OFF" | "ESCALATE" | "RECONCILE_MANUAL" | string;
  state: "DETECTED" | "INVESTIGATING" | "RECOMMENDED" | "PENDING_APPROVAL" | "APPROVED" | "REJECTED" | "EXECUTED" | "FAILED" | string;
  amount: number | string;
  currency: string;
  recommended_by?: string | null;
  recommendation_reason?: string | null;
  evidence?: Record<string, unknown> | null;
  approved_by?: string | null;
  approved_at?: string | null;
  approval_reason?: string | null;
  rejected_by?: string | null;
  rejected_at?: string | null;
  rejection_reason?: string | null;
  execution_result?: {
    posted_adjustment_amount?: string | null;
    ledger_note?: string | null;
    executed_at?: string | null;
    error?: string | null;
  } | null;
  created_at?: string | null;
}

export interface ActionRecommendRequest {
  entity_type: string;
  entity_id: string;
  action_type: string;
  amount: string | number;
  currency?: string;
  recommended_by?: string;
  recommendation_reason: string;
  evidence?: Record<string, unknown>;
  run_id?: string | null;
}

export interface ActionDecisionRequest {
  actor: string;
  reason: string;
}

export interface ActionExecuteRequest {
  actor: string;
}
