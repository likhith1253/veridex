"use client";

import React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { controllerApi } from "@/lib/api/controllerApi";
import { formatINR, formatPercent, formatVariance } from "@/lib/utils/formatters";
import { MetricCard } from "@/components/common/MetricCard";
import { StatusBadge } from "@/components/common/StatusBadge";
import { FunnelChart } from "@/components/reconciliation/FunnelChart";
import { MatchDistributionChart } from "@/components/reconciliation/MatchDistributionChart";
import { ExceptionCategoryChart } from "@/components/exceptions/ExceptionCategoryChart";
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

  // Wider sample for the category-distribution chart — separate from the
  // 5-row preview table above, which isn't enough to chart a distribution.
  const {
    data: exceptionsForChart,
    isLoading: exceptionsChartLoading,
  } = useQuery({
    queryKey: ["controller-exceptions-chart-sample"],
    queryFn: () => controllerApi.getExceptions({ page: 1, page_size: 200 }),
    staleTime: 20000,
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
  // "Issues needing attention" = curated exceptions (the actual review queue),
  // not the raw unresolved-transaction count — these are different populations
  // (an exception can be raised on an otherwise-matched transaction too), and
  // the exception count is what the sidebar badge and /exceptions page use as
  // the authoritative "open issues" figure. Keeping this consistent everywhere
  // avoids the number disagreeing across screens.
  const exceptionRecs = overview?.open_exceptions ?? overview?.unresolved_transactions ?? 0;
  const exposureVal = overview?.unresolved_monetary_exposure_inr ?? overview?.financial_exposure ?? 0;
  const volumeVal = overview?.total_transaction_value_inr ?? overview?.total_financial_volume ?? 0;
  const runId = overview?.run_id;

  // Run provenance: has a reconciliation ever run, and what state is the most
  // recent one in? This is authoritative backend state (ReconciliationRun.status),
  // never a frontend-only flag, so a refresh can never fake or lose it.
  const hasAnyRun = overview?.has_any_run ?? false;
  const latestRunStatus = overview?.latest_run_status ?? null;
  const reconStatusLabel = !hasAnyRun
    ? "No active run"
    : latestRunStatus === "running" || latestRunStatus === "pending"
    ? "In progress"
    : latestRunStatus === "failed"
    ? "Failed"
    : "Idle";
  const reconStatusColor = !hasAnyRun
    ? "#8e96a0"
    : latestRunStatus === "failed"
    ? "#e07070"
    : latestRunStatus === "running" || latestRunStatus === "pending"
    ? "#d4a84e"
    : "#6ecba0";
  const latestReconciliationLabel = !hasAnyRun
    ? "No active reconciliation"
    : latestRunStatus === "running" || latestRunStatus === "pending"
    ? "Reconciliation in progress"
    : latestRunStatus === "failed"
    ? "Reconciliation failed"
    : "Reconciliation complete";

  const reconLink = runId ? `/reconciliation?run_id=${encodeURIComponent(runId)}` : "/reconciliation";
  const exceptionsLink = runId
    ? `/exceptions?status=open&run_id=${encodeURIComponent(runId)}`
    : "/exceptions?status=open";

  const hasIssues = exceptionRecs > 0;

  return (
    <div className="space-y-8 pb-16 select-none">
      {/* ── HERO: current state, what needs attention, one next step ───
          Entrance sequence: the hero rises in first, glowing gently once
          settled, so opening the Control Center reads as an arrival rather
          than a static dashboard dump. */}
      <div
        className="rounded-sm border overflow-hidden veridex-rise-in veridex-hero-glow"
        style={{ borderColor: "var(--border-subtle)", background: "var(--surface-1)" }}
      >
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-6 pt-5">
          <div>
            <h1 className="text-xl font-bold font-mono text-[#eceae6] flex items-center gap-2.5 tracking-tight">
              Financial Control Center
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
            <p className="text-xs text-[#8e96a0] mt-1">
              Continuous reconciliation across Payment Gateway, Internal Ledger, and Core Bank
            </p>
          </div>
          <div className="text-right">
            <div className="text-[10px] uppercase font-bold tracking-wider text-[#545e6a]">
              Latest reconciliation
            </div>
            {overviewLoading ? (
              <div className="h-4 w-32 rounded-xs skeleton mt-1 ml-auto" />
            ) : (
              <div className="flex items-center gap-2 mt-0.5 justify-end">
                <span className="text-xs font-bold" style={{ color: reconStatusColor }}>
                  {latestReconciliationLabel}
                </span>
                {runId && <TechnicalReference id={runId} label="run" maxVisible={14} inline />}
              </div>
            )}
          </div>
        </div>

        {/* Current state — the one number that matters most. Gated behind
            overviewLoading so a fresh page load never flashes a FALSE "INR 0.00
            / no active reconciliation / zero issues" before real data arrives —
            that's actively misleading, not just an empty state, and it visibly
            contradicted the sidebar/topbar which already had cached data. */}
        {overviewLoading ? (
          <div className="px-6 pt-6 pb-2">
            <LoadingSkeleton variant="card" count={2} />
          </div>
        ) : (
          <>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 px-6 pt-6">
              <div>
                <div className="text-[10px] uppercase font-bold tracking-wider text-[#545e6a] mb-1">
                  Current state
                </div>
                <div className="text-3xl font-bold font-mono text-[#eceae6] tabular-nums">
                  {formatINR(volumeVal)}
                </div>
                <p className="text-xs text-[#8e96a0] mt-1">
                  {totalRecs} record{totalRecs === 1 ? "" : "s"} available ·{" "}
                  <span style={{ color: "var(--matched-text)" }}>{formatPercent(overview?.match_rate)} reconciled</span>
                  {" "}({matchedRecs} of {totalRecs})
                </p>
              </div>

              <div>
                <div
                  className="text-[10px] uppercase font-bold tracking-wider mb-1"
                  style={{ color: hasIssues ? "var(--accent)" : "#545e6a" }}
                >
                  What needs attention
                </div>
                {hasIssues ? (
                  <>
                    <div className="text-3xl font-bold font-mono tabular-nums" style={{ color: "#e07070" }}>
                      {formatINR(exposureVal)}
                    </div>
                    <p className="text-xs text-[#8e96a0] mt-1">
                      money at risk across{" "}
                      <span className="text-[#eceae6] font-semibold">
                        {exceptionRecs} open {exceptionRecs === 1 ? "issue" : "issues"}
                      </span>
                    </p>
                  </>
                ) : (
                  <>
                    <div className="text-3xl font-bold font-mono tabular-nums" style={{ color: "#6ecba0" }}>
                      Zero
                    </div>
                    <p className="text-xs text-[#8e96a0] mt-1">open issues — all records reconciled</p>
                  </>
                )}
              </div>
            </div>

            {/* One primary action, contextual to actual state */}
            <div
              className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 px-6 py-4 mt-6"
              style={{ borderTop: "1px solid var(--border-subtle)", background: "var(--surface-2)" }}
            >
              <p className="text-xs text-[#8e96a0]">
                {hasIssues
                  ? "Human review and authorization is required before any money movement."
                  : totalRecs === 0
                  ? "No financial data has been reconciled yet."
                  : "Reconciliation runs are complete with zero unhandled variances."}
              </p>
              <Link
                href={hasIssues ? exceptionsLink : "/reconciliation"}
                className="inline-flex items-center justify-center gap-1.5 px-4 py-2 rounded-xs text-xs font-bold transition-micro flex-shrink-0"
                style={{ color: "#080a0c", background: "var(--accent)" }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "var(--accent-hover)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "var(--accent)")}
              >
                <span>{hasIssues ? "Review highest-priority issue" : "Run reconciliation"}</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          </>
        )}
      </div>

      {/* ── Control status — secondary/technical, de-emphasized ──────── */}
      <div
        className="flex flex-wrap items-center gap-x-6 gap-y-1.5 px-4 py-2 rounded-xs text-[10px] border veridex-rise-in veridex-delay-2"
        style={{ borderColor: "var(--border-subtle)", background: "var(--surface-1)", color: "#8e96a0" }}
      >
        <span className="uppercase font-bold tracking-wider" style={{ color: "var(--text-tertiary)" }}>
          System
        </span>
        <span>Data <b className="text-[#eceae6]">Verified</b></span>
        <span>Recon <b style={{ color: reconStatusColor }}>{reconStatusLabel}</b></span>
        <span>Evidence <b className="text-[#eceae6]">Grounded</b></span>
        <span>AI <b className="text-[#eceae6]">Assistive</b></span>
        <span>HITL <b style={{ color: "#d4a84e" }}>Enforced</b></span>
        <span>Audit <b style={{ color: "#6ecba0" }}>Enabled</b></span>
      </div>

      {/* ── SUPPORTING FINANCIAL METRICS ─────────────────────────────── */}
      <div>
        <div className="text-[10px] font-bold uppercase tracking-wider text-[#545e6a] mb-3">
          Supporting financial metrics
        </div>
        {overviewLoading ? (
        <LoadingSkeleton variant="card" count={4} />
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Link href={reconLink} className="block veridex-card-lift veridex-rise-in veridex-delay-1">
            <MetricCard
              title="Total volume processed"
              value={formatINR(volumeVal)}
              subtitle={`${totalRecs} feed records in scope`}
              icon={<DollarSign className="h-4 w-4 text-[#c9a96e]" />}
              statusBorder="indigo"
            />
          </Link>

          <Link href={reconLink} className="block veridex-card-lift veridex-rise-in veridex-delay-2">
            <MetricCard
              title="Reconciliation rate"
              value={formatPercent(overview?.match_rate)}
              subtitle={`${matchedRecs} of ${totalRecs} matched`}
              delta={overview?.match_rate && overview.match_rate >= 0.9 ? "Optimal" : "Review"}
              deltaType={overview?.match_rate && overview.match_rate >= 0.9 ? "positive" : "neutral"}
              icon={<GitMerge className="h-4 w-4 text-[#6ecba0]" />}
              statusBorder="emerald"
            />
          </Link>

          <Link href={exceptionsLink} className="block veridex-card-lift veridex-rise-in veridex-delay-3">
            <MetricCard
              title="Issues needing attention"
              value={exceptionRecs.toString()}
              subtitle={`${exceptionRecs} open issues`}
              delta={exceptionRecs > 0 ? "Review needed" : "Zero variance"}
              deltaType={exceptionRecs > 0 ? "negative" : "positive"}
              icon={<AlertOctagon className="h-4 w-4 text-[#e07070]" />}
              statusBorder="rose"
            />
          </Link>

          <Link href={exceptionsLink} className="block veridex-card-lift veridex-rise-in veridex-delay-4">
            <MetricCard
              title="Money at risk"
              value={formatINR(exposureVal)}
              subtitle={`Expected Cost: ${formatINR(overview?.manual_review_exposure_inr ?? overview?.expected_cost)}`}
              delta={`${formatPercent(overview?.unreconciled_exposure_pct)} of volume`}
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
      </div>

      {/* ── RECONCILIATION OVERVIEW ───────────────────────────────────── */}
      <div className="veridex-rise-in veridex-delay-4">
        <div className="text-[10px] font-bold uppercase tracking-wider text-[#545e6a] mb-3">
          Reconciliation overview
        </div>
        <FunnelChart funnel={funnel} isLoading={funnelLoading} runId={runId ?? undefined} />
      </div>

      {/* ── VISUAL BREAKDOWN: match composition + issue categories ────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 veridex-rise-in veridex-delay-5">
        <div
          className="rounded-sm border p-6 veridex-card-lift"
          style={{ borderColor: "var(--border-subtle)", background: "var(--surface-1)" }}
        >
          <div className="flex items-center justify-between pb-3.5" style={{ borderBottom: "1px solid var(--border-subtle)" }}>
            <span className="text-[10px] font-bold uppercase tracking-wider font-mono" style={{ color: "var(--accent)" }}>
              Match composition
            </span>
            <span className="text-[10px] text-[#545e6a] font-mono">of {totalRecs} records</span>
          </div>
          <div className="pt-4">
            <MatchDistributionChart
              deterministic={overview?.deterministic_matches ?? 0}
              mlRecovered={overview?.ml_recovered_matches ?? 0}
              manualReview={overview?.manual_reviews ?? 0}
              unresolved={overview?.unresolved_transactions ?? 0}
              isLoading={overviewLoading}
            />
          </div>
        </div>

        <div
          className="rounded-sm border p-6 veridex-card-lift"
          style={{ borderColor: "var(--border-subtle)", background: "var(--surface-1)" }}
        >
          <div className="flex items-center justify-between pb-3.5" style={{ borderBottom: "1px solid var(--border-subtle)" }}>
            <span className="text-[10px] font-bold uppercase tracking-wider font-mono" style={{ color: "var(--accent)" }}>
              Issues by cause
            </span>
            <Link href={exceptionsLink} className="text-[10px] text-[#c9a96e] hover:text-[#e4caa0] font-mono font-semibold">
              Review all →
            </Link>
          </div>
          <div className="pt-4">
            <ExceptionCategoryChart
              exceptions={exceptionsForChart?.exceptions ?? []}
              isLoading={exceptionsChartLoading}
            />
          </div>
        </div>
      </div>

      {/* ── DEEPER INFORMATION ────────────────────────────────────────── */}
      <div>
        <div className="text-[10px] font-bold uppercase tracking-wider text-[#545e6a] mb-3">
          Deeper information
        </div>
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
                What VERIDEX found
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
                    {brief.human_review_required ? "YES" : "NO"}
                  </div>
                </div>
              </div>

              {/* Critical Findings & Recommended Action */}
              <div
                className="space-y-2 pt-2"
                style={{ borderTop: "1px solid var(--border-subtle)" }}
              >
                <div className="text-[11px] font-bold text-[#8e96a0] uppercase tracking-wider">
                  Recommended action:
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
                      "Continue monitoring ingestion pipelines and process pending issues."}
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
              Cash position
            </h2>
            <Link
              href="/settlements"
              className="text-[11px] text-[#c9a96e] hover:text-[#e4caa0] font-mono font-semibold"
            >
              Full breakdown →
            </Link>
          </div>

          <div className="pt-4 space-y-3 font-mono text-xs">
            <div className="flex justify-between text-[#8e96a0]">
              <span>Expected gross:</span>
              <span className="text-[#eceae6] font-bold font-tabular">
                {formatINR(cashPosition?.expected_gross ?? cashPosition?.expected_amount ?? volumeVal)}
              </span>
            </div>

            <div className="flex justify-between text-[#8e96a0]">
              <span>Processing fees:</span>
              <span className="text-[#e07070] font-tabular">
                {formatINR(cashPosition?.total_deducted_fees ?? cashPosition?.deducted_fees)}
              </span>
            </div>

            <div className="flex justify-between text-[#8e96a0]">
              <span>Taxes (GST):</span>
              <span className="text-[#d4a84e] font-tabular">
                {formatINR(cashPosition?.total_deducted_taxes ?? cashPosition?.deducted_taxes)}
              </span>
            </div>

            <div
              className="pt-2 flex justify-between text-[#eceae6] font-semibold"
              style={{ borderTop: "1px solid var(--border-subtle)" }}
            >
              <span>Expected payout:</span>
              <span className="text-[#eceae6] font-bold font-tabular">
                {formatINR(cashPosition?.expected_net_settlement)}
              </span>
            </div>

            <div className="flex justify-between text-[#eceae6] font-semibold">
              <span>Bank received:</span>
              <span className="text-[#6ecba0] font-bold font-tabular">
                {cashPosition?.received_bank_credits !== undefined && cashPosition?.received_bank_credits !== null
                  ? formatINR(cashPosition.received_bank_credits)
                  : "Not yet confirmed"}
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
              <span className="uppercase text-[10px] font-bold">Difference:</span>
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
              Issues needing attention
            </h2>
            <p className="text-xs text-[#8e96a0] mt-0.5">
              Open issues requiring review and authorized resolution
            </p>
          </div>
          <Link
            href={exceptionsLink}
            className="text-xs text-[#c9a96e] hover:text-[#e4caa0] font-bold font-mono"
          >
            Review all issues →
          </Link>
        </div>

        {exceptionsLoading ? (
          <div className="pt-4">
            <LoadingSkeleton variant="table" count={5} />
          </div>
        ) : !exceptionsData || exceptionsData.exceptions.length === 0 ? (
          <div className="py-8 text-center text-[#8e96a0] font-mono text-xs">
            Zero active issues. All records are completely reconciled.
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
                  <th className="py-2.5 px-3">Issue / Reference</th>
                  <th className="py-2.5 px-3">Cause</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Money at risk</th>
                  <th className="py-2.5 px-3">What happens next</th>
                  <th className="py-2.5 px-3 text-right">Review</th>
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
                          Review issue
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
    </div>
  );
}
