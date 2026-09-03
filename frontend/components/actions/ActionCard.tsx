"use client";

import React, { useState } from "react";
import { formatINR, formatDateTime, cn } from "@/lib/utils/formatters";
import type { FinanceAction } from "@/types/actions";
import { StatusBadge } from "@/components/common/StatusBadge";
import { ApprovalModal } from "./ApprovalModal";
import {
  ShieldAlert,
  ShieldCheck,
  Play,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Lock,
} from "lucide-react";

interface ActionCardProps {
  action: FinanceAction;
}

export function ActionCard({ action }: ActionCardProps) {
  const [modalMode, setModalMode] = useState<"approve" | "reject" | "execute" | null>(null);

  const state = (action.state || "PENDING_APPROVAL").toUpperCase();
  const isPending = state === "PENDING_APPROVAL" || state === "RECOMMENDED";
  const isApproved = state === "APPROVED";
  const isExecuted = state === "EXECUTED";
  const isRejected = state === "REJECTED";

  // Policy Limit Check
  const amountNum = typeof action.amount === "string" ? parseFloat(action.amount) : action.amount;
  const isOverLimit =
    (action.action_type === "POST_ADJUSTMENT" && amountNum > 5000) ||
    (action.action_type === "WRITE_OFF" && amountNum > 100);

  return (
    <>
      <div
        className="rounded-sm border p-6 text-[#eceae6] transition-micro select-none"
        style={{
          borderColor: isPending ? "var(--pending-border)" : "var(--border-subtle)",
          background: "var(--surface-1)",
          borderLeft: isPending
            ? "3px solid var(--accent)"
            : isApproved || isExecuted
            ? "3px solid var(--matched)"
            : isRejected
            ? "3px solid var(--variance)"
            : "3px solid var(--border-subtle)",
        }}
      >
        {/* Reusable Action Governance Rail */}
        <div
          className="flex items-center justify-between gap-1 pb-4 mb-4 text-[10px] font-mono uppercase tracking-wider"
          style={{ borderBottom: "1px solid var(--border-subtle)" }}
        >
          <div className="flex items-center gap-1.5 text-[#6ecba0]">
            <CheckCircle2 className="h-3 w-3" />
            <span>1. RECOMMENDED</span>
          </div>
          <span style={{ color: "var(--text-tertiary)" }}>→</span>
          <div
            className="flex items-center gap-1.5"
            style={{
              color: isPending
                ? "var(--accent)"
                : isApproved || isExecuted
                ? "var(--matched-text)"
                : isRejected
                ? "var(--variance-text)"
                : "var(--text-tertiary)",
              fontWeight: isPending ? 700 : 500,
            }}
          >
            {isApproved || isExecuted ? (
              <CheckCircle2 className="h-3 w-3" />
            ) : isRejected ? (
              <XCircle className="h-3 w-3" />
            ) : (
              <Lock className="h-3 w-3" />
            )}
            <span>2. HUMAN AUTH {isPending ? "(ACTIVE)" : ""}</span>
          </div>
          <span style={{ color: "var(--text-tertiary)" }}>→</span>
          <div
            className="flex items-center gap-1.5"
            style={{
              color: isExecuted ? "var(--matched-text)" : "var(--text-tertiary)",
            }}
          >
            <Play className="h-3 w-3" />
            <span>3. BOUNDED EXECUTION</span>
          </div>
          <span style={{ color: "var(--text-tertiary)" }}>→</span>
          <div
            className="flex items-center gap-1.5"
            style={{
              color: isExecuted ? "var(--matched-text)" : "var(--text-tertiary)",
            }}
          >
            <ShieldCheck className="h-3 w-3" />
            <span>4. AUDIT LOG</span>
          </div>
        </div>

        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-[#eceae6]">
                {(action.action_type || "ACTION").replace(/_/g, " ")}
              </span>
              <StatusBadge status={action.state} />
            </div>
            <div className="text-xs text-[#8e96a0] mt-0.5 font-mono">
              ID: <span className="text-[#eceae6]">{action.id}</span> • Target: <span className="text-[#c9a96e]">{action.entity_id}</span>
            </div>
          </div>

          <div className="font-mono text-xl font-bold font-tabular text-[#eceae6]">
            {formatINR(action.amount)}
          </div>
        </div>

        {/* Card Body */}
        <div className="space-y-3 text-xs">
          {/* Recommendation Rationale (Analytical framing) */}
          {action.recommendation_reason && (
            <div
              className="p-3.5 rounded-xs border text-xs"
              style={{
                borderColor: "var(--border-subtle)",
                background: "var(--surface-2)",
              }}
            >
              <span className="text-[10px] font-semibold text-[#8e96a0] uppercase block mb-1">
                VERIDEX Analytical Rationale:
              </span>
              <p className="text-xs text-[#eceae6] leading-relaxed">
                {action.recommendation_reason}
              </p>
            </div>
          )}

          {/* Policy Bounding Flag */}
          {isOverLimit && (
            <div
              className="p-3 rounded-xs border text-xs flex items-center gap-2"
              style={{
                borderColor: "var(--variance-border)",
                background: "var(--variance-bg)",
                color: "var(--variance-text)",
              }}
            >
              <AlertCircle className="h-4 w-4 flex-shrink-0" />
              <span>
                Policy threshold exceeded: Requires dual Controller Level 2 review.
              </span>
            </div>
          )}

          {/* Decision Trail Information */}
          {action.approved_by && (
            <div className="flex items-center gap-1.5 text-[#6ecba0] text-xs pt-1">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>
                Authorized by <strong className="font-semibold text-[#eceae6] font-mono">{action.approved_by}</strong> on{" "}
                <span className="font-mono">{formatDateTime(action.approved_at)}</span>
              </span>
            </div>
          )}

          {action.rejected_by && (
            <div className="flex items-center gap-1.5 text-[#e07070] text-xs pt-1">
              <XCircle className="h-3.5 w-3.5" />
              <span>
                Rejected by <strong className="font-semibold text-[#eceae6] font-mono">{action.rejected_by}</strong> on{" "}
                <span className="font-mono">{formatDateTime(action.rejected_at)}</span>
              </span>
            </div>
          )}

          {(action.approval_reason || action.rejection_reason) && (
            <div
              className="p-2.5 rounded-xs text-xs text-[#8e96a0] italic"
              style={{ background: "var(--surface-2)" }}
            >
              &quot;{action.approval_reason || action.rejection_reason}&quot;
            </div>
          )}

          {/* Execution Result */}
          {isExecuted && action.execution_result && (
            <div
              className="p-2.5 rounded-xs border text-xs font-mono text-[#6ecba0]"
              style={{
                borderColor: "var(--matched-border)",
                background: "var(--matched-bg)",
              }}
            >
              Execution reference: {JSON.stringify(action.execution_result)}
            </div>
          )}
        </div>

        {/* Footer: Policy Controls & Action Buttons */}
        <div
          className="mt-5 pt-4 flex flex-wrap items-center justify-between gap-3"
          style={{ borderTop: "1px solid var(--border-subtle)" }}
        >
          <div className="text-[11px] text-[#8e96a0]">
            Policy Ceiling: <span className="text-[#eceae6] font-mono">{action.currency || "INR"} Enforced</span>
          </div>

          <div className="flex items-center gap-2">
            {isPending && (
              <>
                <button
                  onClick={() => setModalMode("reject")}
                  className="px-3 py-1.5 rounded-xs text-xs font-medium transition-micro"
                  style={{
                    color: "var(--variance-text)",
                    background: "var(--variance-bg)",
                    border: "1px solid var(--variance-border)",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.borderColor = "var(--variance)")}
                  onMouseLeave={(e) => (e.currentTarget.style.borderColor = "var(--variance-border)")}
                >
                  Reject Action
                </button>
                <button
                  onClick={() => setModalMode("approve")}
                  className="px-3.5 py-1.5 rounded-xs text-xs font-semibold transition-micro"
                  style={{
                    color: "#080a0c",
                    background: "var(--accent)",
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = "var(--accent-hover)")}
                  onMouseLeave={(e) => (e.currentTarget.style.background = "var(--accent)")}
                >
                  Authorize Approval
                </button>
              </>
            )}

            {isApproved && (
              <button
                onClick={() => setModalMode("execute")}
                className="inline-flex items-center gap-1.5 px-3.5 py-1.5 rounded-xs text-xs font-semibold transition-micro"
                style={{
                  color: "var(--matched-text)",
                  background: "var(--matched-bg)",
                  border: "1px solid var(--matched-border)",
                }}
              >
                <Play className="h-3.5 w-3.5 fill-current" />
                <span>Execute Bounded Action</span>
              </button>
            )}

            {isExecuted && (
              <span className="text-xs text-[#6ecba0] font-semibold flex items-center gap-1">
                <CheckCircle2 className="h-3.5 w-3.5" /> Immutable Audit Event Committed
              </span>
            )}
          </div>
        </div>
      </div>

      {modalMode && (
        <ApprovalModal
          action={action}
          mode={modalMode}
          onClose={() => setModalMode(null)}
        />
      )}
    </>
  );
}
