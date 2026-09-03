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
  FileText,
  User,
  AlertCircle,
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
      <div className="rounded-lg border border-[#222634] bg-[#11131a] p-5 text-zinc-100 hover:border-zinc-700 transition-all">
        {/* Card Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-zinc-800/80">
          <div className="flex items-center gap-2">
            <div className="font-mono text-sm font-bold text-zinc-200">
              {action.action_type.replace(/_/g, " ")}
            </div>
            <StatusBadge status={action.state} />
          </div>

          <div className="font-mono text-lg font-bold text-zinc-100 font-tabular">
            {formatINR(action.amount)}
          </div>
        </div>

        {/* Card Body */}
        <div className="py-3 space-y-2.5 text-xs font-mono">
          <div className="grid grid-cols-2 gap-2 text-zinc-400">
            <div>
              <span className="text-zinc-500">Action ID:</span>{" "}
              <span className="text-zinc-300 font-semibold">{action.id}</span>
            </div>
            <div>
              <span className="text-zinc-500">Target Entity:</span>{" "}
              <span className="text-zinc-300 font-semibold">{action.entity_id}</span>
            </div>
          </div>

          {/* AI Recommendation Reason */}
          {action.recommendation_reason && (
            <div className="p-2.5 rounded bg-[#171a23] border border-zinc-800 text-zinc-300">
              <span className="text-[10px] text-zinc-500 uppercase block mb-0.5">
                AI Recommendation Rationale:
              </span>
              <p className="font-sans text-xs leading-relaxed">{action.recommendation_reason}</p>
            </div>
          )}

          {/* Policy Bounding Flag */}
          {isOverLimit && (
            <div className="p-2 rounded bg-amber-950/40 border border-amber-800/50 text-amber-300 text-xs flex items-center gap-1.5">
              <AlertCircle className="h-4 w-4 flex-shrink-0 text-amber-400" />
              <span>
                Caution: Amount exceeds standard automated policy threshold. Requires Level 2 review.
              </span>
            </div>
          )}

          {/* Decision Trail Information */}
          {action.approved_by && (
            <div className="flex items-center gap-1.5 text-emerald-400 text-[11px]">
              <CheckCircle2 className="h-3.5 w-3.5" />
              <span>
                Authorized by <strong className="font-semibold">{action.approved_by}</strong> on{" "}
                {formatDateTime(action.approved_at)}
              </span>
            </div>
          )}

          {action.rejected_by && (
            <div className="flex items-center gap-1.5 text-rose-400 text-[11px]">
              <XCircle className="h-3.5 w-3.5" />
              <span>
                Rejected by <strong className="font-semibold">{action.rejected_by}</strong> on{" "}
                {formatDateTime(action.rejected_at)}
              </span>
            </div>
          )}

          {action.execution_result && (
            <div className="p-2 rounded bg-sky-950/30 border border-sky-800/40 text-sky-300 text-[11px]">
              <span className="text-zinc-400">Execution Result:</span>{" "}
              {action.execution_result.ledger_note || "Ledger adjustment posted."}
            </div>
          )}
        </div>

        {/* Card Actions Footer */}
        <div className="flex items-center justify-between border-t border-zinc-800 pt-3 text-xs">
          <div className="text-[11px] text-zinc-500 font-mono">
            Created: {formatDateTime(action.created_at)}
          </div>

          <div className="flex items-center gap-2">
            {isPending && (
              <>
                <button
                  onClick={() => setModalMode("reject")}
                  className="px-3 py-1.5 rounded border border-rose-900 bg-rose-950/40 text-rose-400 hover:bg-rose-900/50 font-semibold font-mono text-xs transition-colors"
                >
                  Reject
                </button>
                <button
                  onClick={() => setModalMode("approve")}
                  className="px-3 py-1.5 rounded bg-emerald-500 hover:bg-emerald-400 text-black font-semibold font-mono text-xs transition-colors"
                >
                  Authorize Action
                </button>
              </>
            )}

            {isApproved && (
              <button
                onClick={() => setModalMode("execute")}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded bg-sky-500 hover:bg-sky-400 text-black font-bold font-mono text-xs shadow-sm transition-colors"
              >
                <Play className="h-3 w-3 fill-current" />
                Execute Post
              </button>
            )}

            {isExecuted && (
              <span className="text-xs font-mono font-bold text-emerald-400 flex items-center gap-1">
                <CheckCircle2 className="h-4 w-4" /> Executed & Audited
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Decision Modal */}
      <ApprovalModal
        action={action}
        mode={modalMode}
        onClose={() => setModalMode(null)}
      />
    </>
  );
}
