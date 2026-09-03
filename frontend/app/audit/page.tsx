"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { controllerApi } from "@/lib/api/controllerApi";
import { AuditTimeline } from "@/components/audit/AuditTimeline";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { History, Search, ShieldCheck } from "lucide-react";

export default function AuditPage() {
  const [searchTxn, setSearchTxn] = useState("");

  const {
    data: events,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["audit-timeline", searchTxn],
    queryFn: () =>
      controllerApi.getAuditTimeline({
        transaction_id: searchTxn ? searchTxn : undefined,
      }),
    refetchInterval: 10000,
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#222634] pb-4">
        <div>
          <h1 className="text-lg font-bold font-mono text-zinc-100 flex items-center gap-2">
            Cryptographic & Immutable Audit Trail
          </h1>
          <p className="text-xs text-zinc-400 mt-0.5">
            Append-only chronological record of every data ingestion, reconciliation match, exception diagnosis, and human authorization.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="font-mono text-xs text-zinc-400">Recorded Events:</span>
          <span className="font-mono text-sm font-bold text-zinc-100 px-2.5 py-1 rounded bg-[#171a23] border border-zinc-800">
            {events?.length || 0} Events
          </span>
        </div>
      </div>

      {/* Filter / Search Bar */}
      <div className="rounded-lg border border-[#222634] bg-[#11131a] p-4 flex items-center justify-between gap-3 text-xs font-mono">
        <div className="relative w-full max-w-md">
          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-zinc-500" />
          <input
            type="text"
            value={searchTxn}
            onChange={(e) => setSearchTxn(e.target.value)}
            placeholder="Filter by Transaction / Reference ID..."
            className="w-full rounded border border-zinc-800 bg-[#171a23] pl-9 pr-3 py-1.5 text-zinc-200 placeholder-zinc-500 focus:border-sky-500 focus:outline-hidden"
          />
        </div>

        <div className="flex items-center gap-2 text-zinc-400">
          <ShieldCheck className="h-4 w-4 text-emerald-400" />
          <span>Append-Only Ledger</span>
        </div>
      </div>

      {/* Audit Timeline Card */}
      <div className="rounded-lg border border-[#222634] bg-[#11131a] p-5">
        {isLoading ? (
          <LoadingSkeleton variant="table" count={5} />
        ) : error ? (
          <ErrorState
            title="Failed to Load Audit Events"
            message={error instanceof Error ? error.message : "Error connecting to backend"}
            onRetry={refetch}
          />
        ) : !events || events.length === 0 ? (
          <EmptyState
            title="No Audit Events Recorded"
            description="Audit events are automatically generated as batches are ingested and actions are approved."
          />
        ) : (
          <AuditTimeline events={events} isLoading={isLoading} />
        )}
      </div>
    </div>
  );
}
