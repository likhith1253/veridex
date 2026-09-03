import React from "react";
import { cn } from "@/lib/utils/formatters";

interface StatusBadgeProps {
  status: string;
  className?: string;
  size?: "sm" | "md";
}

export function StatusBadge({ status, className, size = "sm" }: StatusBadgeProps) {
  const norm = (status || "unknown").toUpperCase();

  let styles = "bg-zinc-800 text-zinc-300 border-zinc-700";

  if (["MATCHED", "COMPLETED", "RESOLVED", "EXECUTED", "CONFIRMED", "PAID", "CAPTURED"].includes(norm)) {
    styles = "bg-emerald-950/60 text-emerald-400 border-emerald-800/60";
  } else if (["VARIANCE", "EXCEPTION", "FAILED", "REJECTED", "DISCREPANT", "OVER_REFUND"].includes(norm)) {
    styles = "bg-rose-950/60 text-rose-400 border-rose-800/60";
  } else if (["PENDING", "PENDING_APPROVAL", "OPEN", "INVESTIGATING", "AUTHORIZED", "ATTEMPTED"].includes(norm)) {
    styles = "bg-amber-950/60 text-amber-400 border-amber-800/60";
  } else if (["ML_RECOVERED", "INFERRED", "ESCALATED"].includes(norm)) {
    styles = "bg-purple-950/60 text-purple-400 border-purple-800/60";
  } else if (["INSUFFICIENT_EVIDENCE", "UNRESOLVED"].includes(norm)) {
    styles = "bg-zinc-900 text-zinc-400 border-zinc-700/80";
  }

  const padding = size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-xs";

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 font-mono font-medium rounded border tracking-wider",
        padding,
        styles,
        className
      )}
    >
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-80" />
      {norm.replace(/_/g, " ")}
    </span>
  );
}
