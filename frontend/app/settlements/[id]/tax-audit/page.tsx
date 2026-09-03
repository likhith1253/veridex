"use client";

import React from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { settlementsApi } from "@/lib/api/settlementsApi";
import { TaxAuditPanel } from "@/components/settlements/TaxAuditPanel";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { ErrorState } from "@/components/common/ErrorState";
import { ArrowLeft, Landmark, FileCheck } from "lucide-react";

export default function SettlementTaxAuditPage() {
  const params = useParams();
  const router = useRouter();
  const id = Array.isArray(params?.id) ? params.id[0] : (params?.id as string);

  const {
    data: taxAudit,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["settlement-tax-audit", id],
    queryFn: () => settlementsApi.getTaxAudit(id),
    enabled: !!id,
  });

  if (error) {
    return (
      <ErrorState
        title="Failed to Load Tax Audit"
        message={error instanceof Error ? error.message : "Error connecting to backend"}
        onRetry={refetch}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Breadcrumb Header */}
      <div className="flex items-center gap-3">
        <Link
          href={`/settlements/${encodeURIComponent(id)}`}
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#171a23] hover:bg-[#1e222e] text-zinc-400 hover:text-zinc-200 border border-zinc-800 font-mono text-xs transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Back to Settlement Breakdown
        </Link>
        <span className="text-zinc-600">/</span>
        <span className="text-xs font-mono text-zinc-400">GST Tax Line Audit: {id}</span>
      </div>

      {/* Main Tax Audit Panel */}
      <TaxAuditPanel taxAudit={taxAudit} isLoading={isLoading} />
    </div>
  );
}
