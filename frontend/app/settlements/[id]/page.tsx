"use client";

import React from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { settlementsApi } from "@/lib/api/settlementsApi";
import { formatINR, formatDateTime } from "@/lib/utils/formatters";
import { SettlementDecomposition } from "@/components/settlements/SettlementDecomposition";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { ErrorState } from "@/components/common/ErrorState";
import {
  ArrowLeft,
  FileCheck,
  CreditCard,
} from "lucide-react";

export default function SettlementDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Array.isArray(params?.id) ? params.id[0] : (params?.id as string);

  // Financial Breakdown Query
  const {
    data: breakdown,
    isLoading: breakdownLoading,
    error: breakdownError,
    refetch,
  } = useQuery({
    queryKey: ["settlement-breakdown", id],
    queryFn: () => settlementsApi.getFinancialBreakdown(id),
    enabled: !!id,
  });

  // Linked Transactions Query
  const {
    data: linkage,
    isLoading: linkageLoading,
  } = useQuery({
    queryKey: ["settlement-transactions", id],
    queryFn: () => settlementsApi.getTransactionLinkage(id),
    enabled: !!id,
  });

  if (breakdownError) {
    return (
      <ErrorState
        title="Failed to Load Settlement Breakdown"
        message={breakdownError instanceof Error ? breakdownError.message : "Error connecting to backend"}
        onRetry={refetch}
      />
    );
  }

  return (
    <div className="space-y-6 pb-12 select-none">
      {/* Breadcrumb & Navigation */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <Link
            href="/settlements"
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xs text-xs transition-micro text-[#8e96a0] hover:text-[#eceae6]"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-2)",
              border: "1px solid var(--border-subtle)",
            }}
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Back to Settlements
          </Link>
          <span style={{ color: "var(--text-tertiary)" }}>/</span>
          <span className="text-xs text-[#8e96a0]">Settlement:</span>
          <span className="text-xs font-mono font-semibold text-[#eceae6]">{id}</span>
        </div>

        <Link
          href={`/settlements/${encodeURIComponent(id)}/tax-audit`}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xs font-semibold text-xs transition-micro"
          style={{
            color: "#080a0c",
            background: "var(--accent)",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "var(--accent-hover)")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "var(--accent)")}
        >
          <FileCheck className="h-3.5 w-3.5" />
          <span>Inspect Statutory Tax Line Audit</span>
        </Link>
      </div>

      {/* Financial Decomposition Component */}
      <SettlementDecomposition
        breakdown={breakdown}
        isLoading={breakdownLoading}
      />

      {/* Linked Transactions Table */}
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
          <div>
            <h2 className="text-xs font-bold uppercase tracking-wider text-[#8e96a0] flex items-center gap-2">
              <CreditCard className="h-4 w-4 text-[#c9a96e]" />
              Linked Gateway Payments in Batch
            </h2>
            <p className="text-xs text-[#8e96a0] mt-0.5">
              UTR Reference: <strong className="text-[#eceae6] font-mono">{linkage?.utr || "N/A"}</strong> | Payments Count:{" "}
              <strong className="text-[#eceae6] font-mono">{linkage?.total_payments_count || 0}</strong>
            </p>
          </div>
        </div>

        {linkageLoading ? (
          <div className="pt-4">
            <LoadingSkeleton variant="table" count={3} />
          </div>
        ) : !linkage?.payments || linkage.payments.length === 0 ? (
          <div className="py-8 text-center text-[#8e96a0] text-xs">
            No linked individual transaction items found for this settlement batch.
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
                  <th className="py-2.5 px-3">Payment ID</th>
                  <th className="py-2.5 px-3">Internal Order ID</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3 text-right">Gross Amount</th>
                  <th className="py-2.5 px-3 text-right">Fee (MDR)</th>
                  <th className="py-2.5 px-3 text-right">Tax</th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: "var(--border-subtle)" }}>
                {linkage.payments.map((p, idx) => (
                  <tr
                    key={p.payment_id ? `${p.payment_id}-${idx}` : `pay-item-${idx}`}
                    className="hover:bg-[#13161a] transition-micro"
                  >
                    <td className="py-3 px-3 font-mono font-semibold text-[#eceae6]">
                      {p.payment_id}
                    </td>
                    <td className="py-3 px-3 font-mono text-[#8e96a0]">
                      {p.order_id || "N/A"}
                    </td>
                    <td className="py-3 px-3">
                      <span className="font-mono text-[10px] font-semibold text-[#6ecba0] uppercase">
                        {p.status || "CAPTURED"}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-right font-mono font-bold font-tabular text-[#eceae6]">
                      {formatINR(p.amount)}
                    </td>
                    <td className="py-3 px-3 text-right font-mono text-[#e07070] font-tabular">
                      {formatINR(p.fee || 0)}
                    </td>
                    <td className="py-3 px-3 text-right font-mono text-[#d4a84e] font-tabular">
                      {formatINR(p.tax || 0)}
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
