"use client";

import React, { useState, useCallback } from "react";
import { Copy, Check } from "lucide-react";

interface TechnicalReferenceProps {
  /** The full technical ID / reference string */
  id: string;
  /** Optional human-readable label prefix e.g. "ref" */
  label?: string;
  /** Max characters visible before truncation. Default: 22 */
  maxVisible?: number;
  /** If true renders as an inline span rather than a flex row */
  inline?: boolean;
  /** Additional className */
  className?: string;
}

/**
 * TechnicalReference
 *
 * Renders a technical identifier (run ID, exception ID, UUID, UTR, settlement ID)
 * in a compact, copy-able format. Truncates long IDs with a tooltip showing the full
 * value. Never deletes traceability — just moves it to the appropriate disclosure level.
 *
 * Usage:
 *   <TechnicalReference id={exception.exception_id} />
 *   <TechnicalReference id={run.run_id} label="run" maxVisible={18} />
 */
export function TechnicalReference({
  id,
  label,
  maxVisible = 22,
  inline = false,
  className = "",
}: TechnicalReferenceProps) {
  const [copied, setCopied] = useState(false);

  const displayId =
    id && id.length > maxVisible
      ? `${id.slice(0, maxVisible - 1)}…`
      : (id || "—");

  const handleCopy = useCallback(
    async (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      if (!id) return;
      try {
        await navigator.clipboard.writeText(id);
        setCopied(true);
        setTimeout(() => setCopied(false), 1500);
      } catch {
        // clipboard not available — silent
      }
    },
    [id]
  );

  if (!id) return <span className="text-[#6F747A] font-mono text-[11px]">—</span>;

  const idEl = (
    <span
      title={id}
      className="font-mono text-[11px] text-[#555B61] cursor-default select-all"
    >
      {label && (
        <span className="text-[#9E7B35] text-[10px] font-semibold mr-1 not-italic">
          {label}:
        </span>
      )}
      {displayId}
    </span>
  );

  const copyBtn = (
    <button
      onClick={handleCopy}
      title={`Copy: ${id}`}
      className="ml-1 p-0.5 rounded text-[#9E7B35] hover:text-[#C9A96E] opacity-0 group-hover:opacity-100 transition-opacity focus:opacity-100 focus:outline-hidden"
      aria-label={`Copy ${label || "reference"}: ${id}`}
    >
      {copied ? (
        <Check className="h-2.5 w-2.5 text-[#1E7B4D]" />
      ) : (
        <Copy className="h-2.5 w-2.5" />
      )}
    </button>
  );

  if (inline) {
    return (
      <span className={`group inline-flex items-center gap-0 ${className}`}>
        {idEl}
        {copyBtn}
      </span>
    );
  }

  return (
    <span
      className={`group inline-flex items-center gap-0 px-2 py-0.5 rounded-xs bg-[#F1EFE9] border border-[#E2DDD3] ${className}`}
    >
      {idEl}
      {copyBtn}
    </span>
  );
}
