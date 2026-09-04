"use client";

import React from "react";
import Link from "next/link";
import { formatINR, formatPercent } from "@/lib/utils/formatters";
import type { ReconciliationFunnel } from "@/types/controller";
import { CheckCircle2, Cpu, AlertTriangle, ArrowRight, ShieldCheck, Layers, GitBranch, ArrowDownRight } from "lucide-react";

interface FunnelChartProps {
  funnel?: ReconciliationFunnel | null;
  isLoading?: boolean;
  /** Current run ID — if provided, drill-down links will be scoped to this run */
  runId?: string;
}

export function FunnelChart({ funnel, isLoading, runId }: FunnelChartProps) {
  if (isLoading || !funnel) {
    return (
      <div
        className="p-6 rounded-sm border"
        style={{
          borderColor: "var(--border-subtle)",
          background: "var(--surface-1)",
        }}
      >
        <div className="h-4 w-52 skeleton mb-6" />
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} className="h-28 skeleton" />
          ))}
        </div>
      </div>
    );
  }

  const incomingRecords = funnel.incoming_records ?? 0;
  const detMatches = funnel.deterministic_matches ?? 0;
  const mlMatches = funnel.ml_recovered ?? funnel.ml_matches ?? 0;
  const manualReviews = funnel.manual_reviews ?? 0;
  const exceptions = funnel.unresolved ?? funnel.unmatched_exceptions ?? 0;
  const totalReconciled = detMatches + mlMatches;
  const totalEvaluated = incomingRecords > 0 ? incomingRecords : totalReconciled + exceptions;

  // Strict data truth percentages: exactly 0.0% when 0
  const deterministicPct = totalEvaluated > 0 ? (detMatches / totalEvaluated) * 100 : 0;
  const mlPct = totalEvaluated > 0 ? (mlMatches / totalEvaluated) * 100 : 0;
  const reviewPct = totalEvaluated > 0 ? (manualReviews / totalEvaluated) * 100 : 0;
  const exceptionPct = totalEvaluated > 0 ? (exceptions / totalEvaluated) * 100 : 0;
  const overallMatchPct = totalEvaluated > 0
    ? (totalReconciled / totalEvaluated) * 100
    : (funnel.final_match_rate ? (funnel.final_match_rate > 1 ? funnel.final_match_rate : funnel.final_match_rate * 100) : 0);

  return (
    <div
      className="rounded-sm border p-6 select-none"
      style={{
        borderColor: "var(--border-subtle)",
        background: "var(--surface-1)",
      }}
    >
      {/* Visual Header */}
      <div
        className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-5"
        style={{ borderBottom: "1px solid var(--border-subtle)" }}
      >
        <div>
          <div className="flex items-center gap-2">
            <span
              className="text-[10px] font-semibold uppercase tracking-[0.14em]"
              style={{ color: "var(--accent)" }}
            >
              Reconciliation Control Flow
            </span>
            <span style={{ color: "var(--text-tertiary)" }}>•</span>
            <span className="text-xs text-[#8e96a0]">
              Authoritative Multi-Source Settlement Arbitration
            </span>
          </div>
          <p className="text-xs text-[#545e6a] mt-0.5">
            Gateway Settlements ↔ Internal Ledger ↔ Core Bank Statement Lineage
          </p>
        </div>

        <div className="flex items-center gap-4 text-xs font-mono">
          <div>
            <span style={{ color: "var(--text-tertiary)" }}>Processed: </span>
            <strong className="text-[#eceae6] font-tabular">{totalEvaluated} records</strong>
          </div>
          {funnel.total_volume_inr && (
            <div>
              <span style={{ color: "var(--text-tertiary)" }}>Volume: </span>
              <strong className="text-[#eceae6] font-tabular">{formatINR(funnel.total_volume_inr)}</strong>
            </div>
          )}
        </div>
      </div>

      {/* Primary Flow Canvas: Engineered Directional Stages */}
      <div className="pt-6">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 relative">
          {/* Stage 01: Feed Ingest & Normalization */}
          <div
            className="p-4 rounded-xs border flex flex-col justify-between"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-2)",
            }}
          >
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] uppercase font-semibold tracking-wider text-[#545e6a]">
                Stage 01
              </span>
              <span className="text-[10px] font-mono text-[#8e96a0]">3 Sources</span>
            </div>
            <div className="text-xs font-semibold text-[#eceae6]">
              Multi-Source Ingestion
            </div>
            <Link
              href={runId ? `/reconciliation?run_id=${encodeURIComponent(runId)}` : "/reconciliation"}
              className="mt-2 font-mono text-2xl font-bold text-[#eceae6] font-tabular hover:text-[#c9a96e] transition-colors cursor-pointer block"
              title={`View ${totalEvaluated} feed records in reconciliation`}
            >
              {totalEvaluated}
            </Link>
            </div>
            <div className="mt-3 pt-2.5 border-t text-[11px] text-[#8e96a0]" style={{ borderColor: "var(--border-subtle)" }}>
              Normalized canonical records
            </div>
          </div>

          {/* Stage 02: Deterministic Parity (Gold primary control path) */}
          <div
            className="p-4 rounded-xs border flex flex-col justify-between"
            style={{
              borderColor: "var(--border-standard)",
              background: "var(--surface-2)",
              borderTop: "2px solid var(--accent)",
            }}
          >
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] uppercase font-semibold tracking-wider text-[#c9a96e]">
                  Stage 02
                </span>
                <span className="text-[10px] font-mono text-[#c9a96e] font-tabular">
                  {deterministicPct.toFixed(1)}%
                </span>
              </div>
            <div className="flex items-center gap-1.5 text-xs font-semibold text-[#eceae6]">
              <CheckCircle2 className="h-3.5 w-3.5 text-[#6ecba0]" />
              <span>Deterministic Rule Match</span>
            </div>
            <Link
              href={runId ? `/reconciliation?run_id=${encodeURIComponent(runId)}` : "/reconciliation"}
              className="mt-2 font-mono text-2xl font-bold text-[#6ecba0] font-tabular hover:opacity-75 transition-opacity cursor-pointer block"
              title={`${detMatches} deterministic matches — view in reconciliation`}
            >
              {detMatches}
            </Link>
            </div>
            <div className="mt-3 pt-2.5 border-t text-[11px] text-[#8e96a0]" style={{ borderColor: "var(--border-subtle)" }}>
              Strict UTR, reference &amp; monetary parity
            </div>
          </div>

          {/* Stage 03: ML Candidate Recovery (Analytical neutral slate, data-aware) */}
          <div
            className="p-4 rounded-xs border flex flex-col justify-between"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-2)",
            }}
          >
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] uppercase font-semibold tracking-wider text-[#9aa5b2]">
                  Stage 03
                </span>
                <span className="text-[10px] font-mono text-[#9aa5b2] font-tabular">
                  {mlPct.toFixed(1)}%
                </span>
              </div>
            <div className="flex items-center gap-1.5 text-xs font-semibold text-[#eceae6]">
              <Cpu className="h-3.5 w-3.5 text-[#9aa5b2]" />
              <span>ML Candidate Recovery</span>
            </div>
            {/* ML drill-down: backend exceptions endpoint has no ML-only filter.
                Link to exceptions for this run — user can see which were ML-recovered
                in the dossier evidence. */}
            <Link
              href={runId ? `/exceptions?run_id=${encodeURIComponent(runId)}` : "/exceptions"}
              className="mt-2 font-mono text-2xl font-bold text-[#eceae6] font-tabular hover:text-[#c9a96e] transition-colors cursor-pointer block"
              title={mlMatches > 0 ? `${mlMatches} ML-recovered — view exceptions for this run` : "ML recovery not invoked"}
            >
              {mlMatches}
            </Link>
            </div>
            <div className="mt-3 pt-2.5 border-t text-[11px] text-[#8e96a0]" style={{ borderColor: "var(--border-subtle)" }}>
              {mlMatches > 0
                ? "Fuzzy metadata & temporal candidate scoring"
                : "Deterministic rule coverage satisfied"}
            </div>
          </div>

          {/* Stage 04: Final Resolution Partition (Reconciled vs Exceptions) */}
          <div
            className="p-4 rounded-xs border flex flex-col justify-between"
            style={{
              borderColor: exceptions > 0 ? "var(--variance-border)" : "var(--matched-border)",
              background: "var(--surface-2)",
              borderTop: exceptions > 0 ? "2px solid var(--variance)" : "2px solid var(--matched)",
            }}
          >
            <div>
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] uppercase font-semibold tracking-wider text-[#8e96a0]">
                  Resolution
                </span>
                <span
                  className="text-[10px] font-mono font-bold"
                  style={{ color: exceptions > 0 ? "var(--variance-text)" : "var(--matched-text)" }}
                >
                  {exceptions > 0 ? `${exceptions} Exceptions` : "100% Reconciled"}
                </span>
              </div>
              <div className="text-xs font-semibold text-[#eceae6] flex items-center justify-between">
                <span>Reconciled / Open</span>
                <span className="font-mono text-xs font-tabular text-[#6ecba0]">
                  {overallMatchPct.toFixed(1)}%
                </span>
              </div>
              <div className="mt-2 flex items-baseline justify-between font-mono">
                <Link
                  href={runId ? `/reconciliation?run_id=${encodeURIComponent(runId)}` : "/reconciliation"}
                  className="text-2xl font-bold text-[#6ecba0] font-tabular hover:opacity-75 transition-opacity cursor-pointer"
                  title={`${totalReconciled} reconciled — view in reconciliation`}
                >
                  {totalReconciled}
                </Link>
                {exceptions > 0 ? (
                  <Link
                    href={runId
                      ? `/exceptions?status=open&run_id=${encodeURIComponent(runId)}`
                      : "/exceptions?status=open"}
                    className="text-sm font-semibold text-[#e07070] font-tabular hover:opacity-75 transition-opacity cursor-pointer"
                    title={`${exceptions} open exceptions — view exception queue`}
                  >
                    +{exceptions} req. review
                  </Link>
                ) : (
                  <span className="text-sm font-semibold text-[#8e96a0] font-tabular">0 discrepancies</span>
                )}
              </div>
            </div>
            <div className="mt-3 pt-2.5 border-t text-[11px] text-[#8e96a0]" style={{ borderColor: "var(--border-subtle)" }}>
              {exceptions > 0
                ? "Discrepant pairs routed to forensic dossiers"
                : "Parity confirmed across all 3 records"}
            </div>
          </div>
        </div>

        {/* Proportional Partition Rail (Strict adherence to numerical truth) */}
        <div className="mt-6 pt-5" style={{ borderTop: "1px solid var(--border-subtle)" }}>
          <div className="flex items-center justify-between text-xs mb-2">
            <span style={{ color: "var(--text-tertiary)" }} className="text-[11px] uppercase tracking-wider font-semibold">
              Volume Distribution
            </span>
            <div className="flex items-center gap-3 font-mono text-xs">
              <span className="text-[#6ecba0] font-medium font-tabular">
                {totalReconciled} Reconciled ({overallMatchPct.toFixed(1)}%)
              </span>
              <span style={{ color: "var(--text-tertiary)" }}>•</span>
              <span
                className="font-medium font-tabular"
                style={{ color: exceptions > 0 ? "var(--variance-text)" : "var(--text-secondary)" }}
              >
                {exceptions} Exceptions ({exceptionPct.toFixed(1)}%)
              </span>
            </div>
          </div>

          {/* Exact Segment Bar: 0% is strictly 0% */}
          <div
            className="h-2 w-full rounded-xs overflow-hidden flex"
            style={{ background: "var(--surface-3)" }}
          >
            {deterministicPct > 0 && (
              <div
                style={{
                  width: `${deterministicPct}%`,
                  background: "var(--matched)",
                }}
                title={`Deterministic: ${detMatches} (${deterministicPct.toFixed(1)}%)`}
              />
            )}
            {mlPct > 0 && (
              <div
                style={{
                  width: `${mlPct}%`,
                  background: "var(--ml)",
                }}
                title={`ML Recovered: ${mlMatches} (${mlPct.toFixed(1)}%)`}
              />
            )}
            {reviewPct > 0 && (
              <div
                style={{
                  width: `${reviewPct}%`,
                  background: "var(--pending)",
                }}
                title={`Under Review: ${manualReviews} (${reviewPct.toFixed(1)}%)`}
              />
            )}
            {exceptionPct > 0 && (
              <div
                style={{
                  width: `${exceptionPct}%`,
                  background: "var(--variance)",
                }}
                title={`Exceptions: ${exceptions} (${exceptionPct.toFixed(1)}%)`}
              />
            )}
          </div>

          {/* Footnote telemetry */}
          <div
            className="flex items-center justify-between text-[11px] font-mono mt-3"
            style={{ color: "var(--text-secondary)" }}
          >
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-1.5">
                <span className="status-dot" style={{ background: "var(--matched)" }} />
                <span>Deterministic: {detMatches}</span>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="status-dot" style={{ background: "var(--ml)" }} />
                <span>ML Recovered: {mlMatches}</span>
              </div>
              {manualReviews > 0 && (
                <div className="flex items-center gap-1.5">
                  <span className="status-dot" style={{ background: "var(--pending)" }} />
                  <span>Pending Review: {manualReviews}</span>
                </div>
              )}
              <div className="flex items-center gap-1.5">
                <span className="status-dot" style={{ background: "var(--variance)" }} />
                <span>Exceptions: {exceptions}</span>
              </div>
            </div>

            {funnel.reconciled_volume_inr && (
              <div className="text-right">
                <span style={{ color: "var(--text-tertiary)" }}>Reconciled Value: </span>
                <strong className="text-[#eceae6] font-tabular">{formatINR(funnel.reconciled_volume_inr)}</strong>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
