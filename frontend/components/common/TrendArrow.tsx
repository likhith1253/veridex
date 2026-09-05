"use client";

import React from "react";
import { ArrowUp, ArrowDown, Minus } from "lucide-react";

interface TrendArrowProps {
  /** Real percentage-point or absolute change — never fabricated. Positive = up, negative = down. */
  delta: number | null | undefined;
  /**
   * Whether an increase in this metric is a good thing (default true).
   * For metrics like open-exception counts, a decrease is the good outcome —
   * pass `goodDirection="down"` there so the color stays semantically correct.
   */
  goodDirection?: "up" | "down";
  /** Format the displayed magnitude, e.g. (n) => `${n.toFixed(1)} pp`. Defaults to a plain percent. */
  format?: (n: number) => string;
  className?: string;
}

/**
 * Small up/down arrow + colored percentage change, respecting semantic
 * direction per metric (e.g. fewer open exceptions is "good" even though the
 * number itself decreased).
 */
export function TrendArrow({
  delta,
  goodDirection = "up",
  format,
  className,
}: TrendArrowProps) {
  if (delta === null || delta === undefined || !Number.isFinite(delta) || Math.abs(delta) < 0.0001) {
    return (
      <span
        className={`inline-flex items-center gap-1 text-[10px] font-mono font-semibold ${className || ""}`}
        style={{ color: "var(--text-tertiary)" }}
      >
        <Minus className="h-3 w-3" />
        <span>0.0%</span>
      </span>
    );
  }

  const isUp = delta > 0;
  const isGood = isUp ? goodDirection === "up" : goodDirection === "down";
  const color = isGood ? "var(--matched-text)" : "var(--variance-text)";
  const Icon = isUp ? ArrowUp : ArrowDown;
  const magnitude = format ? format(Math.abs(delta)) : `${Math.abs(delta).toFixed(1)}%`;

  return (
    <span
      className={`inline-flex items-center gap-1 text-[10px] font-mono font-semibold ${className || ""}`}
      style={{ color }}
    >
      <Icon className="h-3 w-3" />
      <span>{magnitude}</span>
    </span>
  );
}
