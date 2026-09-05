"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { controllerApi } from "@/lib/api/controllerApi";
import { reconciliationApi } from "@/lib/api/reconciliationApi";
import { formatINR, formatDateTime, cn } from "@/lib/utils/formatters";
import { StatusBadge } from "@/components/common/StatusBadge";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { RunBatchModal } from "@/components/reconciliation/RunBatchModal";
import { TechnicalReference } from "@/components/common/TechnicalReference";
import { RadialGauge } from "@/components/common/RadialGauge";
import { BreakdownBar } from "@/components/common/BreakdownBar";
import { TrendArrow } from "@/components/common/TrendArrow";
import { CountUp } from "@/components/common/CountUp";
import { usePreviousValue } from "@/lib/hooks/usePreviousValue";
import {
  Play,
  CreditCard,
  Building2,
  Receipt,
  Layers,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

// Exception-category color legend — restrained institutional palette, no
// new charting library, matches the semantic status colors used elsewhere.
const CATEGORY_COLORS = [
  "var(--variance)",
  "var(--pending)",
  "var(--ml)",
  "var(--accent-deep)",
  "var(--matched)",
  "var(--gateway)",
  "var(--bank)",
];

const FEED_PAGE_SIZE = 25;

export default function ReconciliationPage() {
  const [sourceFilter, setSourceFilter] = useState<string>("all");
  const [isBatchModalOpen, setIsBatchModalOpen] = useState(false);
  const [feedPage, setFeedPage] = useState(1);

  // Raw feed transactions query
  const {
    data: txnsData,
    isLoading: txnsLoading,
    error: txnsError,
    refetch: refetchTxns,
  } = useQuery({
    queryKey: ["reconciliation-transactions"],
    queryFn: () => controllerApi.getTransactions({ limit: 500 }),
    refetchInterval: 15000,
  });

  // Reconciliation runs history query
  const {
    data: runsData,
    isLoading: runsLoading,
  } = useQuery({
    queryKey: ["reconciliation-runs"],
    queryFn: () => reconciliationApi.getRuns(10),
    refetchInterval: 20000,
  });

  // Authoritative match-rate overview — same summary endpoint the Command
  // Center reads from — powers the hero radial gauge below.
  const { data: overview, isLoading: overviewLoading } = useQuery({
    queryKey: ["controller-overview"],
    queryFn: () => controllerApi.getOverview(),
    refetchInterval: 10000,
  });

  // Wider exception sample to drive the exception-type breakdown bar —
  // same pattern already used on the Command Center for its category chart.
  const { data: exceptionsForBreakdown, isLoading: breakdownLoading } = useQuery({
    queryKey: ["controller-exceptions-chart-sample"],
    queryFn: () => controllerApi.getExceptions({ page: 1, page_size: 200 }),
    staleTime: 20000,
  });

  const matchRatePct = (overview?.match_rate ?? 0) * 100;
  const prevMatchRatePct = usePreviousValue(overview?.match_rate !== undefined ? matchRatePct : undefined);
  const matchRateTrend = prevMatchRatePct !== undefined ? matchRatePct - prevMatchRatePct : null;

  const categoryBreakdown = React.useMemo(() => {
    const exceptions = exceptionsForBreakdown?.exceptions ?? [];
    const counts = new Map<string, number>();
    for (const ex of exceptions) {
      const cat = (ex.category || ex.exception_category || "unexplained").toString();
      counts.set(cat, (counts.get(cat) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .sort((a, b) => b[1] - a[1])
      .map(([label, value], idx) => ({
        label,
        value,
        color: CATEGORY_COLORS[idx % CATEGORY_COLORS.length],
      }));
  }, [exceptionsForBreakdown]);

  const transactions = txnsData?.transactions || [];
  const filteredTxns =
    sourceFilter === "all"
      ? transactions
      : transactions.filter((t) => (t.source || "").toLowerCase() === (sourceFilter || "").toLowerCase());

  // Previously this table was hardcoded to `.slice(0, 30)` with no way to
  // see anything past the first 30 rows, regardless of how many records
  // actually matched the filter (up to 500) — real pagination instead.
  const feedTotalPages = Math.max(1, Math.ceil(filteredTxns.length / FEED_PAGE_SIZE));
  const currentFeedPage = Math.min(feedPage, feedTotalPages);
  const pagedTxns = filteredTxns.slice(
    (currentFeedPage - 1) * FEED_PAGE_SIZE,
    currentFeedPage * FEED_PAGE_SIZE
  );

  const handleSourceFilterChange = (src: string) => {
    setSourceFilter(src);
    setFeedPage(1);
  };

  const getSourceIcon = (source?: string | null) => {
    switch ((source || "").toLowerCase()) {
      case "gateway":
        return <CreditCard className="h-3.5 w-3.5 text-[#949da6]" />;
      case "ledger":
        return <Receipt className="h-3.5 w-3.5 text-[#7eaa8e]" />;
      case "bank":
        return <Building2 className="h-3.5 w-3.5 text-[#ab9f90]" />;
      default:
        return <Layers className="h-3.5 w-3.5 text-[#8e96a0]" />;
    }
  };

  return (
    <div className="space-y-6 pb-12 select-none">
      {/* Breadcrumb Context */}
      <div className="flex items-center gap-2 text-xs font-mono text-[#8e96a0] pb-1">
        <Link href="/app" className="hover:text-[#c9a96e] transition-colors">
          Control Center
        </Link>
        <span>/</span>
        <span className="text-[#eceae6] font-semibold">Reconciliation</span>
      </div>

      {/* Page Header */}
      <div
        className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4"
        style={{ borderBottom: "1px solid var(--border-subtle)" }}
      >
        <div>
          <span
            className="text-[10px] font-semibold uppercase tracking-[0.14em]"
            style={{ color: "var(--accent)" }}
          >
            Reconcile
          </span>
          <h1 className="text-xl font-bold tracking-tight text-[#eceae6] mt-0.5">
            Did the data reconcile?
          </h1>
          <p className="text-xs text-[#8e96a0] mt-0.5">
            Compare records across Payment Gateway, Ledger, and Bank feeds to find matches and spot discrepancies
          </p>
        </div>

        <button
          onClick={() => setIsBatchModalOpen(true)}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xs font-semibold text-xs transition-micro"
          style={{
            color: "#080a0c",
            background: "var(--accent)",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "var(--accent-hover)")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "var(--accent)")}
        >
          <Play className="h-3.5 w-3.5 fill-current" />
          <span>Run reconciliation</span>
        </button>
      </div>

      {/* Hero metric: reconciliation match rate as a radial gauge, animating
          in from 0 on mount — the single most important number on this page. */}
      <div
        className="rounded-sm border p-6 veridex-card-lift veridex-rise-in grid grid-cols-1 sm:grid-cols-[auto_1fr] gap-6 items-center"
        style={{ borderColor: "var(--border-subtle)", background: "var(--surface-1)" }}
      >
        <div className="flex justify-center sm:justify-start">
          {overviewLoading ? (
            <div className="h-[168px] w-[168px] rounded-full skeleton" />
          ) : (
            <RadialGauge
              value={matchRatePct}
              label="Match rate"
              sublabel={`${overview?.total_matched_records ?? 0} of ${overview?.total_records_processed ?? 0} matched`}
            />
          )}
        </div>
        <div>
          <div className="flex items-center gap-3 flex-wrap">
            <span className="text-[10px] font-bold uppercase tracking-wider" style={{ color: "var(--accent)" }}>
              Reconciliation rate
            </span>
            {!overviewLoading && matchRateTrend !== null && (
              <TrendArrow delta={matchRateTrend} goodDirection="up" />
            )}
          </div>
          <p className="text-xs mt-1.5" style={{ color: "var(--text-secondary)" }}>
            Share of ingested records automatically or ML-recovered into a confirmed match across
            Payment Gateway, Ledger, and Bank feeds.
          </p>

          <div className="mt-4">
            <div className="text-[10px] font-bold uppercase tracking-wider mb-2" style={{ color: "var(--text-tertiary)" }}>
              Breakdown by issue cause
            </div>
            {breakdownLoading ? (
              <div className="h-[10px] w-full rounded-full skeleton" />
            ) : (
              <BreakdownBar segments={categoryBreakdown} />
            )}
          </div>
        </div>
      </div>

      {/* Data Provenance & Scope Distinction: Available vs Latest Run */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Available Records in System */}
        <div
          className="rounded-sm border p-4 text-[#eceae6] veridex-card-lift"
          style={{
            borderColor: "var(--border-subtle)",
            background: "var(--surface-1)",
          }}
        >
          <div className="flex items-center justify-between pb-2 border-b border-[#22272e]">
            <div>
              <span className="text-[10px] uppercase font-bold text-[#8e96a0] tracking-wider">
                Available Records in System
              </span>
              <p className="text-[11px] text-[#545e6a]">
                Ingested into repository and ready for matching
              </p>
            </div>
            <span className="text-base font-bold font-mono text-[#eceae6]">
              <CountUp value={txnsData?.total_count ?? transactions.length} format={(n) => Math.round(n).toString()} />{" "}
              <span className="text-xs text-[#8e96a0] font-normal">total</span>
            </span>
          </div>

          <div className="grid grid-cols-3 gap-2 pt-3 text-center">
            <div className="p-2 rounded-xs bg-[#111418] border border-[#22272e]">
              <div className="text-[10px] uppercase text-[#8e96a0] flex items-center justify-center gap-1">
                <CreditCard className="h-3 w-3 text-[#949da6]" /> Gateway
              </div>
              <div className="text-sm font-bold font-mono text-[#eceae6] mt-0.5">
                {transactions.filter((t) => (t.source || "").toLowerCase() === "gateway").length}
              </div>
            </div>
            <div className="p-2 rounded-xs bg-[#111418] border border-[#22272e]">
              <div className="text-[10px] uppercase text-[#8e96a0] flex items-center justify-center gap-1">
                <Receipt className="h-3 w-3 text-[#7eaa8e]" /> Ledger
              </div>
              <div className="text-sm font-bold font-mono text-[#eceae6] mt-0.5">
                {transactions.filter((t) => (t.source || "").toLowerCase() === "ledger").length}
              </div>
            </div>
            <div className="p-2 rounded-xs bg-[#111418] border border-[#22272e]">
              <div className="text-[10px] uppercase text-[#8e96a0] flex items-center justify-center gap-1">
                <Building2 className="h-3 w-3 text-[#ab9f90]" /> Bank
              </div>
              <div className="text-sm font-bold font-mono text-[#eceae6] mt-0.5">
                {transactions.filter((t) => (t.source || "").toLowerCase() === "bank").length}
              </div>
            </div>
          </div>
        </div>

        {/* Latest Reconciliation Run */}
        <div
          className="rounded-sm border p-4 text-[#eceae6] veridex-card-lift"
          style={{
            borderColor: "var(--border-subtle)",
            background: "var(--surface-1)",
          }}
        >
          {runsData?.runs && runsData.runs.length > 0 ? (
            (() => {
              const latest = runsData.runs[0];
              return (
                <div>
                  <div className="flex items-center justify-between pb-2 border-b border-[#22272e]">
                    <div>
                      <span className="text-[10px] uppercase font-bold text-[#c9a96e] tracking-wider">
                        Latest Reconciliation Run
                      </span>
                      <p className="text-[11px] text-[#545e6a]">
                        Outcome from the most recent run
                      </p>
                    </div>
                    <StatusBadge status={latest.status} />
                  </div>

                  <div className="grid grid-cols-3 gap-2 pt-3 text-center">
                    <div className="p-2 rounded-xs bg-[#111418] border border-[#22272e]">
                      <div className="text-[10px] uppercase text-[#8e96a0]">Matched</div>
                      <div className="text-sm font-bold font-mono text-[#6ecba0] mt-0.5">
                        {latest.match_count}
                      </div>
                    </div>
                    <div className="p-2 rounded-xs bg-[#111418] border border-[#22272e]">
                      <div className="text-[10px] uppercase text-[#8e96a0]">Need Attention</div>
                      <div className="text-sm font-bold font-mono text-[#e07070] mt-0.5">
                        {latest.exception_count}
                      </div>
                    </div>
                    <div className="p-2 rounded-xs bg-[#111418] border border-[#22272e]">
                      <div className="text-[10px] uppercase text-[#8e96a0]">Run Reference</div>
                      <div className="mt-0.5">
                        <TechnicalReference id={latest.run_id} maxVisible={12} inline />
                      </div>
                    </div>
                  </div>
                </div>
              );
            })()
          ) : (
            <div className="flex flex-col items-center justify-center py-5 text-center">
              <span className="text-xs text-[#8e96a0]">No reconciliation runs completed yet.</span>
              <p className="text-[11px] text-[#545e6a] mt-1">
                Click &ldquo;Run reconciliation&rdquo; to process the available records.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Historical Runs Summary Table */}
      <div
        className="rounded-sm border p-6 text-[#eceae6] veridex-card-lift"
        style={{
          borderColor: "var(--border-subtle)",
          background: "var(--surface-1)",
        }}
      >
        <div
          className="flex items-center justify-between pb-4"
          style={{ borderBottom: "1px solid var(--border-subtle)" }}
        >
          <h2 className="text-xs font-bold uppercase tracking-wider text-[#8e96a0] flex items-center gap-2">
            <Layers className="h-4 w-4 text-[#c9a96e]" />
            Reconciliation run history
          </h2>
          <span className="text-xs font-mono text-[#545e6a]">
            {runsData?.total_count || 0} runs recorded
          </span>
        </div>

        {runsLoading ? (
          <div className="pt-4">
            <LoadingSkeleton variant="table" count={3} />
          </div>
        ) : !runsData?.runs || runsData.runs.length === 0 ? (
          <EmptyState
            title="No Reconciliation Runs Found"
            description="Run a new batch using the top button to trigger ingestion and 3-way matching."
          />
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
                  <th className="py-2.5 px-3">Run Identifier</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Gateway Feed</th>
                  <th className="py-2.5 px-3">Ledger Feed</th>
                  <th className="py-2.5 px-3">Bank Feed</th>
                  <th className="py-2.5 px-3 text-right">Matched</th>
                  <th className="py-2.5 px-3 text-right">Exceptions</th>
                  <th className="py-2.5 px-3 text-right">Started</th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: "var(--border-subtle)" }}>
                {runsData.runs.map((run, idx) => (
                  <tr
                    key={run.id ? `${run.id}-${idx}` : `run-${idx}`}
                    className="hover:bg-[#13161a] transition-micro"
                  >
                    <td className="py-3 px-3">
                      <TechnicalReference id={run.run_id} maxVisible={22} />
                    </td>
                    <td className="py-3 px-3">
                      <StatusBadge status={run.status} />
                    </td>
                    <td className="py-3 px-3 text-[#8e96a0] font-mono">{run.gateway_count} txns</td>
                    <td className="py-3 px-3 text-[#8e96a0] font-mono">{run.ledger_count} txns</td>
                    <td className="py-3 px-3 text-[#8e96a0] font-mono">{run.bank_count} txns</td>
                    <td className="py-3 px-3 text-right font-mono font-bold text-[#6ecba0] font-tabular">
                      {run.match_count}
                    </td>
                    <td className="py-3 px-3 text-right font-mono font-bold text-[#e07070] font-tabular">
                      {run.exception_count > 0 ? (
                        <Link
                          href={`/exceptions?run_id=${encodeURIComponent(run.run_id)}`}
                          className="hover:underline hover:text-[#f08888] transition-colors"
                          title="View scoped exceptions"
                        >
                          {run.exception_count} →
                        </Link>
                      ) : (
                        run.exception_count
                      )}
                    </td>
                    <td className="py-3 px-3 text-right font-mono text-[#545e6a] text-[11px]">
                      {formatDateTime(run.started_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Multi-Source Raw Transactions Feed Table */}
      <div
        className="rounded-sm border p-6 text-[#eceae6] veridex-card-lift"
        style={{
          borderColor: "var(--border-subtle)",
          background: "var(--surface-1)",
        }}
      >
        <div
          className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4"
          style={{ borderBottom: "1px solid var(--border-subtle)" }}
        >
          <div>
            <h2 className="text-xs font-bold uppercase tracking-wider text-[#8e96a0]">
              Feed records in system
            </h2>
            <p className="text-xs text-[#545e6a] mt-0.5">
              Available records across all feeds ({filteredTxns.length} total
              {filteredTxns.length > 0 &&
                ` · showing ${(currentFeedPage - 1) * FEED_PAGE_SIZE + 1}–${Math.min(currentFeedPage * FEED_PAGE_SIZE, filteredTxns.length)}`}
              )
            </p>
          </div>

          {/* Filter Pills */}
          <div
            className="flex items-center gap-1 p-1 rounded-xs border text-xs"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-2)",
            }}
          >
            {["all", "gateway", "ledger", "bank"].map((src) => (
              <button
                key={src}
                onClick={() => handleSourceFilterChange(src)}
                className={cn(
                  "px-2.5 py-1 rounded-xs text-xs font-medium transition-micro uppercase",
                  sourceFilter === src
                    ? "font-semibold text-[#eceae6]"
                    : "text-[#8e96a0] hover:text-[#eceae6]"
                )}
                style={sourceFilter === src ? {
                  background: "var(--surface-3)",
                  border: "1px solid var(--border-standard)",
                } : {
                  border: "1px solid transparent",
                }}
              >
                {src}
              </button>
            ))}
          </div>
        </div>

        {txnsLoading ? (
          <div className="pt-4">
            <LoadingSkeleton variant="table" count={6} />
          </div>
        ) : txnsError ? (
          <ErrorState
            title="Failed to Load Ingested Transactions"
            message={txnsError instanceof Error ? txnsError.message : "Error connecting to backend"}
            onRetry={refetchTxns}
          />
        ) : filteredTxns.length === 0 ? (
          <EmptyState
            title="No Ingested Records Found"
            description="Run a reconciliation batch to ingest records from configured data sources."
          />
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
                  <th className="py-2.5 px-3">Transaction ID</th>
                  <th className="py-2.5 px-3">Source</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Amount</th>
                  <th className="py-2.5 px-3 text-right">Timestamp</th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: "var(--border-subtle)" }}>
                {pagedTxns.map((t, idx) => {
                  const txnId = t.domain_transaction_id || t.id || `raw-txn-${idx}`;
                  return (
                    <tr
                      key={txnId}
                      className="hover:bg-[#13161a] transition-micro"
                    >
                      <td className="py-3 px-3 font-mono font-medium text-[#eceae6]">
                        {txnId}
                      </td>
                      <td className="py-3 px-3">
                        <div className="flex items-center gap-1.5 capitalize text-[#8e96a0]">
                          {getSourceIcon(t.source)}
                          <span>{t.source}</span>
                        </div>
                      </td>
                      <td className="py-3 px-3">
                        <StatusBadge status={t.status} />
                      </td>
                      <td className="py-3 px-3 text-right font-mono font-bold font-tabular text-[#eceae6]">
                        {formatINR(t.amount)}
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-[#545e6a] text-[11px]">
                        {formatDateTime(t.timestamp)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination — the table previously hardcoded `.slice(0, 30)` with
            no way to reach anything past the first page regardless of how
            many records matched the active filter. */}
        {!txnsLoading && !txnsError && filteredTxns.length > FEED_PAGE_SIZE && (
          <div
            className="flex items-center justify-between pt-4 mt-2"
            style={{ borderTop: "1px solid var(--border-subtle)" }}
          >
            <span className="text-[11px] text-[#545e6a] font-mono">
              Page {currentFeedPage} of {feedTotalPages}
            </span>
            <div className="flex items-center gap-1.5">
              <button
                onClick={() => setFeedPage((p) => Math.max(1, p - 1))}
                disabled={currentFeedPage <= 1}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xs text-xs font-medium border transition-micro disabled:opacity-40 disabled:cursor-not-allowed"
                style={{ borderColor: "var(--border-standard)", background: "var(--surface-2)", color: "#eceae6" }}
              >
                <ChevronLeft className="h-3.5 w-3.5" />
                Prev
              </button>
              <button
                onClick={() => setFeedPage((p) => Math.min(feedTotalPages, p + 1))}
                disabled={currentFeedPage >= feedTotalPages}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xs text-xs font-medium border transition-micro disabled:opacity-40 disabled:cursor-not-allowed"
                style={{ borderColor: "var(--border-standard)", background: "var(--surface-2)", color: "#eceae6" }}
              >
                Next
                <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Batch Execution Modal */}
      {isBatchModalOpen && (
        <RunBatchModal
          isOpen={isBatchModalOpen}
          onClose={() => setIsBatchModalOpen(false)}
        />
      )}
    </div>
  );
}
