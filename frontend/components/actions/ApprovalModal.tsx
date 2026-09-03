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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-xs p-4">
      <div className="w-full max-w-md rounded-lg border border-[#222634] bg-[#11131a] p-6 shadow-2xl text-zinc-100">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
          <div className="flex items-center gap-2">
            <div
              className={`p-1.5 rounded border ${
                mode === "approve"
                  ? "bg-emerald-950/60 border-emerald-800/60 text-emerald-400"
                  : mode === "reject"
                  ? "bg-rose-950/60 border-rose-800/60 text-rose-400"
                  : "bg-sky-950/60 border-sky-800/60 text-sky-400"
              }`}
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
              <h2 className="text-sm font-bold font-mono text-zinc-100">
                {mode === "approve"
                  ? "Authorize Finance Action"
                  : mode === "reject"
                  ? "Reject Finance Action"
                  : "Execute Approved Action"}
              </h2>
              <p className="text-[11px] text-zinc-400 font-mono">ID: {action.id}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Action Summary Info */}
        <div className="my-4 p-3 rounded border border-zinc-800 bg-[#171a23] space-y-1.5 text-xs font-mono">
          <div className="flex justify-between text-zinc-400">
            <span>Action Type:</span>
            <span className="text-zinc-100 font-bold">{action.action_type}</span>
          </div>
          <div className="flex justify-between text-zinc-400">
            <span>Target Amount:</span>
            <span className="text-zinc-100 font-bold font-tabular">{formatINR(action.amount)}</span>
          </div>
          <div className="flex justify-between text-zinc-400">
            <span>Entity Ref:</span>
            <span className="text-zinc-300">{action.entity_id}</span>
          </div>
        </div>

        {/* Form Inputs */}
        <form onSubmit={handleSubmit} className="space-y-3.5 text-xs">
          <div>
            <label className="block text-zinc-400 mb-1 font-mono text-[11px]">
              Authorized Human Controller ID <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              required
              value={actorName}
              onChange={(e) => setActorName(e.target.value)}
              placeholder="e.g. JohnDoe_FinanceOps"
              className="w-full rounded border border-zinc-800 bg-[#171a23] px-3 py-2 text-zinc-100 font-mono text-xs focus:border-sky-500 focus:outline-hidden"
            />
            <p className="text-[10px] text-zinc-500 mt-0.5">
              Audited in immutable ledger. AI actor names are strictly rejected by policy bounds.
            </p>
          </div>

          {mode !== "execute" && (
            <div>
              <label className="block text-zinc-400 mb-1 font-mono text-[11px]">
                Decision Justification / Ledger Reason
              </label>
              <textarea
                rows={2}
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Enter justification for the audit trail..."
                className="w-full rounded border border-zinc-800 bg-[#171a23] px-3 py-1.5 text-zinc-100 text-xs focus:border-sky-500 focus:outline-hidden resize-none"
              />
            </div>
          )}

          {validationError && (
            <div className="p-2.5 rounded border border-rose-800/60 bg-rose-950/30 text-rose-300 text-xs flex items-center gap-2 font-mono">
              <AlertTriangle className="h-4 w-4 flex-shrink-0" />
              <span>{validationError}</span>
            </div>
          )}

          {error && (
            <div className="p-2.5 rounded border border-rose-800/60 bg-rose-950/30 text-rose-300 text-xs flex items-center gap-2 font-mono">
              <AlertTriangle className="h-4 w-4 flex-shrink-0" />
              <span>{error.message || "Operation failed."}</span>
            </div>
          )}

          {/* Controls */}
          <div className="flex items-center justify-end gap-2 border-t border-zinc-800 pt-3">
            <button
              type="button"
              onClick={onClose}
              className="px-3 py-1.5 rounded text-xs font-medium text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isPending}
              className={`inline-flex items-center gap-1.5 px-4 py-1.5 rounded text-xs font-bold transition-colors disabled:opacity-50 ${
                mode === "approve"
                  ? "bg-emerald-500 hover:bg-emerald-400 text-black"
                  : mode === "reject"
                  ? "bg-rose-500 hover:bg-rose-400 text-white"
                  : "bg-sky-500 hover:bg-sky-400 text-black"
              }`}
            >
              {isPending ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Processing...</span>
                </>
              ) : mode === "approve" ? (
                "Authorize Action"
              ) : mode === "reject" ? (
                "Reject Action"
              ) : (
                "Execute Bounded Action"
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
