"use client";

import React, { useState, useMemo } from "react";
import { formatINR, formatDateTime, cn } from "@/lib/utils/formatters";
import {
  FileText,
  CreditCard,
  Building2,
  Receipt,
  CheckCircle2,
  AlertCircle,
  Clock,
  HelpCircle,
  Database,
  Link2,
  ArrowRight,
  ShieldCheck,
  X,
} from "lucide-react";

export interface EvidenceNode {
  id: string;
  label: string;
  type: "order" | "payment" | "settlement" | "bank_credit" | "ledger_entry" | string;
  amount?: string | number | null;
  status?: "CONFIRMED" | "SUPPORTING" | "INFERRED" | "UNRESOLVED" | "NOT_FOUND" | "UNAVAILABLE" | string | null;
  source?: string | null;
  reference?: string | null;
  timestamp?: string | null;
  metadata?: Record<string, unknown>;
}

export interface EvidenceEdge {
  source: string;
  target: string;
  relation: string;
  status?: "confirmed" | "inferred" | "discrepant" | "unresolved" | "missing" | string;
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
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);

  const activeNodeId = selectedNodeId || hoveredNodeId;

  // Default authoritative 4-stage financial provenance chain if not dynamically provided
  const activeNodes: EvidenceNode[] = useMemo(() => {
    if (nodes && nodes.length > 0) return nodes;
    return [
      {
        id: "node_order",
        label: "Internal Order",
        type: "order",
        amount: "5000.00",
        source: "Merchant Ledger",
        reference: "ORD_99482",
        status: "CONFIRMED",
        timestamp: "2026-09-03T10:14:02Z",
      },
      {
        id: "node_payment",
        label: "Gateway Payment",
        type: "payment",
        amount: "5000.00",
        source: "Razorpay Feed",
        reference: "pay_live_99482",
        status: "CONFIRMED",
        timestamp: "2026-09-03T10:14:05Z",
      },
      {
        id: "node_settlement",
        label: "Settlement Payout",
        type: "settlement",
        amount: "4882.00",
        source: "Razorpay Payout",
        reference: "setl_live_99482",
        status: "CONFIRMED",
        timestamp: "2026-09-03T14:30:00Z",
      },
      {
        id: "node_bank",
        label: "Bank Statement Credit",
        type: "bank_credit",
        amount: "4882.00",
        source: "Core Banking Feed",
        reference: "UTR_PENDING",
        status: "UNAVAILABLE",
        timestamp: null,
      },
    ];
  }, [nodes]);

  const activeEdges: EvidenceEdge[] = useMemo(() => {
    if (edges && edges.length > 0) return edges;
    return [
      {
        source: "node_order",
        target: "node_payment",
        relation: "Order Authorization",
        status: "confirmed",
      },
      {
        source: "node_payment",
        target: "node_settlement",
        relation: "Deductions (MDR + Tax)",
        status: "confirmed",
      },
      {
        source: "node_settlement",
        target: "node_bank",
        relation: "NEFT / RTGS Statement Parity",
        status: "missing",
      },
    ];
  }, [edges]);

  // Connected nodes map for relational emphasis
  const connectedNodeIds = useMemo(() => {
    if (!activeNodeId) return new Set<string>();
    const set = new Set<string>([activeNodeId]);
    activeEdges.forEach((edge) => {
      if (edge.source === activeNodeId) set.add(edge.target);
      if (edge.target === activeNodeId) set.add(edge.source);
    });
    return set;
  }, [activeNodeId, activeEdges]);

  const getNodeIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case "order":
        return <Receipt className="h-4 w-4 text-[#7eaa8e]" />;
      case "payment":
        return <CreditCard className="h-4 w-4 text-[#949da6]" />;
      case "settlement":
        return <FileText className="h-4 w-4 text-[#c9a96e]" />;
      case "bank_credit":
      case "bank":
        return <Building2 className="h-4 w-4 text-[#ab9f90]" />;
      default:
        return <FileText className="h-4 w-4 text-[#545e6a]" />;
    }
  };

  const getNodeStatusStyle = (status?: string | null) => {
    const s = (status || "UNAVAILABLE").toUpperCase();
    if (s.includes("CONFIRMED") || s.includes("MATCHED")) {
      return {
        label: "CONFIRMED",
        color: "var(--matched-text)",
        bg: "var(--matched-bg)",
        border: "var(--matched-border)",
        icon: <CheckCircle2 className="h-3 w-3" />,
      };
    }
    if (s.includes("INFERRED")) {
      return {
        label: "INFERRED",
        color: "var(--pending-text)",
        bg: "var(--pending-bg)",
        border: "var(--pending-border)",
        icon: <Clock className="h-3 w-3" />,
      };
    }
    if (s.includes("SUPPORTING")) {
      return {
        label: "SUPPORTING",
        color: "var(--text-secondary)",
        bg: "var(--surface-3)",
        border: "var(--border-subtle)",
        icon: <Link2 className="h-3 w-3" />,
      };
    }
    if (s.includes("UNRESOLVED") || s.includes("DISCREPANT")) {
      return {
        label: "DISCREPANCY",
        color: "var(--variance-text)",
        bg: "var(--variance-bg)",
        border: "var(--variance-border)",
        icon: <AlertCircle className="h-3 w-3" />,
      };
    }
    // Honest Known/Unknown visual language: Neutral slate for missing evidence, not error red!
    return {
      label: "EVIDENCE UNAVAILABLE",
      color: "#8e96a0",
      bg: "var(--surface-3)",
      border: "var(--border-subtle)",
      icon: <HelpCircle className="h-3 w-3 text-[#545e6a]" />,
    };
  };

  const selectedNode = activeNodes.find((n) => n.id === selectedNodeId);

  return (
    <div
      className={cn("rounded-sm border p-6 select-none", className)}
      style={{
        borderColor: "var(--border-subtle)",
        background: "var(--surface-1)",
      }}
    >
      {/* Canvas Header */}
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
              Forensic Evidence Provenance
            </span>
            <span style={{ color: "var(--text-tertiary)" }}>•</span>
            <span className="text-xs text-[#8e96a0]">
              Lineage Verification Chain
            </span>
          </div>
          <h2 className="text-sm font-bold text-[#eceae6] mt-0.5">
            Cryptographic Financial Provenance Canvas
          </h2>
        </div>

        {transactionId && (
          <div
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-xs text-xs font-mono"
            style={{
              borderColor: "var(--border-subtle)",
              background: "var(--surface-2)",
              border: "1px solid var(--border-subtle)",
            }}
          >
            <span style={{ color: "var(--text-tertiary)" }}>Anchor: </span>
            <span className="text-[#eceae6] font-semibold">{transactionId}</span>
          </div>
        )}
      </div>

      {/* Hero Visual Provenance Canvas */}
      <div className="py-6 overflow-x-auto scrollbar-none">
        <div className="flex items-stretch justify-between min-w-[720px] gap-3">
          {activeNodes.map((node, index) => {
            const isSelected = selectedNodeId === node.id;
            const isConnected = connectedNodeIds.has(node.id);
            const isSoftened = activeNodeId && !isConnected;
            const statusInfo = getNodeStatusStyle(node.status);
            const hasNext = index < activeNodes.length - 1;
            const nextEdge = hasNext ? activeEdges[index] : null;

            return (
              <React.Fragment key={node.id}>
                {/* Forensic Node Canvas */}
                <div
                  onClick={() => setSelectedNodeId(isSelected ? null : node.id)}
                  onMouseEnter={() => setHoveredNodeId(node.id)}
                  onMouseLeave={() => setHoveredNodeId(null)}
                  className={cn(
                    "flex-1 min-w-[160px] p-4 rounded-xs border cursor-pointer select-none transition-micro flex flex-col justify-between",
                    isSoftened ? "opacity-35" : "opacity-100"
                  )}
                  style={{
                    borderColor: isSelected
                      ? "var(--accent)"
                      : "var(--border-subtle)",
                    background: isSelected ? "var(--surface-3)" : "var(--surface-2)",
                    borderTop: isSelected ? "2px solid var(--accent)" : "1px solid var(--border-subtle)",
                  }}
                >
                  <div>
                    {/* Node Header */}
                    <div className="flex items-center justify-between gap-1 mb-2.5">
                      <div className="p-1 rounded-xs bg-[#080a0c] border border-[#222831]">
                        {getNodeIcon(node.type)}
                      </div>
                      <span
                        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-xs font-mono text-[9px] font-bold border tracking-wider"
                        style={{
                          color: statusInfo.color,
                          background: statusInfo.bg,
                          borderColor: statusInfo.border,
                        }}
                      >
                        {statusInfo.icon}
                        <span>{statusInfo.label}</span>
                      </span>
                    </div>

                    <div className="text-xs font-semibold text-[#eceae6] truncate">
                      {node.label}
                    </div>

                    <div className="text-[11px] text-[#8e96a0] truncate mt-0.5">
                      {node.source || "External Lineage"}
                    </div>
                  </div>

                  {/* Quantitative Details */}
                  <div className="mt-4 pt-3 border-t space-y-1" style={{ borderColor: "var(--border-subtle)" }}>
                    <div className="flex items-baseline justify-between font-mono">
                      <span className="text-[10px] text-[#545e6a] uppercase">Amount:</span>
                      <span className="font-bold text-xs font-tabular text-[#eceae6]">
                        {node.amount !== null && node.amount !== undefined ? formatINR(node.amount) : "—"}
                      </span>
                    </div>

                    <div className="flex items-center justify-between font-mono text-[10px] text-[#545e6a]">
                      <span>Ref:</span>
                      <span className="text-[#8e96a0] truncate max-w-[90px]">{node.reference || "N/A"}</span>
                    </div>
                  </div>
                </div>

                {/* Relational Directional Connection */}
                {hasNext && (
                  <div className="flex flex-col items-center justify-center px-1 flex-shrink-0">
                    <div className="w-5 h-px bg-[#222831]" />
                    <ArrowRight
                      className="h-3.5 w-3.5 -mt-2 -mb-2"
                      style={{
                        color:
                          nextEdge?.status === "confirmed"
                            ? "var(--matched-text)"
                            : nextEdge?.status === "missing"
                            ? "var(--text-tertiary)"
                            : "var(--accent)",
                      }}
                    />
                    <div className="w-5 h-px bg-[#222831]" />
                  </div>
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {/* Selected Node Detail Inspector Drawer */}
      {selectedNode && (
        <div
          className="mt-4 p-4 rounded-xs border text-xs"
          style={{
            borderColor: "var(--accent-border)",
            background: "var(--surface-2)",
          }}
        >
          <div className="flex items-center justify-between pb-3 border-b" style={{ borderColor: "var(--border-subtle)" }}>
            <div className="flex items-center gap-2">
              <span className="text-[10px] uppercase font-bold text-[#c9a96e] tracking-wider">
                Inspected Provenance Entity:
              </span>
              <span className="font-semibold text-[#eceae6]">{selectedNode.label}</span>
              <span className="font-mono text-[10px] text-[#545e6a]">({selectedNode.id})</span>
            </div>
            <button
              onClick={() => setSelectedNodeId(null)}
              className="p-1 text-[#8e96a0] hover:text-[#eceae6] transition-micro"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-3 font-mono text-xs">
            <div>
              <span className="text-[10px] text-[#545e6a] uppercase block">Authority Source</span>
              <span className="text-[#eceae6] font-medium mt-0.5 block">{selectedNode.source || "—"}</span>
            </div>
            <div>
              <span className="text-[10px] text-[#545e6a] uppercase block">Entity Reference</span>
              <span className="text-[#eceae6] font-medium mt-0.5 block">{selectedNode.reference || "—"}</span>
            </div>
            <div>
              <span className="text-[10px] text-[#545e6a] uppercase block">Monetary Value</span>
              <span className="text-[#eceae6] font-bold mt-0.5 block font-tabular">
                {selectedNode.amount !== null && selectedNode.amount !== undefined ? formatINR(selectedNode.amount) : "Unavailable"}
              </span>
            </div>
            <div>
              <span className="text-[10px] text-[#545e6a] uppercase block">Provenance Timestamp</span>
              <span className="text-[#8e96a0] font-medium mt-0.5 block">
                {selectedNode.timestamp ? formatDateTime(selectedNode.timestamp) : "Timestamp absent"}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
