"use client";

import React, { useEffect, useRef, useState } from "react";

interface CountUpProps {
  /** Real numeric value fetched from the API — never fabricated. */
  value: number;
  /** Optional formatter applied to the animated number on every frame (e.g. formatINR, formatPercent). */
  format?: (n: number) => string;
  /** Number of decimal places to keep if no `format` is supplied. */
  decimals?: number;
  className?: string;
  /** Animation duration in ms. */
  durationMs?: number;
}

const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);

/**
 * Animates a real fetched numeric value from its previous value (or 0 on first
 * mount) up/down to the current value using a plain requestAnimationFrame
 * tween — no framer-motion dependency, so it can never get stuck mid-flight
 * regardless of the viewer's reduced-motion/browser environment. Never
 * invents numbers — it only tweens between real values passed in via props.
 */
export function CountUp({
  value,
  format,
  decimals = 0,
  className,
  durationMs = 900,
}: CountUpProps) {
  const safeValue = Number.isFinite(value) ? value : 0;
  const [display, setDisplay] = useState(0);
  const fromRef = useRef(0);
  const rafRef = useRef<number | null>(null);
  const hasMounted = useRef(false);

  useEffect(() => {
    const from = hasMounted.current ? fromRef.current : 0;
    hasMounted.current = true;
    const to = safeValue;
    const start = performance.now();

    if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);

    // Respect reduced-motion preference by snapping instantly.
    const prefersReduced =
      typeof window !== "undefined" &&
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (prefersReduced || from === to) {
      setDisplay(to);
      fromRef.current = to;
      return;
    }

    const tick = (now: number) => {
      const elapsed = now - start;
      const t = Math.min(1, elapsed / durationMs);
      const eased = easeOutCubic(t);
      const current = from + (to - from) * eased;
      setDisplay(current);
      if (t < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        fromRef.current = to;
      }
    };
    rafRef.current = requestAnimationFrame(tick);

    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [safeValue]);

  const rendered = format ? format(display) : display.toFixed(decimals);

  return <span className={className}>{rendered}</span>;
}
