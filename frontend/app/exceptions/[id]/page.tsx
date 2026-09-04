"use client";

import React, { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { controllerApi } from "@/lib/api/controllerApi";
import { investigationsApi } from "@/lib/api/investigationsApi";
import { actionsApi } from "@/lib/api/actionsApi";
import { formatINR, cn } from "@/lib/utils/formatters";
import { StatusBadge } from "@/components/common/StatusBadge";
import { ConfidenceBadge } from "@/components/common/ConfidenceBadge";
import { EvidenceGraph } from "@/components/exceptions/EvidenceGraph";
import { TechnicalReference } from "@/components/common/TechnicalReference";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { ErrorState } from "@/components/common/ErrorState";
import {
  ArrowLeft,
  ShieldCheck,
  Cpu,
  Database,
  CheckCircle2,
  Play,
  FileSearch,
  Lock,
  ChevronRight,
  AlertOctagon,
} from "lucide-react";

export default function ExceptionDossierPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const id = Array.isArray(params?.id) ? params.id[0] : (params?.id as string);

  const [decisionActor, setDecisionActor] = useState("FinanceOps_Lead");
  const [decisionReason, setDecisionReason] = useState("");
  const [decisionSuccess, setDecisionSuccess] = useState<string | null>(null);
  const [decisionError, setDecisionError] = useState<string | null>(null);

  // Load Exception Details
  const {
    data: exception,
    isLoading: exLoading,
    error: exError,
  } = useQuery({
    queryKey: ["exception-detail", id],
    queryFn: () => controllerApi.getExceptionDetail(id),
    enabled: !!id,
  });

  // Load Full Investigation Dossier
  const {
    data: dossier,
    isLoading: dossierLoading,
  } = useQuery({
    queryKey: ["investigation-dossier", id],
    queryFn: () => investigationsApi.getDossier(id),
    enabled: !!id,
  });

  // Human Decision Mutation
  const decisionMutation = useMutation({
    mutationFn: (action: string) => {
      setDecisionError(null);
      return controllerApi.applyHumanDecision(id, {
        action,
        actor: decisionActor,
        reason: decisionReason || `Human ${action} decision applied on exception dossier.`,
      });
    },
    onSuccess: (_, action) => {
      setDecisionSuccess(`Decision '${action}' committed to immutable audit trail.`);
      setDecisionError(null);
      queryClient.invalidateQueries();
    },
    onError: (err: Error) => {
      setDecisionError(err.message || "Failed to commit decision.");
      setDecisionSuccess(null);
    },
  });

  // Recommend Action Mutation
  const recommendActionMutation = useMutation({
    mutationFn: () => {
      setDecisionError(null);
      const rawExposure = exception?.financial_exposure_inr ?? exception?.financial_exposure ?? 0;
      const exposure = parseFloat(String(rawExposure));

      // Policy bounding: POST_ADJUSTMENT is strictly capped at INR 5,000.00 by backend policy.
      // If exposure > 5,000.00, recommend FLAG_INVESTIGATION so policy boundary is respected!
      let actionType = "POST_ADJUSTMENT";
      if (exposure > 5000) {
        actionType = "FLAG_INVESTIGATION";
      } else if (exposure <= 100 && exposure > 0) {
        actionType = "WRITE_OFF";
      }

      return actionsApi.recommendAction({
        entity_type: "exception",
        entity_id: id,
        action_type: actionType,
        amount: exposure,
        currency: "INR",
        recommended_by: "ai_investigation",
        recommendation_reason: decisionReason || exception?.explanation || "Recommended action for exception discrepancy.",
        run_id: exception?.run_id || null,
      });
    },
    onSuccess: () => {
      setDecisionSuccess("Finance Action recommended and queued for policy-gated authorization.");
      setDecisionError(null);
      queryClient.invalidateQueries();
    },
    onError: (err: Error) => {
      setDecisionError(err.message || "Failed to recommend action due to policy constraints.");
      setDecisionSuccess(null);
    },
  });

  if (exLoading || dossierLoading) {
    return (
      <div className="space-y-6">
        <div className="h-6 w-48 skeleton" />
        <LoadingSkeleton variant="dossier" />
      </div>
    );
  }

  if (exError || !exception) {
    return (
      <ErrorState
        title="Investigation Dossier Not Found"
        message={`Could not load investigation evidence for ID: ${id}`}
        onRetry={() => router.back()}
      />
    );
  }

  return (
    <div className="space-y-6 pb-12 select-none">
      {/* Top Breadcrumb & Navigation */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-3 border-b border-[#E2DDD3]">
        <div className="flex items-center gap-2 text-xs font-mono text-[#6F747A]">
          <Link href="/app" className="hover:text-[#9E7B35] transition-colors">Control Center</Link>
          <span>/</span>
          <Link href="/exceptions" className="hover:text-[#9E7B35] transition-colors">Exceptions</Link>
          <span>/</span>
          <span className="text-[#17191C] font-semibold">{id}</span>
        </div>
        <Link
          href="/exceptions"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xs text-xs font-medium bg-[#FFFFFF] border border-[#D7D3CA] text-[#17191C] hover:bg-[#F2EFE9] shadow-xs transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5 text-[#6F747A]" />
          <span>Back to Exceptions</span>
        </Link>
      </div>

      {/* Dossier Executive Banner */}
      <div
        className="rounded-sm border p-6 text-[#eceae6]"
        style={{
          borderColor: "var(--border-subtle)",
          background: "var(--surface-1)",
        }}
      >
        <div
          className="flex flex-col lg:flex-row lg:items-center justify-between gap-6 pb-5"
          style={{ borderBottom: "1px solid var(--border-subtle)" }}
        >
          <div>
            <div className="flex items-center gap-2.5 mb-1.5">
              {/* Primary heading: human-readable category name, not raw ID */}
              <h1 className="text-lg font-bold text-[#eceae6] capitalize">
                {(exception.category || exception.exception_category || "Exception").replace(/_/g, " ")}
              </h1>
              <StatusBadge status={exception.status} />
              <ConfidenceBadge confidence={exception.confidence} />
            </div>
            <div className="flex items-center gap-2 text-xs text-[#8e96a0] flex-wrap">
              <TechnicalReference id={id} label="exc" maxVisible={26} />
              {exception.transaction_id && (
                <>
                  <span className="text-[#3a3f45]">·</span>
                  <span>Anchor txn:</span>
                  <TechnicalReference id={exception.transaction_id} label="txn" maxVisible={22} inline />
                </>
              )}
              {exception.category && (
                <>
                  <span className="text-[#3a3f45]">·</span>
                  <strong className="text-[#c9a96e]">
                    {(exception.category || exception.exception_category || "unexplained").replace(/_/g, " ")}
                  </strong>
                </>
              )}
            </div>
          </div>

          <div className="flex items-baseline gap-6 font-mono">
            <div className="text-right">
              <span className="text-[10px] uppercase text-[#8e96a0] block">Monetary Exposure</span>
              <span className="text-2xl font-bold font-tabular text-[#e07070]">
                {formatINR(exception.financial_exposure_inr ?? exception.financial_exposure)}
              </span>
            </div>
            <div
              className="text-right pl-6"
              style={{ borderLeft: "1px solid var(--border-subtle)" }}
            >
              <span className="text-[10px] uppercase text-[#8e96a0] block">Expected Cost</span>
              <span className="text-lg font-bold font-tabular text-[#d4a84e]">
                {formatINR(exception.expected_cost_inr ?? exception.expected_cost ?? 0)}
              </span>
            </div>
          </div>
        </div>

        {/* Forensic Diagnosis */}
        <div className="pt-4 space-y-2">
          <div className="flex items-center gap-1.5 text-xs font-semibold text-[#c9a96e]">
            <FileSearch className="h-4 w-4" />
            <span>Forensic Diagnosis:</span>
          </div>
          <p
            className="text-xs leading-relaxed p-3.5 rounded-xs border text-[#eceae6]"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-2)",
            }}
          >
            {exception.explanation || "Automated analysis underway. No manual contradiction recorded."}
          </p>
        </div>
      </div>

      {/* ── 3-COLUMN FORENSIC WORKSPACE ─────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left (3.5 cols): Authoritative Financial Facts */}
        <div className="lg:col-span-4 space-y-5">
          <div
            className="rounded-sm border p-5 space-y-4"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-1)",
            }}
          >
            <div
              className="flex items-center justify-between pb-3"
              style={{ borderBottom: "1px solid var(--border-subtle)" }}
            >
              <div className="flex items-center gap-2">
                <Database className="h-4 w-4 text-[#c9a96e]" />
                <h2 className="text-xs font-bold uppercase tracking-wider text-[#eceae6]">
                  Authoritative Financial Facts
                </h2>
              </div>
              <span className="text-[10px] font-mono text-[#545e6a]">Ground Truth</span>
            </div>

            <div className="space-y-2.5 text-xs">
              {dossier?.claims && dossier.claims.length > 0 ? (
                dossier.claims.map((claim, idx) => (
                  <div
                    key={claim.statement ? `${claim.statement.slice(0, 20)}-${idx}` : `claim-${idx}`}
                    className="p-3 rounded-xs border space-y-1.5"
                    style={{
                      borderColor: "var(--border-subtle)",
                      background: "var(--surface-2)",
                    }}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[#eceae6] leading-snug">{claim.statement}</span>
                      <span
                        className="text-[9px] font-mono px-1.5 py-0.5 rounded-xs font-bold flex-shrink-0"
                        style={{
                          color: claim.grounded ? "var(--matched-text)" : "var(--text-secondary)",
                          background: claim.grounded ? "var(--matched-bg)" : "var(--surface-3)",
                          border: `1px solid ${claim.grounded ? "var(--matched-border)" : "var(--border-subtle)"}`,
                        }}
                      >
                        {claim.grounded ? "VERIFIED" : "INFERRED"}
                      </span>
                    </div>
                    {claim.source_reference && (
                      <div className="text-[10px] font-mono text-[#545e6a]">
                        Source: <span className="text-[#8e96a0]">{claim.source_reference}</span>
                      </div>
                    )}
                  </div>
                ))
              ) : (
                <div className="space-y-2 text-xs">
                  <div
                    className="p-3 rounded-xs border text-xs"
                    style={{
                      borderColor: "var(--border-subtle)",
                      background: "var(--surface-2)",
                    }}
                  >
                    <span className="text-[#6ecba0] font-bold mr-1.5">✓ Gateway:</span>
                    Payment <strong className="font-mono text-[#eceae6]">{exception.transaction_id}</strong> captured in settlement feed.
                  </div>
                  <div
                    className="p-3 rounded-xs border text-xs"
                    style={{
                      borderColor: "var(--variance-border)",
                      background: "var(--variance-bg)",
                    }}
                  >
                    <span className="text-[#e07070] font-bold mr-1.5">⚠ Discrepancy:</span>
                    Exposure of <strong className="font-mono text-[#eceae6]">{formatINR(exception.financial_exposure)}</strong> pending core bank match.
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Root-Cause Assessment */}
          <div
            className="rounded-sm border p-5 space-y-4"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-1)",
            }}
          >
            <div
              className="flex items-center justify-between pb-3"
              style={{ borderBottom: "1px solid var(--border-subtle)" }}
            >
              <div className="flex items-center gap-2">
                <Cpu className="h-4 w-4 text-[#9aa5b2]" />
                <h2 className="text-xs font-bold uppercase tracking-wider text-[#eceae6]">
                  Root-Cause Assessment
                </h2>
              </div>
              <span className="text-[10px] font-mono text-[#545e6a]">Model Arbitration</span>
            </div>

            <div className="space-y-3">
              {dossier?.root_cause_candidates && dossier.root_cause_candidates.length > 0 ? (
                dossier.root_cause_candidates.map((rc, idx) => (
                  <div
                    key={rc.cause ? `${rc.cause}-${idx}` : `rc-${idx}`}
                    className="p-3.5 rounded-xs border space-y-2 text-xs"
                    style={{
                      borderColor: "var(--border-subtle)",
                      background: "var(--surface-2)",
                    }}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-[#eceae6] capitalize">
                        {(rc.cause || "UNKNOWN").replace(/_/g, " ")}
                      </span>
                      <ConfidenceBadge confidence={typeof rc.confidence === "string" ? parseFloat(rc.confidence) : rc.confidence} />
                    </div>
                    <p className="text-[11px] text-[#8e96a0] leading-snug">
                      {rc.evidence_summary || rc.evidence}
                    </p>
                  </div>
                ))
              ) : (
                <div className="p-3.5 rounded-xs border text-xs text-[#8e96a0]" style={{ borderColor: "var(--border-subtle)", background: "var(--surface-2)" }}>
                  Classified root cause: <strong className="text-[#eceae6] capitalize">{(exception.category || exception.exception_category || "unexplained").replace(/_/g, " ")}</strong> (Authoritative Grounding)
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Center (5 cols): Large Hero Evidence Graph Canvas (~50% desktop space) */}
        <div className="lg:col-span-5 space-y-5">
          <EvidenceGraph
            transactionId={exception.transaction_id}
            nodes={dossier?.evidence_graph?.nodes}
            edges={dossier?.evidence_graph?.edges}
          />
        </div>

        {/* Right (3.5 cols): Governance Rail & Human Controller Boundary */}
        <div className="lg:col-span-3 space-y-5">
          {/* Reusable Governance Rail */}
          <div
            className="rounded-sm border p-5 space-y-4"
            style={{
              borderColor: "var(--accent-border)",
              background: "var(--surface-1)",
              borderTop: "2px solid var(--accent)",
            }}
          >
            <div
              className="flex items-center justify-between pb-3"
              style={{ borderBottom: "1px solid var(--border-subtle)" }}
            >
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-[#c9a96e]" />
                <h2 className="text-xs font-bold uppercase tracking-wider text-[#eceae6]">
                  Action Governance Rail
                </h2>
              </div>
              <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded-xs text-[#d4a84e]" style={{ background: "var(--pending-bg)", border: "1px solid var(--pending-border)" }}>
                HITL MANDATORY
              </span>
            </div>

            {/* Stepper sequence */}
            <div className="space-y-2 text-[11px] font-mono">
              <div className="flex items-center gap-2 text-[#6ecba0]">
                <CheckCircle2 className="h-3.5 w-3.5" />
                <span>1. AI ANALYSIS</span>
              </div>
              <div className="flex items-center gap-2 text-[#6ecba0]">
                <CheckCircle2 className="h-3.5 w-3.5" />
                <span>2. RECOMMENDATION</span>
              </div>
              <div className="flex items-center gap-2 text-[#c9a96e] font-bold">
                <div className="w-3.5 h-3.5 rounded-full bg-[#c9a96e] text-[#080a0c] flex items-center justify-center text-[9px]">3</div>
                <span>3. HUMAN REVIEW (ACTIVE)</span>
              </div>
              <div className="flex items-center gap-2 text-[#545e6a]">
                <Lock className="h-3.5 w-3.5" />
                <span>4. AUTHORIZED</span>
              </div>
              <div className="flex items-center gap-2 text-[#545e6a]">
                <Play className="h-3.5 w-3.5" />
                <span>5. EXECUTION</span>
              </div>
              <div className="flex items-center gap-2 text-[#545e6a]">
                <Database className="h-3.5 w-3.5" />
                <span>6. AUDITED</span>
              </div>
            </div>

            {/* Recommended Policy Action */}
            <div className="pt-2">
              <span className="text-[10px] text-[#8e96a0] uppercase block mb-1">
                Recommended Resolution:
              </span>
              <div
                className="p-3 rounded-xs border text-xs text-[#eceae6]"
                style={{
                  borderColor: "var(--border-subtle)",
                  background: "var(--surface-2)",
                }}
              >
                {exception.recommended_action || "Post Ledger Adjustment within tolerance"}
              </div>
            </div>

            {decisionSuccess && (
              <div
                className="p-3 rounded-xs border text-xs font-mono flex items-center gap-2 text-[#6ecba0]"
                style={{
                  borderColor: "var(--matched-border)",
                  background: "var(--matched-bg)",
                }}
              >
                <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
                <span>{decisionSuccess}</span>
              </div>
            )}

            {decisionError && (
              <div
                className="p-3 rounded-xs border text-xs font-mono flex items-center gap-2 text-[#e07070]"
                style={{
                  borderColor: "var(--variance-border)",
                  background: "var(--variance-bg)",
                }}
              >
                <AlertOctagon className="h-4 w-4 flex-shrink-0" />
                <span>{decisionError}</span>
              </div>
            )}

            {/* Decision Input Controls */}
            <div className="space-y-3 pt-2 text-xs">
              <div>
                <label className="block text-[#8e96a0] mb-1 text-[11px]">
                  Authorizing Actor ID:
                </label>
                <input
                  type="text"
                  value={decisionActor}
                  onChange={(e) => setDecisionActor(e.target.value)}
                  className="w-full rounded-xs border px-3 py-1.5 font-mono text-xs text-[#eceae6] focus:outline-hidden"
                  style={{
                    borderColor: "var(--border-standard)",
                    background: "var(--surface-2)",
                  }}
                />
              </div>

              <div>
                <label className="block text-[#8e96a0] mb-1 text-[11px]">
                  Audit Justification:
                </label>
                <textarea
                  rows={2}
                  value={decisionReason}
                  onChange={(e) => setDecisionReason(e.target.value)}
                  placeholder="Record formal justification..."
                  className="w-full rounded-xs border px-3 py-1.5 text-xs text-[#eceae6] focus:outline-hidden"
                  style={{
                    borderColor: "var(--border-standard)",
                    background: "var(--surface-2)",
                  }}
                />
              </div>

              {/* Primary Gold Action */}
              <button
                onClick={() => recommendActionMutation.mutate()}
                disabled={recommendActionMutation.isPending}
                className="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-xs text-xs font-semibold transition-micro disabled:opacity-50"
                style={{
                  color: "#080a0c",
                  background: "var(--accent)",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "var(--accent-hover)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "var(--accent)")}
              >
                <Play className="h-3.5 w-3.5 fill-current" />
                <span>Queue Policy Action (HITL)</span>
              </button>

              <div className="grid grid-cols-2 gap-2 pt-1">
                <button
                  onClick={() => decisionMutation.mutate("resolve")}
                  disabled={decisionMutation.isPending}
                  className="px-2.5 py-1.5 rounded-xs border text-xs font-medium text-[#eceae6] hover:bg-[#181c22] transition-micro"
                  style={{
                    borderColor: "var(--border-standard)",
                    background: "var(--surface-2)",
                  }}
                >
                  Mark Resolved
                </button>

                <button
                  onClick={() => decisionMutation.mutate("escalate")}
                  disabled={decisionMutation.isPending}
                  className="px-2.5 py-1.5 rounded-xs border text-xs font-medium text-[#d4a84e] transition-micro"
                  style={{
                    borderColor: "var(--pending-border)",
                    background: "var(--pending-bg)",
                  }}
                >
                  Escalate
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
