"use client";

import React from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { settlementsApi } from "@/lib/api/settlementsApi";
import { formatINR, formatDateTime } from "@/lib/utils/formatters";
import { StatusBadge } from "@/components/common/StatusBadge";
import { TechnicalReference } from "@/components/common/TechnicalReference";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import {
  Landmark,
  ArrowRight,
  FileCheck,
} from "lucide-react";

export default function SettlementsPage() {
  const {
    data: settlementsData,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["settlements-list"],
    queryFn: () => settlementsApi.getSettlements({ limit: 50 }),
    refetchInterval: 15000,
  });

  const settlements = settlementsData?.settlements || [];

  return (
    <div className="space-y-6 pb-12 select-none">
      {/* Breadcrumb Context */}
      <div className="flex items-center gap-2 text-xs font-mono text-[#6F747A] pb-1">
        <Link href="/app" className="hover:text-[#9E7B35] transition-colors">Control Center</Link>
        <span>/</span>
        <span className="text-[#17191C] font-semibold">Settlements</span>
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
            Settlement Intelligence
          </span>
          <h1 className="text-xl font-bold tracking-tight text-[#eceae6] mt-0.5">
            Settlement Payouts &amp; 3-Way Bank Parity
          </h1>
          <p className="text-xs text-[#8e96a0] mt-0.5">
            Automated gateway settlement decomposition, statutory tax-line audits, and UTR bank statement reconciliation
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-[#8e96a0]">Total Batches:</span>
          <span
            className="font-mono text-xs font-bold text-[#eceae6] px-2.5 py-1 rounded-xs border"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-2)",
            }}
          >
            {settlementsData?.total_count || settlements.length} Settlements
          </span>
        </div>
      </div>

      {/* Settlements Table */}
      <div
        className="rounded-sm border p-6 text-[#eceae6]"
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
            <Landmark className="h-4 w-4 text-[#c9a96e]" />
            Settlement Payout Batches
          </h2>
          <span className="text-xs text-[#545e6a]">
            Gateway Payouts &amp; Bank UTR Reference Parity
          </span>
        </div>

        {isLoading ? (
          <div className="pt-4">
            <LoadingSkeleton variant="table" count={5} />
          </div>
        ) : error ? (
          <ErrorState
            title="Failed to Load Settlements"
            message={error instanceof Error ? error.message : "Error connecting to backend"}
            onRetry={refetch}
          />
        ) : settlements.length === 0 ? (
          <EmptyState
            title="No Settlements Ingested"
            description="Sync payments and settlements from the Razorpay Gateway page or execute a reconciliation run."
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
                  <th className="py-2.5 px-3">Settlement ID</th>
                  <th className="py-2.5 px-3">Bank UTR Reference</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Net Amount</th>
                  <th className="py-2.5 px-3 text-right">Fees / Tax</th>
                  <th className="py-2.5 px-3 text-right">Created At</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: "var(--border-subtle)" }}>
                {settlements.map((s, idx) => {
                  const setlId = s.settlement_id || `setl-${idx}`;
                  return (
                    <tr
                      key={setlId ? `${setlId}-${idx}` : `settlement-${idx}`}
                      className="hover:bg-[#13161a] transition-micro"
                    >
                      <td className="py-3 px-3">
                        <TechnicalReference id={setlId} maxVisible={22} />
                      </td>
                      <td className="py-3 px-3">
                        {s.utr
                          ? <TechnicalReference id={s.utr} label="UTR" maxVisible={22} />
                          : <span className="text-[#545e6a] text-[11px] italic">Pending</span>
                        }
                      </td>
                      <td className="py-3 px-3">
                        <StatusBadge status={s.status} />
                      </td>
                      <td className="py-3 px-3 text-right font-mono font-bold font-tabular text-[#eceae6]">
                        {formatINR(s.expected_net_amount ?? s.amount)}
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-[#8e96a0] font-tabular text-[11px]">
                        {formatINR(s.fees ?? 0)} / {formatINR(s.tax ?? 0)}
                      </td>
                      <td className="py-3 px-3 text-right font-mono text-[#545e6a] text-[11px]">
                        {formatDateTime(s.settlement_date ?? s.created_at)}
                      </td>
                      <td className="py-3 px-3 text-right">
                        <Link
                          href={`/settlements/${encodeURIComponent(setlId)}`}
                          className="inline-flex items-center gap-1 px-2.5 py-1 rounded-xs text-xs font-medium transition-micro"
                          style={{
                            color: "var(--accent)",
                            background: "var(--accent-dim)",
                            border: "1px solid var(--accent-border)",
                          }}
                        >
                          <span>Inspect</span>
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
    </div>
  );
}
