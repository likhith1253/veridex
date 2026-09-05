"use client";

import React from "react";
import { motion } from "framer-motion";

interface RadialGaugeProps {
  /** Real percentage value, 0-100. */
  value: number;
  size?: number;
  strokeWidth?: number;
  label?: string;
  sublabel?: string;
  /** Gold by default — stays inside the editorial palette. */
  color?: string;
  trackColor?: string;
  className?: string;
}

/**
 * Inline-SVG radial/donut gauge. No charting library — a single circle whose
 * stroke-dashoffset is animated on mount via framer-motion to reveal the real
 * fetched percentage.
 */
export function RadialGauge({
  value,
  size = 168,
  strokeWidth = 12,
  label,
  sublabel,
  color = "var(--accent-deep)",
  trackColor = "var(--surface-3)",
  className,
}: RadialGaugeProps) {
  const safe = Math.max(0, Math.min(100, Number.isFinite(value) ? value : 0));
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference * (1 - safe / 100);

  return (
    <div
      className={className}
      style={{ width: size, height: size, position: "relative" }}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={trackColor}
          strokeWidth={strokeWidth}
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: dashOffset }}
          transition={{ duration: 1.1, ease: [0.16, 1, 0.3, 1] }}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <motion.span
          initial={{ opacity: 0, y: 4 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.35, duration: 0.5, ease: "easeOut" }}
          className="font-mono font-bold font-tabular"
          style={{ fontSize: size * 0.19, color: "var(--text-primary)", lineHeight: 1 }}
        >
          {safe.toFixed(1)}%
        </motion.span>
        {label && (
          <span
            className="uppercase font-bold tracking-wider mt-1.5 text-center px-2"
            style={{ fontSize: 10, color: "var(--text-tertiary)" }}
          >
            {label}
          </span>
        )}
        {sublabel && (
          <span
            className="mt-0.5 text-center px-2"
            style={{ fontSize: 10, color: "var(--text-tertiary)" }}
          >
            {sublabel}
          </span>
        )}
      </div>
    </div>
  );
}
