import React from "react";
import { cn } from "@/lib/utils/formatters";

interface StatusBadgeProps {
  status?: string | null;
  className?: string;
}

type BadgeVariant = "matched" | "exception" | "pending" | "ml" | "muted";

function classify(status?: string | null): BadgeVariant {
  const s = (status || "unknown").toUpperCase();
  if (
    ["MATCHED", "COMPLETED", "RESOLVED", "EXECUTED", "CONFIRMED", "PAID",
     "CAPTURED", "HEALTHY", "RECONCILED", "CLOSED"].some(k => s.includes(k))
  ) return "matched";
  if (
    ["VARIANCE", "EXCEPTION", "FAILED", "REJECTED", "DISCREPANT", "OVER_REFUND",
     "MISMATCH", "OPEN"].some(k => s.includes(k))
  ) return "exception";
  if (
    ["PENDING", "PENDING_APPROVAL", "INVESTIGATING", "AUTHORIZED", "ATTEMPTED",
     "RECOMMENDED", "REVIEW"].some(k => s.includes(k))
  ) return "pending";
  if (
    ["ML_RECOVERED", "INFERRED", "ESCALATED", "RUNNING"].some(k => s.includes(k))
  ) return "ml";
  return "muted";
}

const STYLES: Record<BadgeVariant, React.CSSProperties> = {
  matched: {
    color: "var(--matched-text)",
    background: "var(--matched-bg)",
    borderColor: "var(--matched-border)",
  },
  exception: {
    color: "var(--variance-text)",
    background: "var(--variance-bg)",
    borderColor: "var(--variance-border)",
  },
  pending: {
    color: "var(--pending-text)",
    background: "var(--pending-bg)",
    borderColor: "var(--pending-border)",
  },
  ml: {
    color: "var(--ml-text)",
    background: "var(--ml-bg)",
    borderColor: "var(--ml-border)",
  },
  muted: {
    color: "var(--text-tertiary)",
    background: "var(--surface-3)",
    borderColor: "var(--border-subtle)",
  },
};

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const variant = classify(status);
  const label = (status || "Unknown")
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, c => c.toUpperCase());

  return (
    <span
      className={cn(
        "inline-flex items-center px-1.5 py-px rounded-sm font-mono text-[10px] font-semibold border tracking-wide",
        className
      )}
      style={STYLES[variant]}
    >
      {label}
    </span>
  );
}
