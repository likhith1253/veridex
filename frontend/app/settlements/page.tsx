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
  CheckCircle2,
  Clock,
  AlertTriangle,
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

  const getWorkflowStateBadge = (s: any) => {
    const rawStatus = (s.status || "").toUpperCase();
    const hasBankCredit = s.bank_received_amount !== null && s.bank_received_amount !== undefined;
    const variance = Math.abs(parseFloat(String(s.variance ?? 0)));

    if (variance > 0) {
      return (
        <span
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-xs text-[10px] font-mono font-bold"
          style={{
            color: "var(--variance-text)",
            background: "var(--variance-bg)",
            border: "1px solid var(--variance-border)",
          }}
        >
          <AlertTriangle className="h-3 w-3" /> EXCEPTION
        </span>
      );
    }
    if (rawStatus === "RECONCILED" || (hasBankCredit && variance === 0)) {
      return (
        <span
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-xs text-[10px] font-mono font-bold"
          style={{
            color: "var(--matched-text)",
            background: "var(--matched-bg)",
            border: "1px solid var(--matched-border)",
          }}
        >
          <CheckCircle2 className="h-3 w-3" /> RECONCILED
        </span>
      );
    }
    if (hasBankCredit) {
      return (
        <span
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-xs text-[10px] font-mono font-bold text-[#6ecba0] bg-[#1a3328] border border-[#2a6648]"
        >
          <CheckCircle2 className="h-3 w-3" /> BANK CREDIT CONFIRMED
        </span>
      );
    }
    if (s.utr || rawStatus === "SETTLED" || rawStatus === "PROCESSED") {
      return (
        <span
          className="inline-flex items-center gap-1 px-2 py-0.5 rounded-xs text-[10px] font-mono font-bold text-[#d4a84e] bg-[#2d2516] border border-[#524122]"
        >
          <Clock className="h-3 w-3" /> BANK CREDIT PENDING
        </span>
      );
    }
    return (
      <span
        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-xs text-[10px] font-mono font-bold text-[#8e96a0] bg-[#1c2128] border border-[#2d333b]"
      >
        PROCESSING
      </span>
    );
  };

  return (
    <div className="space-y-6 pb-12 select-none">
      {/* Breadcrumb Context */}
      <div className="flex items-center gap-2 text-xs font-mono text-[#8e96a0] pb-1">
        <Link href="/app" className="hover:text-[#c9a96e] transition-colors">
          Control Center
        </Link>
        <span>/</span>
        <span className="text-[#eceae6] font-semibold">Settlements</span>
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
            Check settlements
          </span>
          <h1 className="text-xl font-bold tracking-tight text-[#eceae6] mt-0.5">
            Expected payout vs Bank received
          </h1>
          <p className="text-xs text-[#8e96a0] mt-0.5">
            Track payouts, gateway fees, tax deductions, and bank credit confirmation
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
            <Landmark className="h-4 w-4 text-[#c9a96e]" />
            Settlement Payout Batches
          </h2>
          <span className="text-xs text-[#545e6a]">
            Lifecycle Parity: Expected Net vs Core Banking Credit
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
            description="Settlement records come specifically from Razorpay Gateway sync (webhook or manual sync), not from generic reconciliation batches. Sync from the Razorpay Gateway page to populate this view."
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
                  <th className="py-2.5 px-3">Settlement &amp; UTR</th>
                  <th className="py-2.5 px-3 text-right">Gross Amount</th>
                  <th className="py-2.5 px-3 text-right">Expected Net</th>
                  <th className="py-2.5 px-3 text-right">Bank Received</th>
                  <th className="py-2.5 px-3 text-right">Variance</th>
                  <th className="py-2.5 px-3 text-center">Current State</th>
                  <th className="py-2.5 px-3 text-right">Next Action</th>
                </tr>
              </thead>
              <tbody className="divide-y" style={{ borderColor: "var(--border-subtle)" }}>
                {settlements.map((s, idx) => {
                  const setlId = s.settlement_id || `setl-${idx}`;
                  const gross = parseFloat(String(s.gross_amount || s.amount || 0));
                  const expNet = parseFloat(String(s.expected_net_amount ?? s.amount ?? 0));
                  const received =
                    s.bank_received_amount !== null && s.bank_received_amount !== undefined
                      ? parseFloat(String(s.bank_received_amount))
                      : null;
                  const variance =
                    received !== null
                      ? Math.abs(expNet - received)
                      : s.variance !== undefined && s.variance !== null
                      ? Math.abs(parseFloat(String(s.variance)))
                      : null;

                  return (
                    <tr
                      key={setlId ? `${setlId}-${idx}` : `settlement-${idx}`}
                      className="hover:bg-[#13161a] transition-micro"
                    >
                      <td className="py-3 px-3">
                        <div className="space-y-1">
                          <TechnicalReference id={setlId} maxVisible={22} />
                          <div>
                            {s.utr ? (
                              <TechnicalReference id={s.utr} label="UTR" maxVisible={22} inline />
                            ) : (
                              <span className="text-[#545e6a] text-[10px] italic">
                                UTR Pending Credit
                              </span>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="py-3 px-3 text-right font-mono font-medium font-tabular text-[#8e96a0]">
                        {formatINR(gross)}
                      </td>
                      <td className="py-3 px-3 text-right font-mono font-bold font-tabular text-[#eceae6]">
                        {formatINR(expNet)}
                      </td>
                      <td className="py-3 px-3 text-right font-mono font-medium font-tabular">
                        {received !== null ? (
                          <span className="text-[#6ecba0] font-bold">{formatINR(received)}</span>
                        ) : (
                          <span className="text-[#545e6a] text-[11px] italic">Pending Bank Confirmation</span>
                        )}
                      </td>
                      <td className="py-3 px-3 text-right font-mono font-tabular">
                        {variance !== null ? (
                          variance === 0 ? (
                            <span className="text-[#6ecba0] font-bold">₹0.00</span>
                          ) : (
                            <span className="text-[#e07070] font-bold">{formatINR(variance)}</span>
                          )
                        ) : (
                          <span className="text-[#545e6a] text-[11px]">—</span>
                        )}
                      </td>
                      <td className="py-3 px-3 text-center">
                        {getWorkflowStateBadge(s)}
                      </td>
                      <td className="py-3 px-3 text-right">
                        <Link
                          href={`/settlements/${encodeURIComponent(setlId)}`}
                          className="inline-flex items-center gap-1 text-[11px] font-semibold text-[#c9a96e] hover:text-[#e4caa0] transition-micro"
                        >
                          <span>Breakdown</span>
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
