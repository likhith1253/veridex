"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { controllerApi } from "@/lib/api/controllerApi";
import { formatINR, cn } from "@/lib/utils/formatters";
import { StatusBadge } from "@/components/common/StatusBadge";
import { ConfidenceBadge } from "@/components/common/ConfidenceBadge";
import { TechnicalReference } from "@/components/common/TechnicalReference";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import {
  AlertOctagon,
  Search,
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  Database,
  Filter,
} from "lucide-react";

function ExceptionsContent() {
  const searchParams = useSearchParams();

  // Initialize filters from URL params - default to OPEN exceptions
  const [statusFilter, setStatusFilter] = useState<string>(
    () => searchParams.get("status") || "open"
  );
  const [categoryFilter, setCategoryFilter] = useState<string>(
    () => searchParams.get("category") || "all"
  );
  const [agingFilter, setAgingFilter] = useState<string | null>(null);
  const [runIdFilter] = useState<string | null>(
    () => searchParams.get("run_id")
  );
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedExceptionId, setSelectedExceptionId] = useState<string | null>(null);
  const [page, setPage] = useState<number>(1);
  const pageSize = 15;

  // Exceptions Query
  const {
    data: exceptionsData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["exceptions-queue", statusFilter, categoryFilter, runIdFilter, searchQuery, page],
    queryFn: () =>
      controllerApi.getExceptions({
        status: statusFilter === "all" ? undefined : statusFilter,
        category: categoryFilter === "all" ? undefined : categoryFilter,
        run_id: runIdFilter || undefined,
        transaction_id: searchQuery ? searchQuery : undefined,
        page,
        page_size: pageSize,
      }),
    refetchInterval: 15000,
  });

  // Exception Aging Metrics Query
  const { data: aging } = useQuery({
    queryKey: ["exceptions-aging"],
    queryFn: () => controllerApi.getExceptionAging(),
    staleTime: 30000,
  });

  const rawExceptions = exceptionsData?.exceptions || [];
  const totalCount = exceptionsData?.total_count || 0;
  const totalPages = Math.ceil(totalCount / pageSize) || 1;

  // Client-side aging filter if active
  const exceptions = agingFilter
    ? rawExceptions.filter((e) => {
        const hours = (e as any).age_hours ?? 12;
        if (agingFilter === "0_24h") return hours <= 24;
        if (agingFilter === "24_48h") return hours > 24 && hours <= 48;
        if (agingFilter === "48_72h") return hours > 48 && hours <= 72;
        if (agingFilter === "72h_plus") return hours > 72;
        return true;
      })
    : rawExceptions;

  const selectedException =
    exceptions.find((e) => (e.exception_id || e.id) === selectedExceptionId) ||
    exceptions[0];

  return (
    <div className="space-y-6 pb-12 select-none">
      {/* Breadcrumb Context */}
      <div className="flex items-center gap-2 text-xs font-mono text-[#8e96a0] pb-1">
        <Link href="/app" className="hover:text-[#c9a96e] transition-colors">
          Control Center
        </Link>
        <span>/</span>
        <span className="text-[#eceae6] font-semibold">Exceptions</span>
      </div>

      {/* Run scope indicator — shown when drill-down came from a specific run */}
      {runIdFilter && (
        <div
          className="flex items-center gap-2 text-xs font-mono px-3 py-2 rounded-xs border"
          style={{
            borderColor: "var(--accent-border)",
            background: "var(--accent-dim)",
          }}
        >
          <Filter className="h-3.5 w-3.5 text-[#c9a96e]" />
          <span className="text-[#c9a96e] font-semibold">Scoped to Run:</span>
          <TechnicalReference id={runIdFilter} maxVisible={28} />
        </div>
      )}

      {/* Header */}
      <div
        className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4"
        style={{ borderBottom: "1px solid var(--border-subtle)" }}
      >
        <div>
          <span
            className="text-[10px] font-semibold uppercase tracking-[0.14em]"
            style={{ color: "var(--accent)" }}
          >
            Forensic Exceptions Queue
          </span>
          <h1 className="text-xl font-bold tracking-tight text-[#eceae6] mt-0.5">
            Analyst Workbench &amp; Root-Cause Triage
          </h1>
          <p className="text-xs text-[#8e96a0] mt-0.5">
            Root-cause model scoring, monetary exposure tracking, and policy-gated action routing
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-[#8e96a0]">
            {statusFilter === "open"
              ? "Open Queue:"
              : statusFilter === "resolved"
              ? "Resolved Archive:"
              : statusFilter === "investigating"
              ? "Under Investigation:"
              : "Total Exceptions (All Statuses):"}
          </span>
          <span
            className="font-mono text-xs font-bold px-2.5 py-1 rounded-xs"
            style={{
              color: statusFilter === "resolved" ? "var(--success-text)" : "var(--variance-text)",
              background: statusFilter === "resolved" ? "var(--success-bg)" : "var(--variance-bg)",
              border: statusFilter === "resolved" ? "1px solid var(--success-border)" : "1px solid var(--variance-border)",
            }}
          >
            {totalCount} Cases
          </span>
        </div>
      </div>

      {/* Exception Aging SLA Infobar — Interactive Drill-Down Cards */}
      {aging && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 text-xs">
          <button
            onClick={() => setAgingFilter(agingFilter === "0_24h" ? null : "0_24h")}
            className={cn(
              "p-3.5 rounded-xs border text-left transition-micro",
              agingFilter === "0_24h" && "ring-1 ring-[#c9a96e]"
            )}
            style={{
              borderColor: agingFilter === "0_24h" ? "var(--accent)" : "var(--border-subtle)",
              background: agingFilter === "0_24h" ? "var(--accent-dim)" : "var(--surface-1)",
            }}
          >
            <div className="text-[10px] uppercase font-semibold text-[#8e96a0]">0 - 24 Hours Aging</div>
            <div className="mt-1 text-lg font-bold font-mono text-[#6ecba0] font-tabular">
              {aging.bucket_0_24h}
            </div>
            <div className="text-[10px] text-[#545e6a] mt-0.5">
              {agingFilter === "0_24h" ? "Filter Active ✓" : "Within standard SLA"}
            </div>
          </button>

          <button
            onClick={() => setAgingFilter(agingFilter === "24_48h" ? null : "24_48h")}
            className={cn(
              "p-3.5 rounded-xs border text-left transition-micro",
              agingFilter === "24_48h" && "ring-1 ring-[#c9a96e]"
            )}
            style={{
              borderColor: agingFilter === "24_48h" ? "var(--accent)" : "var(--border-subtle)",
              background: agingFilter === "24_48h" ? "var(--accent-dim)" : "var(--surface-1)",
            }}
          >
            <div className="text-[10px] uppercase font-semibold text-[#8e96a0]">24 - 48 Hours Aging</div>
            <div className="mt-1 text-lg font-bold font-mono text-[#d4a84e] font-tabular">
              {aging.bucket_24_48h}
            </div>
            <div className="text-[10px] text-[#545e6a] mt-0.5">
              {agingFilter === "24_48h" ? "Filter Active ✓" : "Under investigation"}
            </div>
          </button>

          <button
            onClick={() => setAgingFilter(agingFilter === "48_72h" ? null : "48_72h")}
            className={cn(
              "p-3.5 rounded-xs border text-left transition-micro",
              agingFilter === "48_72h" && "ring-1 ring-[#c9a96e]"
            )}
            style={{
              borderColor: agingFilter === "48_72h" ? "var(--accent)" : "var(--border-subtle)",
              background: agingFilter === "48_72h" ? "var(--accent-dim)" : "var(--surface-1)",
            }}
          >
            <div className="text-[10px] uppercase font-semibold text-[#8e96a0]">48 - 72 Hours Aging</div>
            <div className="mt-1 text-lg font-bold font-mono text-[#e07070] font-tabular">
              {aging.bucket_48_72h}
            </div>
            <div className="text-[10px] text-[#545e6a] mt-0.5">
              {agingFilter === "48_72h" ? "Filter Active ✓" : "SLA escalation watch"}
            </div>
          </button>

          <button
            onClick={() => setAgingFilter(agingFilter === "72h_plus" ? null : "72h_plus")}
            className={cn(
              "p-3.5 rounded-xs border text-left transition-micro",
              agingFilter === "72h_plus" && "ring-1 ring-[#e07070]"
            )}
            style={{
              borderColor: "var(--variance-border)",
              background: "var(--variance-bg)",
              borderLeft: "3px solid var(--variance)",
            }}
          >
            <div className="text-[10px] uppercase font-semibold text-[#e07070]">72+ Hours (Critical SLA)</div>
            <div className="mt-1 text-lg font-bold font-mono text-[#e07070] font-tabular">
              {aging.bucket_72h_plus}
            </div>
            <div className="text-[10px] text-[#e07070] mt-0.5">
              {agingFilter === "72h_plus" ? "Filter Active ✓" : "Priority resolution required"}
            </div>
          </button>
        </div>
      )}

      {/* Filter & Search Bar */}
      <div
        className="rounded-sm border p-3 flex flex-col md:flex-row items-center justify-between gap-3 text-xs"
        style={{
          borderColor: "var(--border-subtle)",
          background: "var(--surface-1)",
        }}
      >
        {/* Search */}
        <div className="relative w-full md:w-80">
          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-[#545e6a]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              setPage(1);
            }}
            placeholder="Search by Transaction ID / Reference..."
            className="w-full rounded-xs border pl-9 pr-3 py-1.5 font-mono text-xs text-[#eceae6] placeholder-[#545e6a] transition-micro focus:outline-hidden"
            style={{
              borderColor: "var(--border-standard)",
              background: "var(--surface-2)",
            }}
          />
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
          {/* Status Segmented Buttons */}
          <div className="flex items-center gap-1 p-0.5 rounded-xs border border-[#262A30] bg-[#121417]">
            <button
              type="button"
              onClick={() => {
                setStatusFilter("open");
                setPage(1);
              }}
              className={cn(
                "px-3 py-1 text-xs font-medium rounded-xs transition-micro",
                statusFilter === "open"
                  ? "bg-[#262A30] text-[#c9a96e] font-semibold shadow-xs"
                  : "text-[#8e96a0] hover:text-[#eceae6]"
              )}
            >
              OPEN
            </button>
            <button
              type="button"
              onClick={() => {
                setStatusFilter("resolved");
                setPage(1);
              }}
              className={cn(
                "px-3 py-1 text-xs font-medium rounded-xs transition-micro",
                statusFilter === "resolved"
                  ? "bg-[#262A30] text-[#6ecba0] font-semibold shadow-xs"
                  : "text-[#8e96a0] hover:text-[#eceae6]"
              )}
            >
              RESOLVED
            </button>
            <button
              type="button"
              onClick={() => {
                setStatusFilter("all");
                setPage(1);
              }}
              className={cn(
                "px-3 py-1 text-xs font-medium rounded-xs transition-micro",
                statusFilter === "all"
                  ? "bg-[#262A30] text-[#eceae6] font-semibold shadow-xs"
                  : "text-[#8e96a0] hover:text-[#eceae6]"
              )}
            >
              ALL
            </button>
          </div>

          <select
            value={categoryFilter}
            onChange={(e) => {
              setCategoryFilter(e.target.value);
              setPage(1);
            }}
            className="rounded-xs border px-3 py-1.5 text-xs text-[#eceae6] transition-micro focus:outline-hidden"
            style={{
              borderColor: "var(--border-standard)",
              background: "var(--surface-2)",
            }}
          >
            <option value="all">All Root Causes</option>
            <option value="amount_mismatch">Amount Mismatch</option>
            <option value="timing_delay">Timing Delay</option>
            <option value="fee_discrepancy">Fee Discrepancy</option>
            <option value="missing_source">Missing Source</option>
            <option value="duplicate">Duplicate Entry</option>
            <option value="unexplained">Unexplained</option>
          </select>

          {(statusFilter !== "open" || categoryFilter !== "all" || searchQuery || agingFilter) && (
            <button
              onClick={() => {
                setStatusFilter("open");
                setCategoryFilter("all");
                setAgingFilter(null);
                setSearchQuery("");
                setPage(1);
              }}
              className="text-xs text-[#c9a96e] hover:text-[#d8bc8a] transition-micro"
            >
              Reset Filters
            </button>
          )}
        </div>
      </div>

      {/* Main Workbench Layout: Queue Table (8 cols) + Selected Context Panel (4 cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Exceptions Queue Table */}
        <div
          className={cn(
            "rounded-sm border p-5 text-[#eceae6]",
            selectedException ? "lg:col-span-8" : "lg:col-span-12"
          )}
          style={{
            borderColor: "var(--border-subtle)",
            background: "var(--surface-1)",
          }}
        >
          <div
            className="flex items-center justify-between pb-3"
            style={{ borderBottom: "1px solid var(--border-subtle)" }}
          >
            <h2 className="text-xs font-bold uppercase tracking-wider text-[#8e96a0] flex items-center gap-2">
              <AlertOctagon className="h-4 w-4 text-[#e07070]" />
              <span>Queue Records</span>
              <span className="text-[10px] font-mono font-normal text-[#545e6a]">
                ({exceptions.length} visible of {totalCount} {statusFilter.toUpperCase()})
              </span>
            </h2>
            <span className="text-xs text-[#545e6a] font-mono">
              Page {page} of {totalPages}
            </span>
          </div>

          {isLoading ? (
            <div className="pt-4">
              <LoadingSkeleton variant="table" count={5} />
            </div>
          ) : error ? (
            <ErrorState
              title="Failed to Load Exceptions"
              message={error instanceof Error ? error.message : "Error connecting to backend"}
              onRetry={refetch}
            />
          ) : exceptions.length === 0 ? (
            <EmptyState
              title="No Matching Exceptions Found"
              description="Adjust filter parameters above or execute another reconciliation batch."
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
                    <th className="py-2.5 px-3">Exception ID</th>
                    <th className="py-2.5 px-3">Root Cause</th>
                    <th className="py-2.5 px-3">Status</th>
                    <th className="py-2.5 px-3 text-right">Exposure</th>
                    <th className="py-2.5 px-3 text-right">Confidence</th>
                    <th className="py-2.5 px-3 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y" style={{ borderColor: "var(--border-subtle)" }}>
                  {exceptions.map((ex, idx) => {
                    const excId = ex.exception_id || ex.id || `exc-${idx}`;
                    const cat = ex.category || ex.exception_category || "unexplained";
                    const exp = ex.financial_exposure_inr ?? ex.financial_exposure;
                    const isSelected =
                      selectedException &&
                      (selectedException.exception_id || selectedException.id) === excId;

                    return (
                      <tr
                        key={excId ? `${excId}-${idx}` : `exception-${idx}`}
                        onClick={() => setSelectedExceptionId(excId)}
                        className={cn(
                          "cursor-pointer transition-micro",
                          isSelected ? "bg-[#181c22]" : "hover:bg-[#13161a]"
                        )}
                        style={
                          isSelected
                            ? {
                                borderLeft: "2px solid var(--accent)",
                              }
                            : {
                                borderLeft: "2px solid transparent",
                              }
                        }
                      >
                        <td className="py-3 px-3">
                          <div className="font-medium text-xs text-[#eceae6] capitalize">
                            {cat.replace(/_/g, " ")}
                          </div>
                          <TechnicalReference
                            id={excId}
                            label="ref"
                            maxVisible={20}
                            inline
                            className="mt-0.5"
                          />
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
                          <ConfidenceBadge confidence={ex.confidence} />
                        </td>
                        <td className="py-3 px-3 text-right">
                          <Link
                            href={`/exceptions/${encodeURIComponent(excId)}`}
                            onClick={(e) => e.stopPropagation()}
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

          {/* Pagination */}
          {totalPages > 1 && (
            <div
              className="flex items-center justify-between pt-4 mt-4 text-xs font-mono"
              style={{ borderTop: "1px solid var(--border-subtle)" }}
            >
              <button
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xs border disabled:opacity-30 transition-micro text-[#eceae6]"
                style={{
                  borderColor: "var(--border-subtle)",
                  background: "var(--surface-2)",
                }}
              >
                <ChevronLeft className="h-3.5 w-3.5" /> Previous
              </button>
              <span className="text-[#8e96a0]">
                Page {page} of {totalPages}
              </span>
              <button
                disabled={page >= totalPages}
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xs border disabled:opacity-30 transition-micro text-[#eceae6]"
                style={{
                  borderColor: "var(--border-subtle)",
                  background: "var(--surface-2)",
                }}
              >
                Next <ChevronRight className="h-3.5 w-3.5" />
              </button>
            </div>
          )}
        </div>

        {/* Selected Context Panel */}
        {selectedException && (
          <div
            className="lg:col-span-4 rounded-sm border p-5 text-[#eceae6] space-y-4"
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
                <span className="text-xs font-bold text-[#eceae6]">
                  Workbench Detail
                </span>
              </div>
              <StatusBadge status={selectedException.status} />
            </div>

            <div className="space-y-4 text-xs">
              <div>
                <span className="text-[10px] text-[#545e6a] uppercase block mb-1">
                  Exception Reference
                </span>
                <TechnicalReference
                  id={selectedException.exception_id || selectedException.id || ""}
                  maxVisible={28}
                />
              </div>

              <div className="grid grid-cols-2 gap-3 font-mono">
                <div
                  className="p-3 rounded-xs border"
                  style={{
                    borderColor: "var(--variance-border)",
                    background: "var(--variance-bg)",
                  }}
                >
                  <span className="text-[10px] text-[#e07070] uppercase block">
                    Monetary Exposure
                  </span>
                  <span className="text-base font-bold font-tabular text-[#e07070] mt-1 block">
                    {formatINR(
                      selectedException.financial_exposure_inr ??
                        selectedException.financial_exposure
                    )}
                  </span>
                </div>

                <div
                  className="p-3 rounded-xs border"
                  style={{
                    borderColor: "var(--border-subtle)",
                    background: "var(--surface-2)",
                  }}
                >
                  <span className="text-[10px] text-[#8e96a0] uppercase block">
                    Expected Cost
                  </span>
                  <span className="text-base font-bold font-tabular text-[#eceae6] mt-1 block">
                    {formatINR(
                      selectedException.expected_cost_inr ??
                        selectedException.expected_cost ??
                        0
                    )}
                  </span>
                </div>
              </div>

              <div>
                <span className="text-[10px] text-[#8e96a0] uppercase block mb-1">
                  Diagnosis Rationale:
                </span>
                <p
                  className="p-3 rounded-xs border text-xs leading-relaxed text-[#eceae6]"
                  style={{
                    borderColor: "var(--border-subtle)",
                    background: "var(--surface-2)",
                  }}
                >
                  {selectedException.explanation || "Root-cause classification in progress."}
                </p>
              </div>

              <Link
                href={`/exceptions/${encodeURIComponent(
                  selectedException.exception_id || selectedException.id || ""
                )}`}
                className="w-full inline-flex items-center justify-center gap-2 px-4 py-2 rounded-xs font-semibold text-xs transition-micro"
                style={{
                  color: "#080a0c",
                  background: "var(--accent)",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = "var(--accent-hover)")}
                onMouseLeave={(e) => (e.currentTarget.style.background = "var(--accent)")}
              >
                <span>Open Forensic Dossier</span>
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ExceptionsPage() {
  return (
    <React.Suspense fallback={<div className="p-8"><LoadingSkeleton variant="table" /></div>}>
      <ExceptionsContent />
    </React.Suspense>
  );
}
