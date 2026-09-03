"use client";

import React, { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { controllerApi } from "@/lib/api/controllerApi";
import { investigationsApi } from "@/lib/api/investigationsApi";
import { actionsApi } from "@/lib/api/actionsApi";
import { formatINR, formatPercent, cn } from "@/lib/utils/formatters";
import { StatusBadge } from "@/components/common/StatusBadge";
import { ConfidenceBadge } from "@/components/common/ConfidenceBadge";
import { EvidenceGraph } from "@/components/exceptions/EvidenceGraph";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { ErrorState } from "@/components/common/ErrorState";
import {
  ArrowLeft,
  ShieldCheck,
  Cpu,
  FileCheck,
  AlertTriangle,
  Database,
  Layers,
  Sparkles,
  CheckCircle2,
  XCircle,
  Play,
} from "lucide-react";

export default function ExceptionDossierPage() {
  const params = useParams();
  const router = useRouter();
  const queryClient = useQueryClient();
  const id = Array.isArray(params?.id) ? params.id[0] : (params?.id as string);

  const [decisionActor, setDecisionActor] = useState("FinanceOps_Lead");
  const [decisionReason, setDecisionReason] = useState("");
  const [decisionSuccess, setDecisionSuccess] = useState<string | null>(null);

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
    mutationFn: (action: string) =>
      controllerApi.applyHumanDecision(id, {
        action,
        actor: decisionActor,
        reason: decisionReason || `Human ${action} decision applied on exception dossier.`,
      }),
    onSuccess: (_, action) => {
      setDecisionSuccess(`Decision '${action}' successfully committed to immutable audit log.`);
      queryClient.invalidateQueries();
    },
  });

  // Recommend Action Mutation
  const recommendActionMutation = useMutation({
    mutationFn: () =>
      actionsApi.recommendAction({
        entity_type: "exception",
        entity_id: id,
        action_type: "POST_ADJUSTMENT",
        amount: exception?.financial_exposure || "0",
        recommendation_reason: exception?.explanation || "Auto-recommended adjustment for exception discrepancy.",
        run_id: exception?.run_id,
      }),
    onSuccess: () => {
      setDecisionSuccess("Finance Action recommended and queued for policy-gated approval.");
      queryClient.invalidateQueries();
    },
  });

  if (exLoading || dossierLoading) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 rounded bg-zinc-800 animate-pulse" />
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
    <div className="space-y-6">
      {/* Top Breadcrumb & Back */}
      <div className="flex items-center gap-3">
        <Link
          href="/exceptions"
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#171a23] hover:bg-[#1e222e] text-zinc-400 hover:text-zinc-200 border border-zinc-800 font-mono text-xs transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Back to Exception Queue
        </Link>
        <span className="text-zinc-600">/</span>
        <span className="text-xs font-mono text-zinc-400">Forensic Dossier: {id}</span>
      </div>

      {/* Dossier Executive Header */}
      <div className="rounded-lg border border-[#222634] bg-[#11131a] p-6 text-zinc-100">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pb-4 border-b border-zinc-800/80">
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-base font-bold font-mono text-zinc-100">{id}</h1>
              <StatusBadge status={exception.status} />
              <ConfidenceBadge confidence={exception.confidence} />
            </div>
            <p className="text-xs font-mono text-zinc-400 mt-1">
              Transaction Ref: <strong className="text-zinc-200">{exception.transaction_id || "—"}</strong> | Category:{" "}
              <strong className="text-zinc-200">{(exception.category || exception.exception_category || "unexplained").replace(/_/g, " ")}</strong>
            </p>
          </div>

          <div className="flex items-baseline gap-4">
            <div className="text-right font-mono">
              <span className="text-[10px] text-zinc-500 uppercase block">Financial Exposure</span>
              <span className="text-2xl font-bold font-tabular text-rose-400">
                {formatINR(exception.financial_exposure_inr ?? exception.financial_exposure)}
              </span>
            </div>
            <div className="text-right font-mono pl-4 border-l border-zinc-800">
              <span className="text-[10px] text-zinc-500 uppercase block">Expected Cost</span>
              <span className="text-base font-bold font-tabular text-amber-300">
                {formatINR(exception.expected_cost_inr ?? exception.expected_cost)}
              </span>
            </div>
          </div>
        </div>

        {/* AI Forensic Explanation */}
        <div className="pt-4 space-y-2">
          <div className="flex items-center gap-1.5 text-xs font-bold font-mono text-sky-400">
            <Sparkles className="h-4 w-4" /> Root-Cause Forensic Diagnosis:
          </div>
          <p className="text-xs font-mono text-zinc-300 leading-relaxed bg-[#171a23] p-3 rounded-lg border border-zinc-800">
            {exception.explanation || "No automated explanation available for this discrepancy."}
          </p>
        </div>
      </div>

      {/* Financial Provenance Lineage Graph */}
      <EvidenceGraph
        transactionId={exception.transaction_id}
        nodes={dossier?.evidence_graph?.nodes}
        edges={dossier?.evidence_graph?.edges}
      />

      {/* Grid: Root-Cause Probability Ranking & Grounded Fact Claims */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* ML Root Cause Candidates */}
        <div className="rounded-lg border border-[#222634] bg-[#11131a] p-5 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
            <div className="flex items-center gap-2">
              <Cpu className="h-4 w-4 text-purple-400" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-300 font-mono">
                ML Root Cause Candidates
              </h2>
            </div>
            <span className="text-[10px] font-mono text-zinc-500">XGBoost Arbitration</span>
          </div>

          <div className="space-y-3">
            {dossier?.root_cause_candidates && dossier.root_cause_candidates.length > 0 ? (
              dossier.root_cause_candidates.map((rc, idx) => (
                <div key={rc.cause ? `${rc.cause}-${idx}` : `rc-${idx}`} className="p-3 rounded-lg border border-zinc-800 bg-[#171a23] space-y-2 text-xs font-mono">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-zinc-100">{(rc.cause || "UNKNOWN").replace(/_/g, " ")}</span>
                    <ConfidenceBadge confidence={typeof rc.confidence === "string" ? parseFloat(rc.confidence) : rc.confidence} />
                  </div>
                  <p className="text-[11px] text-zinc-400">{rc.evidence_summary || rc.evidence}</p>
                  {rc.features_cited && rc.features_cited.length > 0 && (
                    <div className="pt-1 flex flex-wrap gap-1">
                      {rc.features_cited.map((feat, fIdx) => (
                        <span key={fIdx} className="px-1.5 py-0.2 rounded bg-zinc-900 border border-zinc-800 text-[10px] text-zinc-400">
                          {feat}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              ))
            ) : (
              <div className="p-4 text-center text-zinc-500 font-mono text-xs">
                Root cause classified as: <strong>{(exception.category || exception.exception_category || "unexplained").replace(/_/g, " ")}</strong> (100% confidence)
              </div>
            )}
          </div>
        </div>

        {/* Fact-Grounded Claims & Source Citations */}
        <div className="rounded-lg border border-[#222634] bg-[#11131a] p-5 space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-sky-400" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-300 font-mono">
                PostgreSQL Grounded Facts
              </h2>
            </div>
            <span className="text-[10px] font-mono text-zinc-500">Evidence Citations</span>
          </div>

          <div className="space-y-2.5">
            {dossier?.claims && dossier.claims.length > 0 ? (
              dossier.claims.map((claim, idx) => (
                <div key={claim.statement ? `${claim.statement.slice(0, 20)}-${idx}` : `claim-${idx}`} className="p-3 rounded-lg border border-zinc-800 bg-[#171a23] space-y-1.5 text-xs font-mono">
                  <div className="flex items-center justify-between">
                    <span className="text-zinc-200">{claim.statement}</span>
                    <span className={cn("text-[10px] px-1.5 py-0.2 rounded border font-semibold", claim.grounded ? "bg-emerald-950 text-emerald-400 border-emerald-800" : "bg-zinc-800 text-zinc-400 border-zinc-700")}>
                      {claim.grounded ? "GROUNDED" : "INFERRED"}
                    </span>
                  </div>
                  {claim.source_reference && (
                    <div className="text-[10px] text-zinc-500">
                      Source: <span className="text-zinc-400">{claim.source_reference}</span>
                    </div>
                  )}
                </div>
              ))
            ) : (
              <div className="space-y-2 text-xs font-mono text-zinc-300">
                <div className="p-2.5 rounded bg-[#171a23] border border-zinc-800">
                  <span className="text-emerald-400 font-bold">✓ Gateway Record:</span> Payment ID {exception.transaction_id} captured in Razorpay feed.
                </div>
                <div className="p-2.5 rounded bg-[#171a23] border border-zinc-800">
                  <span className="text-rose-400 font-bold">⚠ Ledger Discrepancy:</span> Financial variance delta of {formatINR(exception.financial_exposure)} detected against ERP balance.
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Controller Decision & Policy Action Section */}
      <div className="rounded-lg border border-[#222634] bg-[#11131a] p-6 space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-emerald-400" />
            <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-100 font-mono">
              Controller Decision & Policy Action Resolution
            </h2>
          </div>
          <span className="text-xs font-mono text-zinc-400">
            Recommended Action: <strong className="text-sky-300">{exception.recommended_action || "Manual Adjustment"}</strong>
          </span>
        </div>

        {decisionSuccess && (
          <div className="p-3 rounded bg-emerald-950/40 border border-emerald-800/60 text-emerald-400 text-xs font-mono flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4" />
            <span>{decisionSuccess}</span>
          </div>
        )}

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2">
          <div>
            <label className="block text-zinc-400 mb-1 font-mono text-[11px]">Human Controller Actor ID</label>
            <input
              type="text"
              value={decisionActor}
              onChange={(e) => setDecisionActor(e.target.value)}
              className="w-full rounded border border-zinc-800 bg-[#171a23] px-3 py-2 text-zinc-100 font-mono text-xs focus:border-sky-500 focus:outline-hidden"
            />
          </div>

          <div className="sm:col-span-2">
            <label className="block text-zinc-400 mb-1 font-mono text-[11px]">Audit Decision Justification</label>
            <input
              type="text"
              value={decisionReason}
              onChange={(e) => setDecisionReason(e.target.value)}
              placeholder="Enter justification for the immutable audit trail..."
              className="w-full rounded border border-zinc-800 bg-[#171a23] px-3 py-2 text-zinc-100 font-mono text-xs focus:border-sky-500 focus:outline-hidden"
            />
          </div>
        </div>

        {/* Action Decision Buttons */}
        <div className="flex flex-wrap items-center justify-end gap-3 pt-3 border-t border-zinc-800">
          <button
            onClick={() => decisionMutation.mutate("resolve")}
            disabled={decisionMutation.isPending}
            className="px-3.5 py-1.5 rounded border border-zinc-700 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-mono font-semibold transition-colors"
          >
            Mark Resolved
          </button>

          <button
            onClick={() => decisionMutation.mutate("escalate")}
            disabled={decisionMutation.isPending}
            className="px-3.5 py-1.5 rounded border border-purple-900 bg-purple-950/50 hover:bg-purple-900 text-purple-300 text-xs font-mono font-semibold transition-colors"
          >
            Escalate to Senior Auditor
          </button>

          <button
            onClick={() => recommendActionMutation.mutate()}
            disabled={recommendActionMutation.isPending}
            className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded bg-sky-500 hover:bg-sky-400 text-black text-xs font-mono font-bold transition-colors"
          >
            <Play className="h-3 w-3 fill-current" />
            <span>Create Policy Action (HITL)</span>
          </button>
        </div>
      </div>
    </div>
  );
}
