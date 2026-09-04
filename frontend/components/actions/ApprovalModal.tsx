"use client";

import React, { useState } from "react";
import { X, ShieldCheck, ShieldAlert, Loader2, UserCheck, AlertTriangle } from "lucide-react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { actionsApi } from "@/lib/api/actionsApi";
import type { FinanceAction } from "@/types/actions";
import { formatINR } from "@/lib/utils/formatters";

interface ApprovalModalProps {
  action: FinanceAction | null;
  mode: "approve" | "reject" | "execute" | null;
  onClose: () => void;
}

export function ApprovalModal({ action, mode, onClose }: ApprovalModalProps) {
  const queryClient = useQueryClient();
  const [actorName, setActorName] = useState("FinanceController_Ops");
  const [reason, setReason] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  const approveMutation = useMutation({
    mutationFn: () => {
      if (!action) throw new Error("No action selected");
      return actionsApi.approveAction(action.id, {
        actor: actorName,
        reason: reason || "Approved following invoice validation against ledger records.",
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries();
      onClose();
    },
  });

  const rejectMutation = useMutation({
    mutationFn: () => {
      if (!action) throw new Error("No action selected");
      return actionsApi.rejectAction(action.id, {
        actor: actorName,
        reason: reason || "Rejected due to insufficient supporting documentation.",
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries();
      onClose();
    },
  });

  const executeMutation = useMutation({
    mutationFn: () => {
      if (!action) throw new Error("No action selected");
      return actionsApi.executeAction(action.id, {
        actor: actorName,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries();
      onClose();
    },
  });

  if (!action || !mode) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    // Human actor policy validation
    const lowerActor = actorName.toLowerCase();
    if (lowerActor.includes("ai") || lowerActor.includes("agent") || lowerActor.includes("bot")) {
      setValidationError("Policy Violation: AI agents cannot approve or execute finance actions. Must be an authorized human actor.");
      return;
    }

    if (!actorName.trim()) {
      setValidationError("Actor identity is required for cryptographic audit logging.");
      return;
    }

    if (mode === "approve") {
      approveMutation.mutate();
    } else if (mode === "reject") {
      rejectMutation.mutate();
    } else if (mode === "execute") {
      executeMutation.mutate();
    }
  };

  const isPending = approveMutation.isPending || rejectMutation.isPending || executeMutation.isPending;
  const error = (approveMutation.error || rejectMutation.error || executeMutation.error) as Error | null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-xs p-4">
      <div
        className="w-full max-w-md rounded-sm border p-6 text-[#eceae6] shadow-2xl text-xs select-none"
        style={{
          borderColor: "var(--border-standard)",
          background: "var(--surface-1)",
        }}
      >
        {/* Header */}
        <div
          className="flex items-center justify-between pb-4"
          style={{ borderBottom: "1px solid var(--border-subtle)" }}
        >
          <div className="flex items-center gap-2">
            <div
              className="p-1.5 rounded-sm border"
              style={{
                borderColor: mode === "approve"
                  ? "var(--accent-border)"
                  : mode === "reject"
                  ? "var(--variance-border)"
                  : "var(--matched-border)",
                background: mode === "approve"
                  ? "var(--accent-dim)"
                  : mode === "reject"
                  ? "var(--variance-bg)"
                  : "var(--matched-bg)",
                color: mode === "approve"
                  ? "var(--accent)"
                  : mode === "reject"
                  ? "var(--variance-text)"
                  : "var(--matched-text)",
              }}
            >
              {mode === "approve" ? (
                <ShieldCheck className="h-4 w-4" />
              ) : mode === "reject" ? (
                <ShieldAlert className="h-4 w-4" />
              ) : (
                <UserCheck className="h-4 w-4" />
              )}
            </div>
            <div>
              <h2 className="text-xs font-bold uppercase tracking-wider text-[#eceae6]">
                {mode === "approve" && "Authorize Financial Action"}
                {mode === "reject" && "Reject Action Recommendation"}
                {mode === "execute" && "Trigger Bounded Execution"}
              </h2>
              <p className="text-[10px] text-[#8e96a0]">
                Policy-Gated Human-in-the-Loop Control
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded text-[#8e96a0] hover:text-[#eceae6] transition-micro"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Action Summary Info */}
        <div
          className="my-4 p-3 rounded-sm border text-xs space-y-1.5"
          style={{
            borderColor: "var(--border-subtle)",
            background: "var(--surface-2)",
          }}
        >
          <div className="flex justify-between">
            <span className="text-[#8e96a0]">Action:</span>
            <span className="font-semibold text-[#eceae6]">{action.action_type}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#8e96a0]">Target ID:</span>
            <span className="text-[#eceae6]">{action.entity_id}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-[#8e96a0]">Amount:</span>
            <span className="font-bold text-[#eceae6] font-tabular">{formatINR(action.amount)}</span>
          </div>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="space-y-4 text-xs">
          {/* Actor Name (Mandatory for audit trail) */}
          <div>
            <label className="block text-[#8e96a0] mb-1 text-[11px]">
              Human Operator ID (Mandatory Audit Identity)
            </label>
            <input
              type="text"
              value={actorName}
              onChange={(e) => setActorName(e.target.value)}
              placeholder="e.g. FinanceLead_JohnDoe"
              disabled={isPending}
              className="w-full rounded-sm border px-3 py-2 text-xs font-mono text-[#eceae6] transition-micro disabled:opacity-50"
              style={{
                borderColor: "var(--border-standard)",
                background: "var(--surface-3)",
              }}
            />
            <p className="mt-1 text-[10px] text-[#525c66]">
              Must identify an authorized human operator. Automated agent usernames are rejected by policy.
            </p>
          </div>

          {/* Decision Rationale */}
          {mode !== "execute" && (
            <div>
              <label className="block text-[#8e96a0] mb-1 text-[11px]">
                Decision Rationale &amp; Audit Explanation
              </label>
              <textarea
                rows={3}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder={
                  mode === "approve"
                    ? "Verified against vendor invoices. Discrepancy confirmed within tolerance."
                    : "Documentation mismatch. Requiring merchant clarification before adjustment."
                }
                disabled={isPending}
                className="w-full rounded-sm border px-3 py-2 text-xs font-sans text-[#eceae6] transition-micro disabled:opacity-50"
                style={{
                  borderColor: "var(--border-standard)",
                  background: "var(--surface-3)",
                }}
              />
            </div>
          )}

          {/* Validation or API Error Alert */}
          {(validationError || error) && (
            <div
              className="p-3 rounded-sm border text-xs flex items-center gap-2"
              style={{
                borderColor: "var(--variance-border)",
                background: "var(--variance-bg)",
                color: "var(--variance-text)",
              }}
            >
              <AlertTriangle className="h-4 w-4 flex-shrink-0" />
              <span>{validationError || error?.message}</span>
            </div>
          )}

          {/* Modal Footer Controls */}
          <div
            className="flex items-center justify-end gap-2 pt-4"
            style={{ borderTop: "1px solid var(--border-subtle)" }}
          >
            <button
              type="button"
              onClick={onClose}
              disabled={isPending}
              className="px-3 py-1.5 rounded-sm text-xs font-semibold text-[#8e96a0] hover:text-[#eceae6] transition-micro"
            >
              Cancel
            </button>

            <button
              type="submit"
              disabled={isPending}
              className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-sm text-xs font-bold transition-micro disabled:opacity-50"
              style={{
                color: "var(--bg)",
                background: mode === "approve"
                  ? "var(--accent)"
                  : mode === "reject"
                  ? "var(--variance-text)"
                  : "var(--matched-text)",
              }}
            >
              {isPending && <Loader2 className="h-3 w-3 animate-spin" />}
              <span>
                {mode === "approve" && "Confirm Human Approval"}
                {mode === "reject" && "Confirm Rejection"}
                {mode === "execute" && "Execute Action"}
              </span>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
