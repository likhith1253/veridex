import React from "react";
import { cn, formatPercent } from "@/lib/utils/formatters";

interface ConfidenceBadgeProps {
  confidence: number;
  className?: string;
}

export function ConfidenceBadge({ confidence, className }: ConfidenceBadgeProps) {
  const norm = confidence > 1 ? confidence / 100 : confidence;
  let color = "text-emerald-400 bg-emerald-950/40 border-emerald-800/50";

  if (norm < 0.7) {
    color = "text-rose-400 bg-rose-950/40 border-rose-800/50";
  } else if (norm < 0.85) {
    color = "text-amber-400 bg-amber-950/40 border-amber-800/50";
  }

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded font-mono text-xs font-semibold border",
        color,
        className
      )}
      title={`Confidence score: ${(norm * 100).toFixed(1)}%`}
    >
      <span className="text-[10px] text-zinc-500 font-sans">CONF</span>
      {formatPercent(norm)}
    </span>
  );
}
