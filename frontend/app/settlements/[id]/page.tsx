"use client";

import React from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { settlementsApi } from "@/lib/api/settlementsApi";
import { formatINR, formatDateTime } from "@/lib/utils/formatters";
import { SettlementDecomposition } from "@/components/settlements/SettlementDecomposition";
import { TechnicalReference } from "@/components/common/TechnicalReference";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { ErrorState } from "@/components/common/ErrorState";
import {
  ArrowLeft,
  FileCheck,
  CreditCard,
  Building2,
  Receipt,
  FileText,
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
    <div className="space-y-6 pb-16 select-none">
      {/* Breadcrumb & Navigation */}
      <div
        className="flex flex-wrap items-center justify-between gap-4 pb-3"
        style={{ borderBottom: "1px solid var(--border-subtle)" }}
      >
        <div className="flex items-center gap-2 text-xs font-mono text-[#8e96a0]">
          <Link href="/app" className="hover:text-[#c9a96e] transition-colors">
            Control Center
          </Link>
          <span>/</span>
          <Link href="/settlements" className="hover:text-[#c9a96e] transition-colors">
            Settlements
          </Link>
          <span>/</span>
          <span className="text-[#eceae6] font-semibold">{id}</span>
        </div>

        <div className="flex items-center gap-3">
          <Link
            href="/settlements"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xs text-xs font-medium border text-[#eceae6] hover:bg-[#161a20] transition-micro"
            style={{
              borderColor: "var(--border-standard)",
              background: "var(--surface-1)",
            }}
          >
            <ArrowLeft className="h-3.5 w-3.5 text-[#8e96a0]" />
            <span>Back to Settlements</span>
          </Link>

          <Link
            href={`/settlements/${encodeURIComponent(id)}/tax-audit`}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xs text-xs font-bold transition-micro"
            style={{
              color: "var(--bg)",
              background: "var(--accent)",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "var(--accent-hover)")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "var(--accent)")}
          >
            <FileCheck className="h-3.5 w-3.5" />
            <span>Inspect Statutory Tax Line Audit</span>
          </Link>
        </div>
      </div>

      {/* 1. Financial Decomposition Waterfall (GROSS - FEE - TAX + ADJ = EXPECTED NET vs BANK RECEIVED -> VARIANCE) */}
      <SettlementDecomposition
        breakdown={breakdown}
        isLoading={breakdownLoading}
      />

      {/* 2. Linked Payments in Settlement Batch */}
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
            <div className="text-xs text-[#8e96a0] mt-1 flex items-center gap-2">
              <span>UTR Reference:</span>
              <strong className="text-[#eceae6] font-mono">
                {linkage?.utr ? (
                  <TechnicalReference id={linkage.utr} label="UTR" maxVisible={22} inline />
                ) : (
                  "N/A (Pending Credit)"
                )}
              </strong>
              <span>·</span>
              <span>Payments Count:</span>
              <strong className="text-[#eceae6] font-mono">
                {linkage?.total_payments_count || 0}
              </strong>
            </div>
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
                  <th className="py-2.5 px-3 text-right">Captured At</th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: "var(--border-subtle)" }}>
                {linkage.payments.map((p, idx) => (
                  <tr
                    key={p.payment_id ? `${p.payment_id}-${idx}` : `pay-${idx}`}
                    className="hover:bg-[#13161a] transition-micro"
                  >
                    <td className="py-3 px-3">
                      <TechnicalReference id={p.payment_id} maxVisible={22} />
                    </td>
                    <td className="py-3 px-3">
                      {p.order_id ? (
                        <TechnicalReference id={p.order_id} label="ord" maxVisible={20} inline />
                      ) : (
                        <span className="text-[#545e6a] text-[11px]">—</span>
                      )}
                    </td>
                    <td className="py-3 px-3">
                      <span className="px-2 py-0.5 rounded-xs text-[10px] font-mono font-semibold text-[#6ecba0] bg-[#1a3328] border border-[#2a6648]">
                        {(p.status || "captured").toUpperCase()}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-right font-mono font-medium font-tabular text-[#eceae6]">
                      {formatINR(p.amount)}
                    </td>
                    <td className="py-3 px-3 text-right font-mono text-[#e07070] font-tabular">
                      {formatINR(p.fee || 0)}
                    </td>
                    <td className="py-3 px-3 text-right font-mono text-[#e07070] font-tabular">
                      {formatINR(p.tax || 0)}
                    </td>
                    <td className="py-3 px-3 text-right font-mono text-[#8e96a0] text-[11px]">
                      {p.timestamp ? formatDateTime(p.timestamp) : "—"}
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
