"use client";

import React from "react";
import { formatINR, cn } from "@/lib/utils/formatters";
import type { SettlementTaxAudit } from "@/types/settlements";
import { CheckCircle2, AlertTriangle, HelpCircle, FileCheck, ShieldAlert } from "lucide-react";

interface TaxAuditPanelProps {
  taxAudit?: SettlementTaxAudit | null;
  isLoading?: boolean;
}

export function TaxAuditPanel({ taxAudit, isLoading }: TaxAuditPanelProps) {
  if (isLoading || !taxAudit) {
    return (
      <div className="h-48 rounded-lg border border-zinc-800 bg-[#11131a] p-5 animate-pulse">
        <div className="h-4 w-40 rounded bg-zinc-800 mb-4" />
        <div className="h-20 rounded bg-zinc-800" />
      </div>
    );
  }

  const status = (taxAudit.status || "INSUFFICIENT_EVIDENCE").toUpperCase();

  const getStatusBadge = () => {
    switch (status) {
      case "MATCHED":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono font-bold border bg-emerald-950/60 text-emerald-400 border-emerald-800/60">
            <CheckCircle2 className="h-3.5 w-3.5" /> MATCHED (0.00% VARIANCE)
          </span>
        );
      case "VARIANCE":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono font-bold border bg-rose-950/60 text-rose-400 border-rose-800/60">
            <AlertTriangle className="h-3.5 w-3.5" /> MATERIAL TAX VARIANCE
          </span>
        );
      case "INSUFFICIENT_EVIDENCE":
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-mono font-bold border bg-zinc-900 text-zinc-400 border-zinc-700">
            <HelpCircle className="h-3.5 w-3.5" /> INSUFFICIENT EVIDENCE
          </span>
        );
    }
  };

  return (
    <div className="rounded-lg border border-[#222634] bg-[#11131a] p-5 text-zinc-100">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-zinc-800/80">
        <div>
          <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-400 font-mono">
            Automated GST Tax-Line Audit (Section 9 CGST / SGST 18%)
          </h2>
          <p className="text-xs text-zinc-500 mt-0.5">
            Verifies reported gateway tax invoices against authoritative tax schedules
          </p>
        </div>
        <div>{getStatusBadge()}</div>
      </div>

      {/* Audit Metrics Comparison */}
      <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 pt-5 font-mono text-xs">
        <div className="rounded border border-zinc-800 bg-[#171a23] p-3">
          <div className="text-[10px] text-zinc-500 uppercase">Gross Settlement</div>
          <div className="text-sm font-bold text-zinc-200 mt-1 font-tabular">
            {formatINR(taxAudit.gross_amount)}
          </div>
        </div>

        <div className="rounded border border-zinc-800 bg-[#171a23] p-3">
          <div className="text-[10px] text-zinc-500 uppercase">Reported Gateway Tax</div>
          <div className="text-sm font-bold text-zinc-200 mt-1 font-tabular">
            {taxAudit.reported_tax !== null && taxAudit.reported_tax !== undefined
              ? formatINR(taxAudit.reported_tax)
              : "N/A (Unreported)"}
          </div>
        </div>

        <div className="rounded border border-zinc-800 bg-[#171a23] p-3">
          <div className="text-[10px] text-zinc-500 uppercase">Expected Authoritative Tax</div>
          <div className="text-sm font-bold text-zinc-200 mt-1 font-tabular">
            {taxAudit.expected_tax !== null && taxAudit.expected_tax !== undefined
              ? formatINR(taxAudit.expected_tax)
              : "Insufficient Data"}
          </div>
        </div>

        <div className="rounded border border-zinc-800 bg-[#171a23] p-3">
          <div className="text-[10px] text-zinc-500 uppercase">Tax Variance Delta</div>
          <div
            className={cn(
              "text-sm font-bold mt-1 font-tabular",
              status === "MATCHED"
                ? "text-emerald-400"
                : status === "VARIANCE"
                ? "text-rose-400"
                : "text-zinc-400"
            )}
          >
            {taxAudit.tax_variance !== null && taxAudit.tax_variance !== undefined
              ? formatINR(taxAudit.tax_variance)
              : "Insufficient Data"}
          </div>
        </div>
      </div>

      {/* Explanation & Evidence Citation */}
      <div className="mt-4 p-3 rounded-lg border border-zinc-800 bg-[#141722] text-xs space-y-2">
        <div className="flex items-center gap-1.5 text-zinc-400 font-semibold font-mono">
          <FileCheck className="h-4 w-4 text-sky-400" />
          Auditor Assessment & Policy Reference:
        </div>
        <p className="text-zinc-300 leading-relaxed font-mono text-[11px]">
          {taxAudit.explanation || "No tax audit explanation available."}
        </p>

        {taxAudit.evidence_ids && taxAudit.evidence_ids.length > 0 && (
          <div className="pt-2 border-t border-zinc-800/80 flex items-center gap-2 text-[10px] font-mono text-zinc-500">
            <span>Supporting Invoices / Ledger IDs:</span>
            <div className="flex flex-wrap gap-1">
              {taxAudit.evidence_ids.map((id, idx) => (
                <span key={idx} className="px-1.5 py-0.2 rounded bg-zinc-900 border border-zinc-800 text-zinc-300">
                  {id}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
