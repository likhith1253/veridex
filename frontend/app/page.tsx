"use client";

import React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { controllerApi } from "@/lib/api/controllerApi";
import { formatINR, formatPercent, formatVariance } from "@/lib/utils/formatters";
import { MetricCard } from "@/components/common/MetricCard";
import { StatusBadge } from "@/components/common/StatusBadge";
import { FunnelChart } from "@/components/reconciliation/FunnelChart";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { ErrorState } from "@/components/common/ErrorState";
import {
  DollarSign,
  GitMerge,
  AlertOctagon,
  ShieldAlert,
  ArrowRight,
  Sparkles,
  TrendingUp,
  Scale,
  CheckCircle2,
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
        title="Failed to Load Command Center Data"
        message={overviewError instanceof Error ? overviewError.message : "Backend unreachable"}
        onRetry={refetchOverview}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Banner: Executive Context */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#222634] pb-4">
        <div>
          <h1 className="text-lg font-bold font-mono text-zinc-100 flex items-center gap-2">
            Finance Operations Command Center
            <span className="text-xs px-2 py-0.5 rounded bg-sky-950 text-sky-400 border border-sky-800">
              LIVE
            </span>
          </h1>
          <p className="text-xs text-zinc-400 mt-0.5">
            Continuous real-time multi-source reconciliation across Payment Gateway, Internal Ledger, and Core Banking.
          </p>
        </div>

        {overview?.run_id && (
          <div className="flex items-center gap-2 text-xs font-mono text-zinc-400">
            <span>Scoped Run:</span>
            <span className="font-semibold text-zinc-200 px-2 py-1 rounded bg-[#171a23] border border-zinc-800">
              {overview.run_id}
            </span>
          </div>
        )}
      </div>

      {/* KPI Matrix Cards */}
      {overviewLoading ? (
        <LoadingSkeleton variant="card" count={4} />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <MetricCard
            title="Total Financial Volume"
            value={formatINR(overview?.total_financial_volume)}
            subtitle={`${overview?.total_records || 0} total records in scope`}
            icon={<DollarSign className="h-4 w-4 text-sky-400" />}
            statusBorder="indigo"
          />

          <MetricCard
            title="Reconciliation Rate"
            value={formatPercent(overview?.match_rate)}
            subtitle={`${overview?.matched_records || 0} reconciled records`}
            delta={overview?.match_rate && overview.match_rate >= 0.9 ? "Target Exceeded" : "Within Range"}
            deltaType={overview?.match_rate && overview.match_rate >= 0.9 ? "positive" : "neutral"}
            icon={<GitMerge className="h-4 w-4 text-emerald-400" />}
            statusBorder="emerald"
          />

          <MetricCard
            title="Open Exceptions"
            value={overview?.open_exceptions || 0}
            subtitle={`${overview?.resolved_exceptions || 0} resolved / closed`}
            delta={overview?.open_exceptions === 0 ? "Zero Backlog" : `${overview?.open_exceptions} Pending`}
            deltaType={overview?.open_exceptions === 0 ? "positive" : "negative"}
            icon={<AlertOctagon className="h-4 w-4 text-rose-400" />}
            statusBorder={overview?.open_exceptions && overview.open_exceptions > 0 ? "rose" : "none"}
          />

          <MetricCard
            title="Unreconciled Exposure"
            value={formatINR(overview?.financial_exposure)}
            subtitle={`Expected Cost: ${formatINR(overview?.expected_cost)}`}
            delta={`${formatPercent(overview?.unreconciled_exposure_pct)} volume`}
            deltaType={overview?.unreconciled_exposure_pct && overview.unreconciled_exposure_pct > 0.05 ? "negative" : "neutral"}
            icon={<ShieldAlert className="h-4 w-4 text-amber-400" />}
            statusBorder="amber"
          />
        </div>
      )}

      {/* Funnel Pipeline Visualizer */}
      <FunnelChart funnel={funnel} isLoading={funnelLoading} />

      {/* Grid: Executive Daily Brief & Grounded Cash Position */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Executive AI Brief */}
        <div className="lg:col-span-2 rounded-lg border border-[#222634] bg-[#11131a] p-5">
          <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded bg-indigo-950/80 border border-indigo-800/60 text-indigo-400">
                <Sparkles className="h-4 w-4" />
              </div>
              <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-300 font-mono">
                Executive Daily Brief
              </h2>
            </div>
            {brief?.reconciliation_health_score !== undefined && (
              <span className="font-mono text-xs text-emerald-400 font-bold px-2 py-0.5 rounded bg-emerald-950/40 border border-emerald-800/60">
                Health Score: {brief.reconciliation_health_score}/100
              </span>
            )}
          </div>

          {briefLoading ? (
            <div className="py-4 space-y-2 animate-pulse">
              <div className="h-4 w-3/4 rounded bg-zinc-800" />
              <div className="h-3 w-full rounded bg-zinc-800/60" />
              <div className="h-3 w-5/6 rounded bg-zinc-800/60" />
            </div>
          ) : (
            <div className="pt-4 space-y-4 text-xs">
              <p className="font-mono text-sm font-semibold text-zinc-100">
                {brief?.headline || "Reconciliation pipeline operational with active deterministic matching."}
              </p>

              {brief?.critical_findings && brief.critical_findings.length > 0 && (
                <div className="space-y-1.5">
                  <span className="text-[10px] uppercase font-mono font-bold text-zinc-500">
                    Critical Audit Findings
                  </span>
                  <ul className="space-y-1 text-zinc-300 font-mono text-[11px]">
                    {brief.critical_findings.map((item, idx) => (
                      <li key={idx} className="flex items-start gap-2">
                        <span className="text-amber-400 mt-0.5">•</span>
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {brief?.recommended_actions && brief.recommended_actions.length > 0 && (
                <div className="pt-2 border-t border-zinc-800/80 flex items-center justify-between">
                  <span className="text-[11px] font-mono text-zinc-400">
                    Recommended Policy Actions: {brief.recommended_actions.length} pending review
                  </span>
                  <Link
                    href="/actions"
                    className="inline-flex items-center gap-1 text-xs font-semibold text-sky-400 hover:text-sky-300 font-mono"
                  >
                    Review in Actions Queue <ArrowRight className="h-3.5 w-3.5" />
                  </Link>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Grounded Cash Position Snapshot */}
        <div className="rounded-lg border border-[#222634] bg-[#11131a] p-5">
          <div className="flex items-center justify-between pb-3 border-b border-zinc-800">
            <div className="flex items-center gap-2">
              <Scale className="h-4 w-4 text-sky-400" />
              <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-300 font-mono">
                Cash Parity Snapshot
              </h2>
            </div>
            <Link
              href="/settlements"
              className="text-[11px] text-zinc-400 hover:text-sky-400 font-mono"
            >
              Full Breakdown →
            </Link>
          </div>

          <div className="pt-4 space-y-3 font-mono text-xs">
            <div className="flex justify-between text-zinc-400">
              <span>Expected Gross:</span>
              <span className="text-zinc-200 font-bold font-tabular">
                {formatINR(cashPosition?.expected_gross)}
              </span>
            </div>

            <div className="flex justify-between text-zinc-400">
              <span>Deducted Fees:</span>
              <span className="text-rose-300 font-tabular">
                {formatINR(cashPosition?.deducted_fees)}
              </span>
            </div>

            <div className="flex justify-between text-zinc-400">
              <span>Deducted Taxes (GST):</span>
              <span className="text-amber-300 font-tabular">
                {formatINR(cashPosition?.deducted_taxes)}
              </span>
            </div>

            <div className="pt-2 border-t border-zinc-800 flex justify-between text-zinc-200 font-semibold">
              <span>Expected Net:</span>
              <span className="text-sky-300 font-tabular">
                {formatINR(cashPosition?.expected_net_settlement)}
              </span>
            </div>

            <div className="flex justify-between text-zinc-200 font-semibold">
              <span>Received Bank Credits:</span>
              <span className="text-emerald-300 font-tabular">
                {formatINR(cashPosition?.received_bank_credits)}
              </span>
            </div>

            <div className="pt-2 border-t border-zinc-800/80 flex justify-between items-center text-xs">
              <span className="text-zinc-500 uppercase text-[10px]">Net Variance:</span>
              <span
                className={`font-bold font-tabular ${
                  formatVariance(cashPosition?.settlement_variance).isZero
                    ? "text-emerald-400"
                    : "text-rose-400"
                }`}
              >
                {formatVariance(cashPosition?.settlement_variance).text}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Exception Queue Quick Preview Table */}
      <div className="rounded-lg border border-[#222634] bg-[#11131a] p-5">
        <div className="flex items-center justify-between pb-4 border-b border-zinc-800">
          <div>
            <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-300 font-mono">
              Active Exception Queue
            </h2>
            <p className="text-xs text-zinc-500 mt-0.5">
              Unreconciled records routed to forensic investigation dossiers
            </p>
          </div>
          <Link
            href="/exceptions"
            className="inline-flex items-center gap-1 text-xs font-semibold text-sky-400 hover:text-sky-300 font-mono"
          >
            View All Exceptions ({exceptionsData?.total_count || 0}) <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>

        {exceptionsLoading ? (
          <LoadingSkeleton variant="table" count={4} />
        ) : !exceptionsData?.exceptions || exceptionsData.exceptions.length === 0 ? (
          <div className="p-8 text-center text-zinc-500 font-mono text-xs">
            Zero open exceptions detected in current reconciliation run.
          </div>
        ) : (
          <div className="overflow-x-auto pt-2">
            <table className="w-full text-left font-mono text-xs">
              <thead>
                <tr className="border-b border-zinc-800 text-zinc-500 text-[10px] uppercase">
                  <th className="py-2.5 px-3">Exception ID / Txn</th>
                  <th className="py-2.5 px-3">Category</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Exposure</th>
                  <th className="py-2.5 px-3">Recommended Action</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800/60 text-zinc-300">
                {exceptionsData.exceptions.map((ex, idx) => (
                  <tr key={ex.id ? `${ex.id}-${idx}` : `exception-prev-${idx}`} className="hover:bg-[#171a23] transition-colors">
                    <td className="py-3 px-3 font-semibold text-zinc-100">
                      <div>{ex.id}</div>
                      <div className="text-[10px] text-zinc-500">{ex.transaction_id}</div>
                    </td>
                    <td className="py-3 px-3">
                      <span className="text-zinc-300">{(ex.exception_category || "UNKNOWN").replace(/_/g, " ")}</span>
                    </td>
                    <td className="py-3 px-3">
                      <StatusBadge status={ex.status} />
                    </td>
                    <td className="py-3 px-3 text-right font-bold font-tabular text-rose-300">
                      {formatINR(ex.financial_exposure)}
                    </td>
                    <td className="py-3 px-3 text-zinc-400 max-w-xs truncate text-[11px]">
                      {ex.recommended_action || "Manual Investigation"}
                    </td>
                    <td className="py-3 px-3 text-right">
                      <Link
                        href={`/exceptions/${ex.id}`}
                        className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-semibold transition-colors"
                      >
                        Investigate Dossier
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
