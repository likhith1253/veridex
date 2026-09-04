"use client";

import React from "react";
import { formatINR, cn } from "@/lib/utils/formatters";
import type { SettlementTaxAudit } from "@/types/settlements";
import { CheckCircle2, AlertTriangle, HelpCircle, FileCheck } from "lucide-react";

interface TaxAuditPanelProps {
  taxAudit?: SettlementTaxAudit | null;
  isLoading?: boolean;
}

export function TaxAuditPanel({ taxAudit, isLoading }: TaxAuditPanelProps) {
  if (isLoading || !taxAudit) {
    return (
      <div
        className="rounded-sm border p-6 animate-pulse"
        style={{
          borderColor: "var(--border-subtle)",
          background: "var(--surface-1)",
        }}
      >
        <div className="h-4 w-40 skeleton mb-4" />
        <div className="h-20 skeleton" />
      </div>
    );
  }

  const status = (taxAudit.status || "INSUFFICIENT_EVIDENCE").toUpperCase();
  const isInsufficient = status === "INSUFFICIENT_EVIDENCE";

  const getStatusBadge = () => {
    switch (status) {
      case "MATCHED":
        return (
          <span
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xs text-xs font-mono font-bold"
            style={{
              color: "var(--matched-text)",
              background: "var(--matched-bg)",
              border: "1px solid var(--matched-border)",
            }}
          >
            <CheckCircle2 className="h-3.5 w-3.5" /> PARITY CONFIRMED (₹0.00 VARIANCE)
          </span>
        );
      case "VARIANCE":
        return (
          <span
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xs text-xs font-mono font-bold"
            style={{
              color: "var(--variance-text)",
              background: "var(--variance-bg)",
              border: "1px solid var(--variance-border)",
            }}
          >
            <AlertTriangle className="h-3.5 w-3.5" /> STATUTORY TAX VARIANCE
          </span>
        );
      case "INSUFFICIENT_EVIDENCE":
      default:
        return (
          <span
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-xs text-xs font-mono font-bold"
            style={{
              color: "#8e96a0",
              background: "var(--surface-3)",
              border: "1px solid var(--border-subtle)",
            }}
          >
            <HelpCircle className="h-3.5 w-3.5 text-[#545e6a]" /> INSUFFICIENT EVIDENCE
          </span>
        );
    }
  };

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
          <span
            className="text-[10px] font-semibold uppercase tracking-[0.14em]"
            style={{ color: "var(--accent)" }}
          >
            Statutory Tax Line Auditor
          </span>
          <h2 className="text-sm font-bold text-[#eceae6] mt-0.5">
            Automated Statutory Tax Deduction Verification
          </h2>
          <p className="text-xs text-[#8e96a0] mt-0.5">
            Verifies gateway invoice deductions against authoritative tax schedules
          </p>
        </div>
        <div>{getStatusBadge()}</div>
      </div>

      {/* Audit Metrics Comparison */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 pt-6 text-xs">
        <div
          className="rounded-xs border p-3.5"
          style={{
            borderColor: "var(--border-subtle)",
            background: "var(--surface-2)",
          }}
        >
          <div className="text-[10px] uppercase font-semibold text-[#8e96a0]">Gross Settlement</div>
          <div className="text-sm font-bold font-mono text-[#eceae6] mt-1 font-tabular">
            {formatINR(taxAudit.gross_amount)}
          </div>
        </div>

        <div
          className="rounded-xs border p-3.5"
          style={{
            borderColor: "var(--border-subtle)",
            background: "var(--surface-2)",
          }}
        >
          <div className="text-[10px] uppercase font-semibold text-[#8e96a0]">Reported Gateway Tax</div>
          <div className="text-sm font-bold font-mono text-[#eceae6] mt-1 font-tabular">
            {taxAudit.reported_tax !== null && taxAudit.reported_tax !== undefined
              ? formatINR(taxAudit.reported_tax)
              : "INSUFFICIENT EVIDENCE"}
          </div>
        </div>

        <div
          className="rounded-xs border p-3.5"
          style={{
            borderColor: "var(--border-subtle)",
            background: "var(--surface-2)",
          }}
        >
          <div className="text-[10px] uppercase font-semibold text-[#8e96a0]">Expected Authoritative Tax</div>
          <div className="text-sm font-bold font-mono text-[#c9a96e] mt-1 font-tabular">
            {isInsufficient
              ? "INSUFFICIENT EVIDENCE"
              : taxAudit.expected_tax !== null && taxAudit.expected_tax !== undefined
              ? formatINR(taxAudit.expected_tax)
              : "INSUFFICIENT EVIDENCE"}
          </div>
        </div>

        <div
          className="rounded-xs border p-3.5"
          style={{
            borderColor:
              status === "MATCHED"
                ? "var(--matched-border)"
                : isInsufficient
                ? "var(--border-subtle)"
                : "var(--variance-border)",
            background: "var(--surface-2)",
            borderLeft:
              status === "MATCHED"
                ? "3px solid var(--matched)"
                : isInsufficient
                ? "3px solid #545e6a"
                : "3px solid var(--variance)",
          }}
        >
          <div className="text-[10px] uppercase font-semibold text-[#8e96a0]">Statutory Tax Variance</div>
          <div
            className={`text-sm font-bold font-mono mt-1 font-tabular ${
              status === "MATCHED"
                ? "text-[#6ecba0]"
                : isInsufficient
                ? "text-[#8e96a0]"
                : "text-[#e07070]"
            }`}
          >
            {isInsufficient
              ? "INSUFFICIENT EVIDENCE"
              : taxAudit.tax_variance !== null && taxAudit.tax_variance !== undefined
              ? formatINR(taxAudit.tax_variance)
              : "₹0.00"}
          </div>
        </div>
      </div>

      {/* Explanation Footnote */}
      <div className="mt-5 pt-4 border-t text-xs text-[#8e96a0]" style={{ borderColor: "var(--border-subtle)" }}>
        <p className="leading-relaxed">
          <strong className="text-[#eceae6]">Audit Assessment:</strong> {taxAudit.explanation}
        </p>
      </div>
    </div>
  );
}
