"use client";

import React from "react";
import { formatINR, formatVariance, cn } from "@/lib/utils/formatters";
import type { SettlementFinancialBreakdown } from "@/types/settlements";
import { Minus, Plus, Equal, ArrowRight, ShieldCheck, AlertTriangle } from "lucide-react";

interface SettlementDecompositionProps {
  breakdown?: SettlementFinancialBreakdown | null;
  isLoading?: boolean;
}

export function SettlementDecomposition({
  breakdown,
  isLoading,
}: SettlementDecompositionProps) {
  if (isLoading || !breakdown) {
    return (
      <div
        className="rounded-sm border p-6 animate-pulse"
        style={{
          borderColor: "var(--border-subtle)",
          background: "var(--surface-1)",
        }}
      >
        <div className="h-4 w-48 skeleton mb-6" />
        <div className="grid grid-cols-5 gap-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="h-20 skeleton" />
          ))}
        </div>
      </div>
    );
  }

  const varianceResult = formatVariance(breakdown.variance);
  const isClean = varianceResult.isZero || breakdown.variance_type === "NO_VARIANCE";

  const gross = parseFloat(String(breakdown.gross_amount || 0));
  const fee = parseFloat(String(breakdown.fee_amount || 0));
  const tax = parseFloat(String(breakdown.tax_amount || 0));
  const adj = parseFloat(String(breakdown.adjustment_amount || 0));
  const expNet = parseFloat(String(breakdown.expected_net_amount || 0));
  const received = breakdown.bank_received_amount !== null && breakdown.bank_received_amount !== undefined
    ? parseFloat(String(breakdown.bank_received_amount))
    : null;

  // Dynamic tax basis calculation from backend values rather than hardcoding 18% universally
  const dynamicTaxBasis = fee > 0 && tax > 0
    ? `${((tax / fee) * 100).toFixed(0)}% basis on fee`
    : "Statutory deduction";

  return (
    <div
      className="rounded-sm border p-6 text-[#eceae6] select-none"
      style={{
        borderColor: "var(--border-subtle)",
        background: "var(--surface-1)",
      }}
    >
      {/* Header */}
      <div
        className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-5"
        style={{ borderBottom: "1px solid var(--border-subtle)" }}
      >
        <div>
          <div className="flex items-center gap-2">
            <span
              className="text-[10px] font-semibold uppercase tracking-[0.14em]"
              style={{ color: "var(--accent)" }}
            >
              Settlement Decomposition
            </span>
            <span style={{ color: "var(--text-tertiary)" }}>•</span>
            <span
              className="text-[9px] font-mono px-1.5 py-0.5 rounded-xs font-bold"
              style={{
                color: isClean ? "var(--matched-text)" : "var(--variance-text)",
                background: isClean ? "var(--matched-bg)" : "var(--variance-bg)",
                border: `1px solid ${isClean ? "var(--matched-border)" : "var(--variance-border)"}`,
              }}
            >
              {isClean ? "PARITY CONFIRMED" : (breakdown.variance_type || "VARIANCE DETECTED").replace(/_/g, " ")}
            </span>
          </div>
          <h2 className="text-sm font-bold text-[#eceae6] mt-0.5">
            Expected Net vs. Bank Statement Parity
          </h2>
          <p className="text-xs text-[#8e96a0] mt-0.5">
            Gross Billed − Gateway MDR Fee − Statutory Tax + Account Adjustments = Expected Net Settlement
          </p>
        </div>

        {breakdown.settlement_id && (
          <div
            className="flex items-center gap-2 text-xs font-mono px-2.5 py-1 rounded-xs"
            style={{
              background: "var(--surface-2)",
              border: "1px solid var(--border-subtle)",
            }}
          >
            <span style={{ color: "var(--text-tertiary)" }}>ID:</span>
            <span className="text-[#eceae6] font-semibold">{breakdown.settlement_id}</span>
          </div>
        )}
      </div>

      {/* Part 1: Mathematical Ledger Decomposition Waterfall */}
      <div className="pt-6">
        <div className="text-[10px] uppercase font-semibold tracking-wider text-[#8e96a0] mb-3">
          1. Gateway Deduction Waterfall
        </div>

        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 text-xs">
          {/* Gross */}
          <div
            className="p-3.5 rounded-xs border"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-2)",
            }}
          >
            <div className="text-[10px] uppercase font-semibold text-[#8e96a0]">Gross Captured</div>
            <div className="mt-1.5 text-base font-bold font-mono text-[#eceae6] font-tabular">
              {formatINR(gross)}
            </div>
            <div className="mt-1 text-[11px] text-[#545e6a]">Payment volume</div>
          </div>

          {/* Fees */}
          <div
            className="p-3.5 rounded-xs border"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-2)",
            }}
          >
            <div className="text-[10px] uppercase font-semibold text-[#8e96a0]">− Gateway Fee (MDR)</div>
            <div className="mt-1.5 text-base font-bold font-mono text-[#e07070] font-tabular">
              {formatINR(fee)}
            </div>
            <div className="mt-1 text-[11px] text-[#545e6a]">Merchant discount rate</div>
          </div>

          {/* Tax (Dynamic Basis, never hardcoded universal 18%) */}
          <div
            className="p-3.5 rounded-xs border"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-2)",
            }}
          >
            <div className="text-[10px] uppercase font-semibold text-[#8e96a0]">− Statutory Tax</div>
            <div className="mt-1.5 text-base font-bold font-mono text-[#d4a84e] font-tabular">
              {formatINR(tax)}
            </div>
            <div className="mt-1 text-[11px] font-mono text-[#8e96a0]">
              Basis: {dynamicTaxBasis}
            </div>
          </div>

          {/* Adjustments */}
          <div
            className="p-3.5 rounded-xs border"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-2)",
            }}
          >
            <div className="text-[10px] uppercase font-semibold text-[#8e96a0]">± Adjustments</div>
            <div className="mt-1.5 text-base font-bold font-mono text-[#8e96a0] font-tabular">
              {formatINR(adj)}
            </div>
            <div className="mt-1 text-[11px] text-[#545e6a]">Dispute / correction</div>
          </div>

          {/* Expected Net (Gold Control Emphasis) */}
          <div
            className="p-3.5 rounded-xs border"
            style={{
              borderColor: "var(--accent-border)",
              background: "var(--surface-3)",
              borderTop: "2px solid var(--accent)",
            }}
          >
            <div className="text-[10px] uppercase font-semibold text-[#c9a96e]">═ Expected Net</div>
            <div className="mt-1.5 text-base font-bold font-mono text-[#eceae6] font-tabular">
              {formatINR(expNet)}
            </div>
            <div className="mt-1 text-[11px] text-[#c9a96e]">Authoritative target</div>
          </div>
        </div>
      </div>

      {/* Part 2: Settlement Variance Comparison Rails */}
      <div className="mt-6 pt-5" style={{ borderTop: "1px solid var(--border-subtle)" }}>
        <div className="text-[10px] uppercase font-semibold tracking-wider text-[#8e96a0] mb-3">
          2. Core Banking Reconciliation Parity
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div
            className="p-4 rounded-xs border font-mono"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-2)",
            }}
          >
            <div className="text-[10px] uppercase text-[#8e96a0]">Expected Net Wire</div>
            <div className="mt-2 text-xl font-bold text-[#eceae6] font-tabular">
              {formatINR(expNet)}
            </div>
            <div className="mt-1 text-[11px] text-[#545e6a]">Computed settlement credit</div>
          </div>

          <div
            className="p-4 rounded-xs border font-mono"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-2)",
            }}
          >
            <div className="text-[10px] uppercase text-[#8e96a0]">Bank Statement Received</div>
            <div className="mt-2 text-xl font-bold font-tabular text-[#6ecba0]">
              {received !== null ? formatINR(received) : "—"}
            </div>
            <div className="mt-1 text-[11px] text-[#545e6a]">
              {received !== null ? "Confirmed core bank credit" : "Awaiting bank statement match"}
            </div>
          </div>

          <div
            className="p-4 rounded-xs border font-mono"
            style={{
              borderColor: isClean ? "var(--matched-border)" : "var(--variance-border)",
              background: "var(--surface-2)",
              borderTop: isClean ? "2px solid var(--matched)" : "2px solid var(--variance)",
            }}
          >
            <div className="text-[10px] uppercase text-[#8e96a0]">Reconciliation Variance</div>
            <div
              className={`mt-2 text-xl font-bold font-tabular ${
                isClean ? "text-[#6ecba0]" : "text-[#e07070]"
              }`}
            >
              {varianceResult.text}
            </div>
            <div className="mt-1 text-[11px] text-[#8e96a0]">
              {isClean ? "0.00 Parity Confirmed" : (breakdown.variance_type || "Discrepancy Detected").replace(/_/g, " ")}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
