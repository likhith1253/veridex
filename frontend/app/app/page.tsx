"use client";

import React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { controllerApi } from "@/lib/api/controllerApi";
import { formatINR, formatPercent, formatVariance } from "@/lib/utils/formatters";
import { MetricCard } from "@/components/common/MetricCard";
import { StatusBadge } from "@/components/common/StatusBadge";
import { FunnelChart } from "@/components/reconciliation/FunnelChart";
import { TechnicalReference } from "@/components/common/TechnicalReference";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { ErrorState } from "@/components/common/ErrorState";
import {
  DollarSign,
  GitMerge,
  AlertOctagon,
  ShieldAlert,
  ArrowRight,
  ShieldCheck,
  CheckCircle2,
  TrendingUp,
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

  const { data: cashPosition } = useQuery({
    queryKey: ["controller-cash-position"],
    queryFn: () => controllerApi.getCashPosition(),
    staleTime: 30000,
  });

  if (overviewError) {
    return (
      <ErrorState
        title="Failed to Load Command Center Data"
        message={overviewError instanceof Error ? overviewError.message : "Backend unreachable"}
        onRetry={refetchOverview}
      />
    );
  }

  const totalRecs = overview?.total_records_processed ?? overview?.total_records ?? 0;
  const matchedRecs = overview?.total_matched_records ?? overview?.matched_records ?? 0;
  const exceptionRecs = overview?.unresolved_transactions ?? overview?.open_exceptions ?? 0;
  const exposureVal = overview?.unresolved_monetary_exposure_inr ?? overview?.financial_exposure ?? 0;
  const volumeVal = overview?.total_transaction_value_inr ?? overview?.total_financial_volume ?? 0;
  const runId = overview?.run_id;

  const reconLink = runId ? `/reconciliation?run_id=${encodeURIComponent(runId)}` : "/reconciliation";
  const exceptionsLink = runId
    ? `/exceptions?status=open&run_id=${encodeURIComponent(runId)}`
    : "/exceptions?status=open";

  return (
    <div className="space-y-8 pb-16 select-none">
      {/* ── ZONE 0: CONTROL STATUS PROOF BAR ───────────────────────── */}
      <div
        className="flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 rounded-xs text-[11px] border"
        style={{
          borderColor: "var(--border-subtle)",
          background: "var(--surface-1)",
        }}
      >
        <div className="flex items-center gap-2">
          <span
            className="text-[10px] font-bold uppercase tracking-[0.14em]"
            style={{ color: "var(--accent)" }}
          >
            Control Status
          </span>
          <span style={{ color: "var(--text-tertiary)" }}>|</span>
        </div>

        <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-[#8e96a0]">
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] uppercase font-semibold text-[#545e6a]">Data</span>
            <span className="font-bold text-[#eceae6]">Verified</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] uppercase font-semibold text-[#545e6a]">Recon</span>
            <span className="font-bold text-[#6ecba0]">Active</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] uppercase font-semibold text-[#545e6a]">Evidence</span>
            <span className="font-bold text-[#eceae6]">Grounded</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] uppercase font-semibold text-[#545e6a]">AI</span>
            <span className="font-bold text-[#eceae6]">Assistive</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] uppercase font-semibold text-[#545e6a]">HITL</span>
            <span className="font-bold text-[#d4a84e]">Enforced</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] uppercase font-semibold text-[#545e6a]">Audit</span>
            <span className="font-bold text-[#6ecba0]">Enabled</span>
          </div>
        </div>

        {runId && (
          <div className="hidden lg:flex items-center gap-2 text-[10px] font-mono text-[#8e96a0]">
            <span>Scope:</span>
            <TechnicalReference id={runId} maxVisible={20} />
          </div>
        )}
      </div>

      {/* ── ZONE 1: TOP BANNER: OPERATIONAL CONTEXT ─────────────────── */}
      <div
        className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-5"
        style={{ borderBottom: "1px solid var(--border-subtle)" }}
      >
        <div>
          <h1 className="text-xl font-bold font-mono text-[#eceae6] flex items-center gap-2.5 tracking-tight">
            Finance Operations Command Center
            <span
              className="text-[10px] px-2 py-0.5 rounded-xs font-bold"
              style={{
                color: "var(--matched-text)",
                background: "var(--matched-bg)",
                border: "1px solid var(--matched-border)",
              }}
            >
              LIVE
            </span>
          </h1>
          <p className="text-xs text-[#8e96a0] mt-1 italic">
            Continuous real-time multi-source reconciliation across Payment Gateway, Internal Ledger, and Core Banking.
          </p>
        </div>

        {runId && (
          <div className="flex items-center gap-2 text-xs font-mono text-[#8e96a0]">
            <span>Scoped Run:</span>
            <TechnicalReference id={runId} maxVisible={24} />
          </div>
        )}
      </div>

      {/* ── ZONE 2: FOUR PRIMARY KPI MATRIX BLOCKS ─────────────────── */}
      {overviewLoading ? (
        <LoadingSkeleton variant="card" count={4} />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Link href={reconLink} className="block hover:opacity-90 transition-opacity">
            <MetricCard
              title="Total Financial Volume"
              value={formatINR(volumeVal)}
              subtitle={`${totalRecs} feed records in scope`}
              icon={<DollarSign className="h-4 w-4 text-[#c9a96e]" />}
              statusBorder="indigo"
            />
          </Link>

          <Link href={reconLink} className="block hover:opacity-90 transition-opacity">
            <MetricCard
              title="Reconciliation Rate"
              value={formatPercent(overview?.match_rate)}
              subtitle={`${matchedRecs} of ${totalRecs} matched`}
              delta={overview?.match_rate && overview.match_rate >= 0.9 ? "Optimal" : "Review"}
              deltaType={overview?.match_rate && overview.match_rate >= 0.9 ? "positive" : "neutral"}
              icon={<GitMerge className="h-4 w-4 text-[#6ecba0]" />}
              statusBorder="emerald"
            />
          </Link>

          <Link href={exceptionsLink} className="block hover:opacity-90 transition-opacity">
            <MetricCard
              title="Open Exceptions"
              value={exceptionRecs.toString()}
              subtitle={`${exceptionRecs} unresolved exceptions`}
              delta={exceptionRecs > 0 ? "Action Required" : "Zero Variance"}
              deltaType={exceptionRecs > 0 ? "negative" : "positive"}
              icon={<AlertOctagon className="h-4 w-4 text-[#e07070]" />}
              statusBorder="rose"
            />
          </Link>

          <Link href={exceptionsLink} className="block hover:opacity-90 transition-opacity">
            <MetricCard
              title="Unreconciled Exposure"
              value={formatINR(exposureVal)}
              subtitle={`Expected Cost: ${formatINR(overview?.manual_review_exposure_inr ?? overview?.expected_cost)}`}
              delta={`${formatPercent(overview?.unreconciled_exposure_pct)} volume`}
              deltaType={
                overview?.unreconciled_exposure_pct && overview.unreconciled_exposure_pct > 0.05
                  ? "negative"
                  : "neutral"
              }
              icon={<ShieldAlert className="h-4 w-4 text-[#d4a84e]" />}
              statusBorder="amber"
            />
          </Link>
        </div>
      )}

      {/* ── ZONE 3: 3-WAY RECONCILIATION PIPELINE VISUALIZER ───────── */}
      <div className="pt-1">
        <FunnelChart funnel={funnel} isLoading={funnelLoading} runId={runId ?? undefined} />
      </div>

      {/* ── ZONE 4: GRID: EXECUTIVE ASSESSMENT & LIVE CASH POSITION ── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Executive Assessment */}
        <div
          className="lg:col-span-2 rounded-sm border p-6"
          style={{
            borderColor: "var(--border-subtle)",
            background: "var(--surface-1)",
          }}
        >
          <div
            className="flex items-center justify-between pb-3.5"
            style={{ borderBottom: "1px solid var(--border-subtle)" }}
          >
            <div className="flex items-center gap-2">
              <span
                className="text-[10px] font-bold uppercase tracking-wider font-mono"
                style={{ color: "var(--accent)" }}
              >
                VERIDEX Operational Assessment
              </span>
            </div>
            {brief?.reconciliation_health_score !== undefined && (
              <span
                className="font-mono text-xs font-bold px-2.5 py-0.5 rounded-xs"
                style={{
                  color: "var(--matched-text)",
                  background: "var(--matched-bg)",
                  border: "1px solid var(--matched-border)",
                }}
              >
                Health Score: {brief.reconciliation_health_score}/100
              </span>
            )}
          </div>

          {briefLoading ? (
            <div className="py-5 space-y-2">
              <div className="h-4 w-3/4 rounded-xs skeleton" />
              <div className="h-3 w-full rounded-xs skeleton" />
            </div>
          ) : brief ? (
            <div className="py-4 space-y-4 font-mono text-xs">
              <div
                className="p-3.5 rounded-xs border text-[#eceae6] leading-relaxed font-semibold"
                style={{
                  borderColor: "var(--border-subtle)",
                  background: "var(--surface-2)",
                }}
              >
                <p>{brief.why || brief.headline || "Continuous multi-source reconciliation in progress."}</p>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-1 text-center">
                <div
                  className="p-3 rounded-xs border"
                  style={{
                    borderColor: "var(--border-subtle)",
                    background: "var(--surface-2)",
                  }}
                >
                  <div className="text-[10px] text-[#8e96a0] uppercase font-bold">Match Rate</div>
                  <div className="text-sm font-bold text-[#6ecba0] mt-0.5 font-tabular">
                    {formatPercent(brief.reconciliation_match_rate_percent ?? brief.key_metrics?.match_rate_pct)}
                  </div>
                </div>

                <div
                  className="p-3 rounded-xs border"
                  style={{
                    borderColor: "var(--border-subtle)",
                    background: "var(--surface-2)",
                  }}
                >
                  <div className="text-[10px] text-[#8e96a0] uppercase font-bold">Money at Risk</div>
                  <div className="text-sm font-bold text-[#e07070] mt-0.5 font-tabular">
                    {formatINR(brief.money_at_risk_inr ?? brief.key_metrics?.financial_exposure_inr)}
                  </div>
                </div>

                <div
                  className="p-3 rounded-xs border"
                  style={{
                    borderColor: "var(--border-subtle)",
                    background: "var(--surface-2)",
                  }}
                >
                  <div className="text-[10px] text-[#8e96a0] uppercase font-bold">Source Health</div>
                  <div className="text-sm font-bold text-[#eceae6] mt-0.5">
                    {brief.source_health || "HEALTHY"}
                  </div>
                </div>

                <div
                  className="p-3 rounded-xs border"
                  style={{
                    borderColor: "var(--border-subtle)",
                    background: "var(--surface-2)",
                  }}
                >
                  <div className="text-[10px] text-[#8e96a0] uppercase font-bold">Review Required</div>
                  <div
                    className={`text-sm font-bold mt-0.5 ${
                      brief.human_review_required ? "text-[#d4a84e]" : "text-[#6ecba0]"
                    }`}
                  >
                    {brief.human_review_required ? "YES (HITL)" : "NO"}
                  </div>
                </div>
              </div>

              {/* Critical Findings & Recommended Action */}
              <div
                className="space-y-2 pt-2"
                style={{ borderTop: "1px solid var(--border-subtle)" }}
              >
                <div className="text-[11px] font-bold text-[#8e96a0] uppercase tracking-wider">
                  Recommended Controller Action:
                </div>
                <div
                  className="text-[#eceae6] text-xs p-3 rounded-xs border flex items-start gap-2.5"
                  style={{
                    borderColor: "var(--accent-border)",
                    background: "var(--accent-dim)",
                  }}
                >
                  <span className="text-[#c9a96e] font-bold">▶</span>
                  <span className="font-sans font-medium">
                    {brief.recommended_action ||
                      "Continue monitoring ingestion pipelines and process pending exceptions."}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <div className="py-6 text-center text-[#8e96a0] font-mono text-xs">
              Executive brief unavailable for this scope.
            </div>
          )}
        </div>

        {/* Live Multi-Source Cash Position */}
        <div
          className="rounded-sm border p-6"
          style={{
            borderColor: "var(--border-subtle)",
            background: "var(--surface-1)",
          }}
        >
          <div
            className="flex items-center justify-between pb-3.5"
            style={{ borderBottom: "1px solid var(--border-subtle)" }}
          >
            <h2 className="text-xs font-bold uppercase tracking-wider text-[#eceae6] font-mono">
              Live Cash Position
            </h2>
            <Link
              href="/settlements"
              className="text-[11px] text-[#c9a96e] hover:text-[#e4caa0] font-mono font-semibold"
            >
              Full Breakdown →
            </Link>
          </div>

          <div className="pt-4 space-y-3 font-mono text-xs">
            <div className="flex justify-between text-[#8e96a0]">
              <span>Expected Gross:</span>
              <span className="text-[#eceae6] font-bold font-tabular">
                {formatINR(cashPosition?.expected_gross ?? cashPosition?.expected_amount ?? volumeVal)}
              </span>
            </div>

            <div className="flex justify-between text-[#8e96a0]">
              <span>Deducted Fees:</span>
              <span className="text-[#e07070] font-tabular">
                {formatINR(cashPosition?.total_deducted_fees ?? cashPosition?.deducted_fees)}
              </span>
            </div>

            <div className="flex justify-between text-[#8e96a0]">
              <span>Deducted Taxes (GST):</span>
              <span className="text-[#d4a84e] font-tabular">
                {formatINR(cashPosition?.total_deducted_taxes ?? cashPosition?.deducted_taxes)}
              </span>
            </div>

            <div
              className="pt-2 flex justify-between text-[#eceae6] font-semibold"
              style={{ borderTop: "1px solid var(--border-subtle)" }}
            >
              <span>Expected Net:</span>
              <span className="text-[#eceae6] font-bold font-tabular">
                {formatINR(cashPosition?.expected_net_settlement)}
              </span>
            </div>

            <div className="flex justify-between text-[#eceae6] font-semibold">
              <span>Received Bank Credits:</span>
              <span className="text-[#6ecba0] font-bold font-tabular">
                {formatINR(cashPosition?.received_bank_credits ?? cashPosition?.received_amount)}
              </span>
            </div>

            <div
              className="pt-2 flex justify-between items-center text-xs p-2.5 rounded-xs border"
              style={{
                borderTop: "1px solid var(--border-subtle)",
                borderColor: formatVariance(cashPosition?.settlement_variance).isZero
                  ? "var(--matched-border)"
                  : "var(--variance-border)",
                background: formatVariance(cashPosition?.settlement_variance).isZero
                  ? "var(--matched-bg)"
                  : "var(--variance-bg)",
                color: formatVariance(cashPosition?.settlement_variance).isZero
                  ? "var(--matched-text)"
                  : "var(--variance-text)",
              }}
            >
              <span className="uppercase text-[10px] font-bold">Net Variance:</span>
              <span className="font-bold font-tabular">
                {formatVariance(cashPosition?.settlement_variance).text}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ── ZONE 5: EXCEPTION QUEUE QUICK PREVIEW TABLE ─────────────── */}
      <div
        className="rounded-sm border p-6"
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
            <h2 className="text-xs font-bold uppercase tracking-wider text-[#eceae6] font-mono">
              Active Exception Queue
            </h2>
            <p className="text-xs text-[#8e96a0] mt-0.5">
              Unreconciled records routed to forensic investigation dossiers
            </p>
          </div>
          <Link
            href={exceptionsLink}
            className="text-xs text-[#c9a96e] hover:text-[#e4caa0] font-bold font-mono"
          >
            View All Exceptions →
          </Link>
        </div>

        {exceptionsLoading ? (
          <div className="pt-4">
            <LoadingSkeleton variant="table" count={5} />
          </div>
        ) : !exceptionsData || exceptionsData.exceptions.length === 0 ? (
          <div className="py-8 text-center text-[#8e96a0] font-mono text-xs">
            Zero active exceptions. Financial state is completely reconciled.
          </div>
        ) : (
          <div className="overflow-x-auto pt-2">
            <table className="w-full text-left font-mono text-xs">
              <thead>
                <tr
                  className="text-[10px] uppercase font-bold"
                  style={{
                    color: "var(--text-tertiary)",
                    borderBottom: "1px solid var(--border-subtle)",
                  }}
                >
                  <th className="py-2.5 px-3">Exception ID / Txn</th>
                  <th className="py-2.5 px-3">Category</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Exposure</th>
                  <th className="py-2.5 px-3">Recommended Action</th>
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
                      key={excId ? `${excId}-${idx}` : `exception-prev-${idx}`}
                      className="hover:bg-[#13161a] transition-micro text-[#eceae6]"
                    >
                      <td className="py-3 px-3">
                        <div className="font-medium text-[#eceae6] capitalize">
                          {(ex.category || "unexplained").replace(/_/g, " ")}
                        </div>
                        <TechnicalReference
                          id={excId}
                          label="ref"
                          maxVisible={20}
                          inline
                          className="mt-0.5 text-[10px]"
                        />
                      </td>
                      <td className="py-3 px-3">
                        <span className="text-[#8e96a0] font-medium">{cat.replace(/_/g, " ")}</span>
                      </td>
                      <td className="py-3 px-3">
                        <StatusBadge status={ex.status} />
                      </td>
                      <td className="py-3 px-3 text-right font-bold font-tabular text-[#e07070]">
                        {formatINR(exp)}
                      </td>
                      <td className="py-3 px-3 text-[#8e96a0] max-w-xs truncate text-[11px]">
                        {ex.recommended_action || "Manual Investigation"}
                      </td>
                      <td className="py-3 px-3 text-right">
                        <Link
                          href={`/exceptions/${encodeURIComponent(excId)}`}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xs text-xs font-semibold transition-micro"
                          style={{
                            color: "var(--bg)",
                            background: "var(--accent)",
                          }}
                          onMouseEnter={(e) => (e.currentTarget.style.background = "var(--accent-hover)")}
                          onMouseLeave={(e) => (e.currentTarget.style.background = "var(--accent)")}
                        >
                          Investigate Dossier
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
    </div>
  );
}
