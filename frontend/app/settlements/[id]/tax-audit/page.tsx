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
    <div className="space-y-6 pb-12 select-none">
      {/* Top Breadcrumb & Navigation */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-3 border-b border-[#E2DDD3]">
        <div className="flex items-center gap-2 text-xs font-mono text-[#6F747A]">
          <Link href="/app" className="hover:text-[#9E7B35] transition-colors">Control Center</Link>
          <span>/</span>
          <Link href="/settlements" className="hover:text-[#9E7B35] transition-colors">Settlements</Link>
          <span>/</span>
          <Link href={`/settlements/${encodeURIComponent(id)}`} className="hover:text-[#9E7B35] transition-colors">{id}</Link>
          <span>/</span>
          <span className="text-[#17191C] font-semibold">Tax Line Audit</span>
        </div>
        <Link
          href={`/settlements/${encodeURIComponent(id)}`}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xs text-xs font-medium bg-[#FFFFFF] border border-[#D7D3CA] text-[#17191C] hover:bg-[#F2EFE9] shadow-xs transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5 text-[#6F747A]" />
          <span>Back to Settlement</span>
        </Link>
      </div>

      {/* Main Tax Audit Panel */}
      <TaxAuditPanel taxAudit={taxAudit} isLoading={isLoading} />
    </div>
  );
}
