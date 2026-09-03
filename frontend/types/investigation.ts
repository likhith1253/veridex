/**
 * Type definitions for Investigation Evidence Dossier & Root Cause Analysis.
 */

export interface RootCauseCandidate {
  cause: string;
  confidence: number;
  evidence_summary: string;
  features_cited?: string[];
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
  entity_type: "exception" | "settlement" | "transaction" | string;
  status: string;
  financial_exposure: number;
  currency: string;
  root_cause_candidates: RootCauseCandidate[];
  claims: GroundedClaim[];
  recommended_action: string;
  human_review_required: boolean;
  insufficient_evidence: boolean;
  created_at?: string | null;
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
