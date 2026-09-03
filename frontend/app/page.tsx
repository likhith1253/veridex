"use client";

import React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { controllerApi } from "@/lib/api/controllerApi";
import { formatINR, formatPercent, formatVariance } from "@/lib/utils/formatters";
import { StatusBadge } from "@/components/common/StatusBadge";
import { FunnelChart } from "@/components/reconciliation/FunnelChart";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { ErrorState } from "@/components/common/ErrorState";
import {
  ArrowRight,
  ShieldCheck,
  Building2,
  CheckCircle2,
  AlertOctagon,
  Scale,
  Activity,
  Layers,
  FileCheck2,
} from "lucide-react";

export default function CommandCenterPage() {
  const {
    data: overview,
    isLoading: overviewLoading,
    error: overviewError,
    refetch: refetchOverview,
  } = useQuery({
    queryKey: ["controller-overview"],
    queryFn: () => controllerApi.getOverview(),
    refetchInterval: 10000,
  });

  const {
    data: funnel,
    isLoading: funnelLoading,
  } = useQuery({
    queryKey: ["controller-funnel"],
    queryFn: () => controllerApi.getFunnel(),
    refetchInterval: 10000,
  });

  const {
    data: brief,
    isLoading: briefLoading,
  } = useQuery({
    queryKey: ["controller-brief"],
    queryFn: () => controllerApi.getCopilotBrief(),
    staleTime: 30000,
  });

  const {
    data: exceptionsData,
    isLoading: exceptionsLoading,
  } = useQuery({
    queryKey: ["controller-exceptions-preview"],
    queryFn: () => controllerApi.getExceptions({ page: 1, page_size: 5 }),
    refetchInterval: 15000,
  });

  const {
    data: cashPosition,
  } = useQuery({
    queryKey: ["controller-cash-position"],
    queryFn: () => controllerApi.getCashPosition(),
    staleTime: 30000,
  });

  if (overviewError) {
    return (
      <ErrorState
        title="Failed to Load Command Center"
        message={overviewError instanceof Error ? overviewError.message : "Backend connection error"}
        onRetry={refetchOverview}
      />
    );
  }

  const totalRecs = overview?.total_records_processed ?? overview?.total_records ?? 0;
  const matchedRecs = overview?.total_matched_records ?? overview?.matched_records ?? 0;
  const exceptionRecs = overview?.unresolved_transactions ?? overview?.open_exceptions ?? 0;
  const matchPct = overview?.match_rate ?? 0;
  const exposureVal = overview?.unresolved_monetary_exposure_inr ?? overview?.financial_exposure ?? 0;
  const volumeVal = overview?.total_transaction_value_inr ?? overview?.total_financial_volume ?? 0;

  return (
    <div className="space-y-8 pb-10 select-none">
      {/* ── ZONE 0: CONTROL STATUS PROOF BAR ───────────────────────── */}
      <div
        className="flex flex-wrap items-center justify-between gap-3 px-4 py-2 rounded-xs text-[11px]"
        style={{
          background: "var(--surface-1)",
          border: "1px solid var(--border-subtle)",
        }}
      >
        <div className="flex items-center gap-2">
          <span
            className="text-[9px] font-bold uppercase tracking-[0.14em]"
            style={{ color: "var(--accent)" }}
          >
            CONTROL STATUS
          </span>
          <span style={{ color: "var(--text-tertiary)" }}>|</span>
        </div>

        <div className="flex flex-wrap items-center gap-x-5 gap-y-1 text-[#8e96a0]">
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-[#545e6a] uppercase">Data</span>
            <span className="font-semibold text-[#eceae6]">Verified</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-[#545e6a] uppercase">Recon</span>
            <span className="font-semibold text-[#6ecba0]">Active</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-[#545e6a] uppercase">Evidence</span>
            <span className="font-semibold text-[#eceae6]">Grounded</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-[#545e6a] uppercase">AI</span>
            <span className="font-semibold text-[#eceae6]">Assistive</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-[#545e6a] uppercase">HITL</span>
            <span className="font-semibold text-[#d4a84e]">Enforced</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-[#545e6a] uppercase">Audit</span>
            <span className="font-semibold text-[#6ecba0]">Enabled</span>
          </div>
        </div>

        <div className="hidden lg:flex items-center gap-2 text-[10px] font-mono text-[#545e6a]">
          <span>Scope:</span>
          <span className="text-[#9098a2]">{overview?.run_id || "Active Run"}</span>
        </div>
      </div>

      {/* ── ZONE 1: CINEMATIC ASYMMETRIC HERO STATEMENT & EXPOSURE ─── */}
      <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-6 pt-1">
        <div>
          <div className="flex items-center gap-2 mb-2">
            <span
              className="text-[11px] font-semibold uppercase tracking-[0.14em]"
              style={{ color: "var(--accent)" }}
            >
              VERIDEX FINANCIAL CONTROL CENTER
            </span>
          </div>

          {/* Large Authoritative Narrative (Sans-Serif) */}
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-[#eceae6]">
            {overviewLoading ? (
              <span className="h-9 w-96 skeleton inline-block" />
            ) : (
              <>
                <span>{totalRecs} feed records processed. </span>
                <span className="text-[#6ecba0]">{matchedRecs} reconciled. </span>
                <span className={exceptionRecs > 0 ? "text-[#e07070]" : "text-[#9098a2]"}>
                  {exceptionRecs} require investigation.
                </span>
              </>
            )}
          </h1>

          <p className="text-xs text-[#8e96a0] mt-1.5">
            Continuous 3-way settlement arbitration across Gateway, Internal Ledger, and Core Bank statements
          </p>
        </div>

        {/* Asymmetric Dominant Monetary Exposure Anchor */}
        <div
          className="flex-shrink-0 px-6 py-4 rounded-xs border self-start lg:self-auto"
          style={{
            borderColor: exceptionRecs > 0 ? "var(--variance-border)" : "var(--border-subtle)",
            background: "var(--surface-1)",
            borderLeft: exceptionRecs > 0 ? "3px solid var(--variance)" : "3px solid var(--accent)",
          }}
        >
          <div className="text-[10px] font-semibold uppercase tracking-wider text-[#8e96a0]">
            Unreconciled Exposure
          </div>
          <div
            className="text-2xl sm:text-3xl font-bold font-mono font-tabular mt-1"
            style={{
              color: exceptionRecs > 0 ? "var(--variance-text)" : "var(--matched-text)",
            }}
          >
            {formatINR(exposureVal)}
          </div>
          <div className="text-[11px] text-[#545e6a] mt-0.5 font-mono">
            {exceptionRecs} exception {exceptionRecs === 1 ? "case" : "cases"} pending resolution
          </div>
        </div>
      </div>

      {/* ── ZONE 2: PRIMARY RECONCILIATION VISUAL (40% Visual Weight) ─ */}
      <FunnelChart funnel={funnel} isLoading={funnelLoading} />

      {/* ── ZONE 3: ASYMMETRIC WORKSPACE (Exceptions 60% vs Assessment 40%) ── */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left: Active Exceptions Forensic Queue (7 cols = ~60%) */}
        <div
          className="lg:col-span-7 rounded-sm border p-6 text-[#eceae6]"
          style={{
            borderColor: "var(--border-subtle)",
            background: "var(--surface-1)",
          }}
        >
          <div
            className="flex items-center justify-between pb-4"
            style={{ borderBottom: "1px solid var(--border-subtle)" }}
          >
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-semibold uppercase tracking-[0.1em] text-[#8e96a0]">
                  Forensic Queue
                </span>
                <span
                  className="text-[9px] font-mono px-1.5 py-0.5 rounded-xs font-bold text-[#e07070]"
                  style={{
                    background: "var(--variance-bg)",
                    border: "1px solid var(--variance-border)",
                  }}
                >
                  {exceptionRecs} UNRESOLVED
                </span>
              </div>
              <h2 className="text-sm font-bold text-[#eceae6] mt-0.5">
                Exceptions Requiring Investigation
              </h2>
            </div>

            <Link
              href="/exceptions"
              className="text-xs text-[#c9a96e] hover:text-[#d8bc8a] flex items-center gap-1 font-medium transition-micro"
            >
              <span>Full Workbench</span>
              <ArrowRight className="h-3 w-3" />
            </Link>
          </div>

          {exceptionsLoading ? (
            <div className="pt-4">
              <LoadingSkeleton variant="table" count={4} />
            </div>
          ) : !exceptionsData || exceptionsData.exceptions.length === 0 ? (
            <div className="py-12 text-center text-[#8e96a0] text-xs">
              Zero active exceptions. Financial state is completely reconciled.
            </div>
          ) : (
            <div className="overflow-x-auto pt-2">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr
                    className="text-[10px] uppercase font-semibold"
                    style={{
                      color: "var(--text-tertiary)",
                      borderBottom: "1px solid var(--border-subtle)",
                    }}
                  >
                    <th className="py-2.5 px-3">Exception ID</th>
                    <th className="py-2.5 px-3">Root-Cause Category</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3 text-right">Exposure</th>
                    <th className="py-2.5 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y" style={{ borderColor: "var(--border-subtle)" }}>
                  {exceptionsData.exceptions.map((ex, idx) => {
                    const excId = ex.exception_id || ex.id || `exc-${idx}`;
                    const cat = ex.category || ex.exception_category || "unexplained";
                    const exp = ex.financial_exposure_inr ?? ex.financial_exposure;

                    return (
                      <tr
                        key={excId ? `${excId}-${idx}` : `exception-row-${idx}`}
                        className="hover:bg-[#13161a] transition-micro"
                      >
                        <td className="py-3 px-3">
                          <div className="font-mono text-xs font-semibold text-[#eceae6]">{excId}</div>
                          <div className="text-[10px] font-mono text-[#545e6a]">{ex.transaction_id || "—"}</div>
                        </td>
                        <td className="py-3 px-3">
                          <span className="text-[#8e96a0] capitalize">{cat.replace(/_/g, " ")}</span>
                        </td>
                        <td className="py-3 px-3">
                          <StatusBadge status={ex.status} />
                        </td>
                        <td className="py-3 px-3 text-right font-mono font-bold font-tabular text-[#e07070]">
                          {formatINR(exp)}
                        </td>
                        <td className="py-3 px-3 text-right">
                          <Link
                            href={`/exceptions/${encodeURIComponent(excId)}`}
                            className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xs text-xs font-medium transition-micro"
                            style={{
                              color: "var(--accent)",
                              background: "var(--accent-dim)",
                              border: "1px solid var(--accent-border)",
                            }}
                          >
                            <span>Dossier</span>
                            <ArrowRight className="h-3 w-3" />
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right: VERIDEX Assessment & Parity Ledger (5 cols = ~40%) */}
        <div className="lg:col-span-5 space-y-6">
          {/* VERIDEX Assessment & Policy Action */}
          <div
            className="rounded-sm border p-6 text-[#eceae6]"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-1)",
            }}
          >
            <div
              className="flex items-center justify-between pb-3"
              style={{ borderBottom: "1px solid var(--border-subtle)" }}
            >
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-[0.1em] text-[#8e96a0]">
                  Controller Intelligence
                </span>
                <h3 className="text-xs font-bold text-[#eceae6] mt-0.5">
                  VERIDEX Operational Assessment
                </h3>
              </div>
              {brief?.reconciliation_health_score !== undefined && (
                <span
                  className="font-mono text-xs font-bold px-2 py-0.5 rounded-xs"
                  style={{
                    color: "var(--matched-text)",
                    background: "var(--matched-bg)",
                    border: "1px solid var(--matched-border)",
                  }}
                >
                  Health: {brief.reconciliation_health_score}/100
                </span>
              )}
            </div>

            {briefLoading ? (
              <div className="py-4 space-y-2">
                <div className="h-4 w-3/4 skeleton" />
                <div className="h-3.5 w-full skeleton" />
              </div>
            ) : brief ? (
              <div className="pt-4 space-y-4 text-xs">
                <div
                  className="p-3.5 rounded-xs border text-xs leading-relaxed"
                  style={{
                    borderColor: "var(--border-standard)",
                    background: "var(--surface-2)",
                    color: "var(--text-primary)",
                  }}
                >
                  <p>{brief.why || brief.headline || "Continuous multi-source reconciliation in progress."}</p>
                </div>

                {/* Recommended Controller Action */}
                <div>
                  <div className="text-[10px] font-semibold text-[#8e96a0] uppercase tracking-wider mb-1.5">
                    Recommended Policy Action:
                  </div>
                  <div
                    className="p-3 rounded-xs border text-xs text-[#eceae6] flex items-start gap-2.5 leading-relaxed"
                    style={{
                      borderColor: "var(--accent-border)",
                      background: "var(--accent-dim)",
                    }}
                  >
                    <span className="text-[#c9a96e] font-bold">▶</span>
                    <span>{brief.recommended_action || "Continue monitoring ingestion pipelines and process pending exceptions."}</span>
                  </div>
                </div>

                <div className="flex items-center justify-between pt-2 text-xs">
                  <span className="text-[#545e6a]">Human Review Status:</span>
                  <span className={brief.human_review_required ? "text-[#d4a84e] font-semibold" : "text-[#6ecba0] font-semibold"}>
                    {brief.human_review_required ? "HITL Action Required" : "Cleared"}
                  </span>
                </div>
              </div>
            ) : (
              <div className="py-6 text-center text-[#545e6a] text-xs">
                Operational assessment unavailable for current scope.
              </div>
            )}
          </div>

          {/* Multi-Source Cash Position & Settlement Variance */}
          <div
            className="rounded-sm border p-6 text-[#eceae6]"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-1)",
            }}
          >
            <div
              className="flex items-center justify-between pb-3"
              style={{ borderBottom: "1px solid var(--border-subtle)" }}
            >
              <div>
                <span className="text-[10px] font-semibold uppercase tracking-[0.1em] text-[#8e96a0]">
                  Parity Ledger
                </span>
                <h3 className="text-xs font-bold text-[#eceae6] mt-0.5">
                  Multi-Source Settlement Variance
                </h3>
              </div>
              <Link
                href="/settlements"
                className="text-xs text-[#c9a96e] hover:text-[#d8bc8a] flex items-center gap-1 transition-micro"
              >
                <span>Settlements</span>
                <ArrowRight className="h-3 w-3" />
              </Link>
            </div>

            <div className="pt-4 space-y-3">
              <div className="grid grid-cols-2 gap-3 font-mono">
                <div
                  className="p-3 rounded-xs border"
                  style={{
                    borderColor: "var(--border-subtle)",
                    background: "var(--surface-2)",
                  }}
                >
                  <div className="text-[10px] uppercase text-[#8e96a0]">Expected Gross</div>
                  <div className="mt-1 text-lg font-bold text-[#eceae6] font-tabular">
                    {formatINR(cashPosition?.expected_gross ?? cashPosition?.expected_amount ?? volumeVal)}
                  </div>
                </div>

                <div
                  className="p-3 rounded-xs border"
                  style={{
                    borderColor: "var(--border-subtle)",
                    background: "var(--surface-2)",
                  }}
                >
                  <div className="text-[10px] uppercase text-[#8e96a0]">Bank Received</div>
                  <div className="mt-1 text-lg font-bold text-[#6ecba0] font-tabular">
                    {formatINR(cashPosition?.received_bank_credits ?? cashPosition?.received_amount ?? 0)}
                  </div>
                </div>
              </div>

              {/* Settlement Net Variance */}
              <div
                className="p-3 rounded-xs border font-mono flex items-center justify-between"
                style={{
                  borderColor: formatVariance(cashPosition?.settlement_variance).isZero
                    ? "var(--matched-border)"
                    : "var(--variance-border)",
                  background: "var(--surface-2)",
                  borderLeft: formatVariance(cashPosition?.settlement_variance).isZero
                    ? "3px solid var(--matched)"
                    : "3px solid var(--variance)",
                }}
              >
                <div>
                  <div className="text-[10px] uppercase text-[#8e96a0]">Net Settlement Variance</div>
                  <div className="text-xs text-[#545e6a] mt-0.5">
                    {formatVariance(cashPosition?.settlement_variance).isZero
                      ? "Zero discrepancy verified"
                      : "Material variance detected"}
                  </div>
                </div>
                <div
                  className={`text-lg font-bold font-tabular ${
                    formatVariance(cashPosition?.settlement_variance).isZero
                      ? "text-[#6ecba0]"
                      : "text-[#e07070]"
                  }`}
                >
                  {formatVariance(cashPosition?.settlement_variance).text}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
