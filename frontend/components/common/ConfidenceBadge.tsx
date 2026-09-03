import React from "react";
import { cn, formatPercent } from "@/lib/utils/formatters";

interface ConfidenceBadgeProps {
  confidence: number;
  className?: string;
}

export function ConfidenceBadge({ confidence, className }: ConfidenceBadgeProps) {
  const rawConf = typeof confidence === "number" && Number.isFinite(confidence) ? confidence : 0;
  const norm = rawConf > 1 ? rawConf / 100 : rawConf;

  let badgeStyle: React.CSSProperties = {
    color: "var(--matched-text)",
    background: "var(--matched-bg)",
    border: "1px solid var(--matched-border)",
  };

  if (norm < 0.7) {
    badgeStyle = {
      color: "var(--variance-text)",
      background: "var(--variance-bg)",
      border: "1px solid var(--variance-border)",
    };
  } else if (norm < 0.85) {
    badgeStyle = {
      color: "var(--pending-text)",
      background: "var(--pending-bg)",
      border: "1px solid var(--pending-border)",
    };
  }

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-1.5 py-px rounded-xs font-mono text-[10px] font-semibold tracking-wide",
        className
      )}
      style={badgeStyle}
      title={`Confidence score: ${(norm * 100).toFixed(1)}%`}
    >
      <span className="text-[9px] text-[#8e96a0]">CONF</span>
      <span className="font-tabular">{formatPercent(norm)}</span>
    </span>
  );
}
