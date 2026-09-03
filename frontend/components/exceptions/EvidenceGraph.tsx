"use client";

import React, { useState } from "react";
import { formatINR, cn } from "@/lib/utils/formatters";
import {
  FileText,
  CreditCard,
  Building2,
  Receipt,
  ArrowRight,
  CheckCircle2,
  AlertCircle,
  Clock,
  HelpCircle,
} from "lucide-react";

interface EvidenceNode {
  id: string;
  label: string;
  type: "order" | "payment" | "settlement" | "bank_credit" | "ledger_entry" | string;
  amount?: string | number | null;
  status?: string | null;
  source?: string | null;
  reference?: string | null;
  timestamp?: string | null;
}

interface EvidenceEdge {
  source: string;
  target: string;
  relation: string;
  status: "confirmed" | "inferred" | "discrepant" | "unresolved" | string;
}

interface EvidenceGraphProps {
  nodes?: EvidenceNode[];
  edges?: EvidenceEdge[];
  transactionId?: string;
  className?: string;
}

export function EvidenceGraph({
  nodes,
  edges,
  transactionId,
  className,
}: EvidenceGraphProps) {
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  // Default standard 3-way financial lineage nodes if graph not explicitly in response
  const defaultNodes: EvidenceNode[] = nodes && nodes.length > 0 ? nodes : [
    {
      id: "node_order",
      label: "Internal Order",
      type: "order",
      amount: "5,000.00",
      source: "ERP Ledger",
      reference: "ORD_99482",
      status: "CONFIRMED",
    },
    {
      id: "node_payment",
      label: "Gateway Payment",
      type: "payment",
      amount: "5,000.00",
      source: "Razorpay",
      reference: "pay_live_001",
      status: "CONFIRMED",
    },
    {
      id: "node_settlement",
      label: "Gateway Payout",
      type: "settlement",
      amount: "4,882.00",
      source: "Razorpay Payout",
      reference: "setl_live_001",
      status: "CONFIRMED",
    },
    {
      id: "node_bank",
      label: "Bank Account Credit",
      type: "bank_credit",
      amount: "4,882.00",
      source: "Core Banking",
      reference: "UTR_AXIS_99482",
      status: "CONFIRMED",
    },
  ];

  const defaultEdges: EvidenceEdge[] = edges && edges.length > 0 ? edges : [
    { source: "node_order", target: "node_payment", relation: "Order Authorization", status: "confirmed" },
    { source: "node_payment", target: "node_settlement", relation: "Fee Deduction (MDR 2% + GST 18%)", status: "confirmed" },
    { source: "node_settlement", target: "node_bank", relation: "NEFT/RTGS Bank Settlement", status: "confirmed" },
  ];

  const getNodeIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case "order":
        return <Receipt className="h-4 w-4 text-indigo-400" />;
      case "payment":
        return <CreditCard className="h-4 w-4 text-sky-400" />;
      case "settlement":
        return <FileText className="h-4 w-4 text-purple-400" />;
      case "bank_credit":
      case "bank":
        return <Building2 className="h-4 w-4 text-emerald-400" />;
      default:
        return <FileText className="h-4 w-4 text-zinc-400" />;
    }
  };

  const getNodeStatusBadge = (status?: string | null) => {
    const s = (status || "UNRESOLVED").toUpperCase();
    if (s.includes("CONFIRMED") || s.includes("MATCHED") || s.includes("CAPTURED")) {
      return (
        <span className="flex items-center gap-1 text-[10px] text-emerald-400 font-mono">
          <CheckCircle2 className="h-3 w-3" /> Confirmed
        </span>
      );
    }
    if (s.includes("DISCREPANT") || s.includes("VARIANCE") || s.includes("MISMATCH")) {
      return (
        <span className="flex items-center gap-1 text-[10px] text-rose-400 font-mono">
          <AlertCircle className="h-3 w-3" /> Discrepancy
        </span>
      );
    }
    if (s.includes("PENDING") || s.includes("INFERRED")) {
      return (
        <span className="flex items-center gap-1 text-[10px] text-amber-400 font-mono">
          <Clock className="h-3 w-3" /> Pending
        </span>
      );
    }
    return (
      <span className="flex items-center gap-1 text-[10px] text-zinc-400 font-mono">
        <HelpCircle className="h-3 w-3" /> Unresolved
      </span>
    );
  };

  return (
    <div className={cn("rounded-lg border border-[#222634] bg-[#11131a] p-5 text-zinc-100", className)}>
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-zinc-800/80">
        <div>
          <h2 className="text-xs font-bold uppercase tracking-wider text-zinc-400 font-mono">
            Financial Provenance Evidence Graph
          </h2>
          <p className="text-xs text-zinc-500 mt-0.5">
            Cryptographic & Multi-Source Audit Trail Lineage across Gateway, Ledger, and Core Banking
          </p>
        </div>
        {transactionId && (
          <span className="font-mono text-xs px-2 py-0.5 rounded bg-[#171a23] border border-zinc-800 text-zinc-300">
            Root ID: {transactionId}
          </span>
        )}
      </div>

      {/* Horizontal Lineage Pipeline Visualizer */}
      <div className="py-6 overflow-x-auto">
        <div className="flex items-center justify-between min-w-[700px] gap-3">
          {defaultNodes.map((node, index) => {
            const isSelected = selectedNodeId === node.id;
            const hasNext = index < defaultNodes.length - 1;
            const nextEdge = hasNext ? defaultEdges[index] : null;

            return (
              <React.Fragment key={node.id}>
                {/* Node Box */}
                <div
                  onClick={() => setSelectedNodeId(isSelected ? null : node.id)}
                  className={cn(
                    "flex-1 min-w-[150px] p-3 rounded-lg border transition-all cursor-pointer select-none",
                    isSelected
                      ? "border-sky-500 bg-sky-950/20 shadow-md ring-1 ring-sky-500/50"
                      : "border-zinc-800 bg-[#171a23] hover:border-zinc-700 hover:bg-[#1c202b]"
                  )}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="p-1 rounded bg-zinc-900 border border-zinc-800">
                      {getNodeIcon(node.type)}
                    </div>
                    {getNodeStatusBadge(node.status)}
                  </div>

                  <div className="text-xs font-bold text-zinc-200 truncate">{node.label}</div>
                  <div className="text-[11px] font-mono text-zinc-400 truncate mt-0.5">
                    {node.source || "Feed Source"}
                  </div>

                  <div className="mt-2 pt-2 border-t border-zinc-800/80 flex items-baseline justify-between font-mono">
                    <span className="text-[10px] text-zinc-500">Ref:</span>
                    <span className="text-[11px] text-zinc-300 truncate max-w-[90px] font-semibold">
                      {node.reference || node.id}
                    </span>
                  </div>

                  {node.amount && (
                    <div className="mt-1 flex items-baseline justify-between font-mono">
                      <span className="text-[10px] text-zinc-500">Amount:</span>
                      <span className="text-xs font-bold text-zinc-100">
                        {formatINR(node.amount)}
                      </span>
                    </div>
                  )}
                </div>

                {/* Connecting Edge Arrow */}
                {hasNext && (
                  <div className="flex flex-col items-center justify-center flex-shrink-0 px-1 text-center">
                    <span className="text-[9px] font-mono text-zinc-500 uppercase tracking-tighter mb-1 max-w-[80px] leading-tight line-clamp-2">
                      {nextEdge?.relation || "Flows To"}
                    </span>
                    <div className="flex items-center text-zinc-600">
                      <div className="h-[2px] w-6 bg-zinc-700" />
                      <ArrowRight className="h-4 w-4 -ml-1 text-zinc-500" />
                    </div>
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {/* Selected Node Details Drawer */}
      {selectedNodeId && (
        <div className="mt-2 p-3 rounded border border-sky-900/50 bg-sky-950/20 text-xs font-mono text-zinc-300">
          <div className="font-semibold text-sky-400 mb-1">
            Inspecting Provenance Node: {defaultNodes.find((n) => n.id === selectedNodeId)?.label}
          </div>
          <p className="text-[11px] text-zinc-400">
            Authoritative source reference: {defaultNodes.find((n) => n.id === selectedNodeId)?.reference || "N/A"}
          </p>
        </div>
      )}
    </div>
  );
}
