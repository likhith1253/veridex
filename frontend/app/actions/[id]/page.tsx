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
      {/* Breadcrumb */}
      <div className="flex items-center gap-3">
        <Link
          href="/actions"
          className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-sm text-xs font-mono transition-micro text-[#8e96a0] hover:text-[#eceae6]"
          style={{
            borderColor: "var(--border-subtle)",
            background: "var(--surface-2)",
            border: "1px solid var(--border-subtle)",
          }}
        >
          <ArrowLeft className="h-3.5 w-3.5" /> Back to Actions Queue
        </Link>
        <span style={{ color: "var(--text-tertiary)" }}>/</span>
        <span className="text-xs font-mono text-[#eceae6]">Action: {id}</span>
      </div>

      {/* Main Action Review Card */}
      <ActionCard action={action} />
    </div>
  );
}
