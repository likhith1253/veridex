"use client";

import React from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { actionsApi } from "@/lib/api/actionsApi";
import { ActionCard } from "@/components/actions/ActionCard";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { ErrorState } from "@/components/common/ErrorState";
import { ArrowLeft } from "lucide-react";

export default function ActionDetailPage() {
  const params = useParams();
  const id = Array.isArray(params?.id) ? params.id[0] : (params?.id as string);

  const {
    data: action,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["action-detail", id],
    queryFn: () => actionsApi.getActionById(id),
    enabled: !!id,
  });

  if (isLoading) {
    return (
      <div className="space-y-6">
        <div className="h-6 w-48 skeleton rounded-xs" />
        <LoadingSkeleton variant="card" count={1} />
      </div>
    );
  }

  if (error || !action) {
    return (
      <ErrorState
        title="Action Not Found"
        message={`Could not locate finance action ID: ${id}`}
        onRetry={refetch}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Breadcrumb & Navigation */}
      <div className="flex flex-wrap items-center justify-between gap-4 pb-3 border-b border-[#E2DDD3]">
        <div className="flex items-center gap-2 text-xs font-mono text-[#6F747A]">
          <Link href="/app" className="hover:text-[#9E7B35] transition-colors">Control Center</Link>
          <span>/</span>
          <Link href="/actions" className="hover:text-[#9E7B35] transition-colors">Actions</Link>
          <span>/</span>
          <span className="text-[#17191C] font-semibold">{id}</span>
        </div>
        <Link
          href="/actions"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xs text-xs font-medium bg-[#FFFFFF] border border-[#D7D3CA] text-[#17191C] hover:bg-[#F2EFE9] shadow-xs transition-colors"
        >
          <ArrowLeft className="h-3.5 w-3.5 text-[#6F747A]" />
          <span>Back to Actions</span>
        </Link>
      </div>

      {/* Main Action Review Card */}
      <ActionCard action={action} />
    </div>
  );
}
