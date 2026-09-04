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

  const totalRecs = overview?.total_records_processed ?? overview?.total_records ?? 0;
  const matchedRecs = overview?.total_matched_records ?? overview?.matched_records ?? 0;
  const exceptionRecs = overview?.unresolved_transactions ?? overview?.open_exceptions ?? 0;
  const exposureVal = overview?.unresolved_monetary_exposure_inr ?? overview?.financial_exposure ?? 0;
  const volumeVal = overview?.total_transaction_value_inr ?? overview?.total_financial_volume ?? 0;

  return (
    <div className="space-y-8 pb-14 select-none">
      {/* ── ZONE 0: CONTROL STATUS PROOF BAR ───────────────────────── */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-2.5 rounded-xs bg-[#FFFFFF] border border-[#D7D3CA] text-[11px] shadow-xs">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#9E7B35]">
            CONTROL STATUS
          </span>
          <span className="text-[#BDB8AE]">|</span>
        </div>

        <div className="flex flex-wrap items-center gap-x-6 gap-y-1 text-[#555B61]">
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-[#6F747A] uppercase font-semibold">Data</span>
            <span className="font-bold text-[#17191C]">Verified</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-[#6F747A] uppercase font-semibold">Recon</span>
            <span className="font-bold text-[#1E7B4D]">Active</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-[#6F747A] uppercase font-semibold">Evidence</span>
            <span className="font-bold text-[#17191C]">Grounded</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-[#6F747A] uppercase font-semibold">AI</span>
            <span className="font-bold text-[#17191C]">Assistive</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-[#6F747A] uppercase font-semibold">HITL</span>
            <span className="font-bold text-[#9C6B19]">Enforced</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-[#6F747A] uppercase font-semibold">Audit</span>
            <span className="font-bold text-[#1E7B4D]">Enabled</span>
          </div>
        </div>

        {overview?.run_id && (
          <div className="hidden lg:flex items-center gap-2 text-[10px] font-mono text-[#6F747A]">
            <span>Scope:</span>
            <TechnicalReference id={overview.run_id} maxVisible={20} />
          </div>
        )}
      </div>

      {/* ── ZONE 1: TOP BANNER: OPERATIONAL CONTEXT ─────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#D7D3CA] pb-5">
        <div>
          <h1 className="text-xl font-bold font-mono text-[#17191C] flex items-center gap-2.5 tracking-tight">
            Finance Operations Command Center
            <span className="text-[10px] px-2 py-0.5 rounded-xs bg-[#F1F8F4] text-[#1E7B4D] border border-[rgba(30,123,77,0.2)] font-bold">
              LIVE
            </span>
          </h1>
          <p className="text-xs text-[#555B61] mt-1 italic">
            Continuous real-time multi-source reconciliation across Payment Gateway, Internal Ledger, and Core Banking.
          </p>
        </div>

        {overview?.run_id && (
          <div className="flex items-center gap-2 text-xs font-mono text-[#555B61]">
            <span>Scoped Run:</span>
            <TechnicalReference id={overview.run_id} maxVisible={24} />
          </div>
        )}
      </div>

      {/* ── ZONE 2: FOUR PRIMARY KPI MATRIX BLOCKS ─────────────────── */}
      {overviewLoading ? (
        <LoadingSkeleton variant="card" count={4} />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Link href="/reconciliation" className="block hover:opacity-90 transition-opacity">
            <MetricCard
              title="Total Financial Volume"
              value={formatINR(overview?.total_transaction_value_inr ?? overview?.total_financial_volume)}
              subtitle={`${totalRecs} feed records in scope`}
              icon={<DollarSign className="h-4 w-4 text-[#9E7B35]" />}
              statusBorder="indigo"
            />
          </Link>

          <Link href="/reconciliation" className="block hover:opacity-90 transition-opacity">
            <MetricCard
              title="Reconciliation Rate"
              value={formatPercent(overview?.match_rate)}
              subtitle={`${matchedRecs} of ${totalRecs} matched`}
              delta={overview?.match_rate && overview.match_rate >= 0.9 ? "Optimal" : "Review"}
              deltaType={overview?.match_rate && overview.match_rate >= 0.9 ? "positive" : "neutral"}
              icon={<GitMerge className="h-4 w-4 text-[#1E7B4D]" />}
              statusBorder="emerald"
            />
          </Link>

          <Link
            href={overview?.run_id
              ? `/exceptions?status=open&run_id=${encodeURIComponent(overview.run_id)}`
              : "/exceptions?status=open"}
            className="block hover:opacity-90 transition-opacity"
          >
            <MetricCard
              title="Open Exceptions"
              value={exceptionRecs.toString()}
              subtitle={`${exceptionRecs} unresolved exceptions`}
              delta={exceptionRecs > 0 ? "Action Required" : "Zero Variance"}
              deltaType={exceptionRecs > 0 ? "negative" : "positive"}
              icon={<AlertOctagon className="h-4 w-4 text-[#B83A3A]" />}
              statusBorder="rose"
            />
          </Link>

          <Link
            href={overview?.run_id
              ? `/exceptions?status=open&run_id=${encodeURIComponent(overview.run_id)}`
              : "/exceptions?status=open"}
            className="block hover:opacity-90 transition-opacity"
          >
            <MetricCard
              title="Unreconciled Exposure"
              value={formatINR(exposureVal)}
              subtitle={`Expected Cost: ${formatINR(overview?.manual_review_exposure_inr ?? overview?.expected_cost)}`}
              delta={`${formatPercent(overview?.unreconciled_exposure_pct)} volume`}
              deltaType={overview?.unreconciled_exposure_pct && overview.unreconciled_exposure_pct > 0.05 ? "negative" : "neutral"}
              icon={<ShieldAlert className="h-4 w-4 text-[#9C6B19]" />}
              statusBorder="amber"
            />
          </Link>
        </div>
      )}

      {/* ── ZONE 3: 3-WAY RECONCILIATION PIPELINE VISUALIZER ───────── */}
      <div className="pt-1">
        <FunnelChart funnel={funnel} isLoading={funnelLoading} runId={overview?.run_id ?? undefined} />
      </div>

      {/* ── ZONE 4: GRID: EXECUTIVE ASSESSMENT & LIVE CASH POSITION ── */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Executive Assessment */}
        <div className="lg:col-span-2 rounded-xs border border-[#D7D3CA] bg-[#FFFFFF] p-6 shadow-xs">
          <div className="flex items-center justify-between pb-3.5 border-b border-[#E2DDD3]">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#9E7B35] font-mono">
                VERIDEX OPERATIONAL ASSESSMENT
              </span>
            </div>
            {brief?.reconciliation_health_score !== undefined && (
              <span className="font-mono text-xs text-[#1E7B4D] font-bold px-2.5 py-0.5 rounded-xs bg-[#F1F8F4] border border-[rgba(30,123,77,0.2)]">
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
              <div className="p-3.5 rounded-xs border border-[#D7D3CA] bg-[#F7F5F0] text-[#17191C] leading-relaxed font-semibold">
                <p>{brief.why || brief.headline || "Continuous multi-source reconciliation in progress."}</p>
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-1 text-center">
                <div className="p-3 rounded-xs bg-[#F7F5F0] border border-[#D7D3CA]">
                  <div className="text-[10px] text-[#6F747A] uppercase font-bold">Match Rate</div>
                  <div className="text-sm font-bold text-[#1E7B4D] mt-0.5 font-tabular">
                    {formatPercent(brief.reconciliation_match_rate_percent ?? brief.key_metrics?.match_rate_pct)}
                  </div>
                </div>

                <div className="p-3 rounded-xs bg-[#F7F5F0] border border-[#D7D3CA]">
                  <div className="text-[10px] text-[#6F747A] uppercase font-bold">Money at Risk</div>
                  <div className="text-sm font-bold text-[#B83A3A] mt-0.5 font-tabular">
                    {formatINR(brief.money_at_risk_inr ?? brief.key_metrics?.financial_exposure_inr)}
                  </div>
                </div>

                <div className="p-3 rounded-xs bg-[#F7F5F0] border border-[#D7D3CA]">
                  <div className="text-[10px] text-[#6F747A] uppercase font-bold">Source Health</div>
                  <div className="text-sm font-bold text-[#17191C] mt-0.5">
                    {brief.source_health || "HEALTHY"}
                  </div>
                </div>

                <div className="p-3 rounded-xs bg-[#F7F5F0] border border-[#D7D3CA]">
                  <div className="text-[10px] text-[#6F747A] uppercase font-bold">Review Required</div>
                  <div className={`text-sm font-bold mt-0.5 ${brief.human_review_required ? "text-[#9C6B19]" : "text-[#1E7B4D]"}`}>
                    {brief.human_review_required ? "YES (HITL)" : "NO"}
                  </div>
                </div>
              </div>

              {/* Critical Findings & Recommended Action */}
              <div className="space-y-2 pt-2 border-t border-[#E2DDD3]">
                <div className="text-[11px] font-bold text-[#6F747A] uppercase tracking-wider">
                  Recommended Controller Action:
                </div>
                <div className="text-[#17191C] text-xs bg-[rgba(201,169,110,0.08)] p-3 rounded-xs border border-[rgba(201,169,110,0.35)] flex items-start gap-2.5">
                  <span className="text-[#9E7B35] font-bold">▶</span>
                  <span className="font-sans font-medium">{brief.recommended_action || "Continue monitoring ingestion pipelines and process pending exceptions."}</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="py-6 text-center text-[#6F747A] font-mono text-xs">
              Executive brief unavailable for this scope.
            </div>
          )}
        </div>

        {/* Live Multi-Source Cash Position */}
        <div className="rounded-xs border border-[#D7D3CA] bg-[#FFFFFF] p-6 shadow-xs">
          <div className="flex items-center justify-between pb-3.5 border-b border-[#E2DDD3]">
            <h2 className="text-xs font-bold uppercase tracking-wider text-[#17191C] font-mono">
              Live Cash Position
            </h2>
            <Link
              href="/settlements"
              className="text-[11px] text-[#9E7B35] hover:text-[#C9A96E] font-mono font-semibold"
            >
              Full Breakdown →
            </Link>
          </div>

          <div className="pt-4 space-y-3 font-mono text-xs">
            <div className="flex justify-between text-[#555B61]">
              <span>Expected Gross:</span>
              <span className="text-[#17191C] font-bold font-tabular">
                {formatINR(cashPosition?.expected_gross ?? cashPosition?.expected_amount ?? volumeVal)}
              </span>
            </div>

            <div className="flex justify-between text-[#555B61]">
              <span>Deducted Fees:</span>
              <span className="text-[#B83A3A] font-tabular">
                {formatINR(cashPosition?.total_deducted_fees ?? cashPosition?.deducted_fees)}
              </span>
            </div>

            <div className="flex justify-between text-[#555B61]">
              <span>Deducted Taxes (GST):</span>
              <span className="text-[#9C6B19] font-tabular">
                {formatINR(cashPosition?.total_deducted_taxes ?? cashPosition?.deducted_taxes)}
              </span>
            </div>

            <div className="pt-2 border-t border-[#E2DDD3] flex justify-between text-[#17191C] font-semibold">
              <span>Expected Net:</span>
              <span className="text-[#17191C] font-bold font-tabular">
                {formatINR(cashPosition?.expected_net_settlement)}
              </span>
            </div>

            <div className="flex justify-between text-[#17191C] font-semibold">
              <span>Received Bank Credits:</span>
              <span className="text-[#1E7B4D] font-bold font-tabular">
                {formatINR(cashPosition?.received_bank_credits ?? cashPosition?.received_amount)}
              </span>
            </div>

            <div className={`pt-2 border-t border-[#E2DDD3] flex justify-between items-center text-xs p-2.5 rounded-xs ${
              formatVariance(cashPosition?.settlement_variance).isZero
                ? "bg-[#F1F8F4] text-[#1E7B4D]"
                : "bg-[#FFF9F9] text-[#B83A3A]"
            }`}>
              <span className="uppercase text-[10px] font-bold">Net Variance:</span>
              <span className="font-bold font-tabular">
                {formatVariance(cashPosition?.settlement_variance).text}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* ── ZONE 5: EXCEPTION QUEUE QUICK PREVIEW TABLE ─────────────── */}
      <div className="rounded-xs border border-[#D7D3CA] bg-[#FFFFFF] p-6 shadow-xs">
        <div className="flex items-center justify-between pb-4 border-b border-[#E2DDD3]">
          <div>
            <h2 className="text-xs font-bold uppercase tracking-wider text-[#17191C] font-mono">
              Active Exception Queue
            </h2>
            <p className="text-xs text-[#555B61] mt-0.5">
              Unreconciled records routed to forensic investigation dossiers
            </p>
          </div>
          <Link
            href="/exceptions"
            className="text-xs text-[#9E7B35] hover:text-[#C9A96E] font-bold font-mono"
          >
            View All Exceptions →
          </Link>
        </div>

        {exceptionsLoading ? (
          <div className="pt-4">
            <LoadingSkeleton variant="table" count={5} />
          </div>
        ) : !exceptionsData || exceptionsData.exceptions.length === 0 ? (
          <div className="py-8 text-center text-[#6F747A] font-mono text-xs">
            Zero active exceptions. Financial state is completely reconciled.
          </div>
        ) : (
          <div className="overflow-x-auto pt-2">
            <table className="w-full text-left font-mono text-xs">
              <thead>
                <tr className="border-b border-[#E2DDD3] text-[#6F747A] text-[10px] uppercase font-bold">
                  <th className="py-2.5 px-3">Exception ID / Txn</th>
                  <th className="py-2.5 px-3">Category</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Exposure</th>
                  <th className="py-2.5 px-3">Recommended Action</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E2DDD3] text-[#17191C]">
                {exceptionsData.exceptions.map((ex, idx) => {
                  const excId = ex.exception_id || ex.id || `exc-${idx}`;
                  const cat = ex.category || ex.exception_category || "unexplained";
                  const exp = ex.financial_exposure_inr ?? ex.financial_exposure;

                  return (
                    <tr key={excId ? `${excId}-${idx}` : `exception-prev-${idx}`} className="hover:bg-[#F7F5F0] transition-colors">
                      <td className="py-3 px-3 font-semibold text-[#17191C]">
                        <div className="font-medium text-[#17191C] capitalize">
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
                        <span className="text-[#555B61] font-medium">{cat.replace(/_/g, " ")}</span>
                      </td>
                      <td className="py-3 px-3">
                        <StatusBadge status={ex.status} />
                      </td>
                      <td className="py-3 px-3 text-right font-bold font-tabular text-[#B83A3A]">
                        {formatINR(exp)}
                      </td>
                      <td className="py-3 px-3 text-[#555B61] max-w-xs truncate text-[11px]">
                        {ex.recommended_action || "Manual Investigation"}
                      </td>
                      <td className="py-3 px-3 text-right">
                        <Link
                          href={`/exceptions/${encodeURIComponent(excId)}`}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xs bg-[#C9A96E] hover:bg-[#D8BC8A] text-[#171A1E] text-xs font-semibold transition-colors shadow-xs"
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
