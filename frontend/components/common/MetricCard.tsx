import React, { type ReactNode } from "react";
import { cn } from "@/lib/utils/formatters";

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  delta?: string;
  deltaType?: "positive" | "negative" | "neutral";
  icon?: ReactNode;
  badge?: ReactNode;
  statusBorder?: "emerald" | "rose" | "amber" | "indigo" | "none";
  className?: string;
}

export function MetricCard({
  title,
  value,
  subtitle,
  delta,
  deltaType = "neutral",
  icon,
  badge,
  statusBorder = "none",
  className,
}: MetricCardProps) {
  const borderStyles = {
    none: "border-zinc-800/80",
    emerald: "border-emerald-500/30 bg-emerald-950/10",
    rose: "border-rose-500/30 bg-rose-950/10",
    amber: "border-amber-500/30 bg-amber-950/10",
    indigo: "border-indigo-500/30 bg-indigo-950/10",
  }[statusBorder];

  const deltaColor = {
    positive: "text-emerald-400 bg-emerald-950/50 border-emerald-800/50",
    negative: "text-rose-400 bg-rose-950/50 border-rose-800/50",
    neutral: "text-zinc-400 bg-zinc-800/50 border-zinc-700/50",
  }[deltaType];

  return (
    <div
      className={cn(
        "rounded-lg border bg-[#11131a] p-4 text-zinc-100 transition-all hover:border-zinc-700",
        borderStyles,
        className
      )}
    >
      <div className="flex items-center justify-between gap-2 pb-2">
        <span className="text-xs font-medium uppercase tracking-wider text-zinc-400">
          {title}
        </span>
        {icon && <div className="text-zinc-500">{icon}</div>}
        {badge && <div>{badge}</div>}
      </div>

      <div className="flex items-baseline justify-between gap-2 pt-1">
        <div className="font-mono text-2xl font-bold tracking-tight text-zinc-100 font-tabular">
          {value}
        </div>
        {delta && (
          <span className={cn("inline-flex items-center px-1.5 py-0.5 rounded text-[11px] font-mono border", deltaColor)}>
            {delta}
          </span>
        )}
      </div>

      {subtitle && (
        <p className="mt-1.5 text-xs text-zinc-500 line-clamp-1">
          {subtitle}
        </p>
      )}
    </div>
  );
}
