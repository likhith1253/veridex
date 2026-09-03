import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Decimal-safe formatter for Indian Rupee currency strings/numbers.
 * Formats: 500000 -> "INR 5,00,000.00"
 */
export function formatINR(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "INR 0.00";
  }

  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) {
    return "INR 0.00";
  }

  const isNegative = num < 0;
  const absNum = Math.abs(num);

  const parts = absNum.toFixed(2).split(".");
  let integerPart = parts[0];
  const decimalPart = parts[1];

  // Indian Numbering System grouping: last 3 digits, then groups of 2
  let lastThree = integerPart.substring(integerPart.length - 3);
  const otherNumbers = integerPart.substring(0, integerPart.length - 3);
  if (otherNumbers !== "") {
    lastThree = "," + lastThree;
  }
  const formattedInteger = otherNumbers.replace(/\B(?=(\d{2})+(?!\d))/g, ",") + lastThree;

  const result = `INR ${formattedInteger}.${decimalPart}`;
  return isNegative ? `-${result}` : result;
}

/**
 * Explicit signed variance formatter:
 * e.g. "+INR 150.00", "-INR 42.00", "INR 0.00"
 */
export function formatVariance(value: number | string | null | undefined): {
  text: string;
  isPositive: boolean;
  isNegative: boolean;
  isZero: boolean;
} {
  if (value === null || value === undefined || value === "") {
    return { text: "INR 0.00", isPositive: false, isNegative: false, isZero: true };
  }

  const num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num) || Math.abs(num) < 0.001) {
    return { text: "INR 0.00", isPositive: false, isNegative: false, isZero: true };
  }

  const formatted = formatINR(Math.abs(num));
  if (num > 0) {
    return { text: `+${formatted}`, isPositive: true, isNegative: false, isZero: false };
  } else {
    return { text: `-${formatted}`, isPositive: false, isNegative: true, isZero: false };
  }
}

/**
 * Format decimal as percentage (e.g. 0.9474 -> "94.74%", 94.74 -> "94.74%")
 */
export function formatPercent(value: number | string | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "0.00%";
  }
  let num = typeof value === "string" ? parseFloat(value) : value;
  if (isNaN(num)) return "0.00%";

  // Normalize if fraction (e.g. 0.95 -> 95.00)
  if (num <= 1.0 && num > 0) {
    num = num * 100;
  }
  return `${num.toFixed(2)}%`;
}

/**
 * Format ISO datetime into compact tabular string:
 * e.g. "2026-09-03 16:18:29 UTC"
 */
export function formatDateTime(isoString?: string | null): string {
  if (!isoString) return "—";
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return d.toISOString().replace("T", " ").substring(0, 19) + " UTC";
  } catch {
    return isoString;
  }
}

/**
 * Relative time ago (e.g. "2m ago", "1h ago")
 */
export function formatTimeAgo(isoString?: string | null): string {
  if (!isoString) return "—";
  try {
    const d = new Date(isoString);
    const now = new Date();
    const diffSecs = Math.floor((now.getTime() - d.getTime()) / 1000);
    if (diffSecs < 60) return `${Math.max(1, diffSecs)}s ago`;
    const diffMins = Math.floor(diffSecs / 60);
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  } catch {
    return isoString;
  }
}
