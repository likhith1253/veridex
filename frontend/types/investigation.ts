/**
 * Type definitions for Investigation Evidence Dossier & Root Cause Analysis.
 * Verified against app/models/investigation_dossier.py and app/api/routes/investigations.py.
 */

export interface RootCauseCandidate {
  cause: string;
  confidence: number | string;
  evidence: string;

  // Normalized compatibility accessors
  evidence_summary?: string;
  features_cited?: string[];
}

export interface RelatedIDs {
  transaction_ids: string[];
  order_id?: string | null;
  settlement_id?: string | null;
  reference_number?: string | null;
}

export interface GroundedClaim {
  statement: string;
  grounded: boolean;
  source_reference?: string | null;
  confidence?: number | null;
}

export interface InvestigationDossier {
  investigation_id: string;
  entity_id: string;
  entity_type: string;
  status: string;
  exception_status?: string | null;
  financial_exposure: number | string;
  variance?: number | string;
  variance_type?: string;
  related_ids?: RelatedIDs;
  reconciliation_evidence?: Record<string, unknown>;
  root_cause_candidates: RootCauseCandidate[];
  recommended_action: string;
  requires_human_review: boolean;
  insufficient_evidence: boolean;
  evidence_summary: string;
  method: string;
  llm_invoked: boolean;
  created_at?: string | null;

  // Presentation compatibility accessors
  currency?: string;
  claims?: GroundedClaim[];
  evidence_graph?: {
    nodes: Array<{
      id: string;
      label: string;
      type: "order" | "payment" | "settlement" | "bank_credit" | "ledger_entry" | string;
      amount?: string | number | null;
      status?: string | null;
      source?: string | null;
      reference?: string | null;
      timestamp?: string | null;
    }>;
    edges: Array<{
      source: string;
      target: string;
      relation: string;
      status: "confirmed" | "inferred" | "discrepant" | "unresolved" | string;
    }>;
  } | null;
}
