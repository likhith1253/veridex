"use client";

import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { controllerApi } from "@/lib/api/controllerApi";
import { AuditTimeline } from "@/components/audit/AuditTimeline";
import { LoadingSkeleton } from "@/components/common/LoadingSkeleton";
import { EmptyState } from "@/components/common/EmptyState";
import { ErrorState } from "@/components/common/ErrorState";
import { Search, ShieldCheck } from "lucide-react";

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
    <div className="space-y-6 pb-12 select-none">
      {/* Institutional Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-[#D7D3CA]">
        <div>
          <span className="text-[10px] font-bold uppercase tracking-[0.14em] text-[#9E7B35]">
            AUDIT TRAIL
          </span>
          <h1 className="text-xl font-bold tracking-tight text-[#17191C] mt-0.5">
            Authoritative Financial Audit Trail
          </h1>
          <p className="text-xs text-[#555B61] mt-1 leading-relaxed">
            Append-only chronological record of every ingestion batch, reconciliation decision, and authorized action.
          </p>
        </div>

        <div className="flex items-center gap-2 flex-shrink-0">
          <span className="text-xs text-[#6F747A] font-medium">Recorded Events:</span>
          <span className="font-mono text-xs font-bold text-[#17191C] px-3 py-1 rounded-xs bg-[#FFFFFF] border border-[#D7D3CA] shadow-xs">
            {events?.length || 0} Events
          </span>
        </div>
      </div>

      {/* Filter / Search Bar */}
      <div className="bg-[#FFFFFF] border border-[#D7D3CA] rounded-xs p-3.5 flex flex-col sm:flex-row items-center justify-between gap-3 shadow-xs">
        <div className="relative w-full max-w-md">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-[#6F747A]" />
          <input
            type="text"
            value={searchTxn}
            onChange={(e) => setSearchTxn(e.target.value)}
            placeholder="Filter by Transaction / Reference ID..."
            className="w-full rounded-xs border border-[#D7D3CA] pl-9 pr-3 py-1.5 font-mono text-xs text-[#17191C] placeholder-[#6F747A] bg-[#F7F5F0] focus:bg-[#FFFFFF] focus:border-[#C9A96E] focus:outline-hidden transition-micro"
          />
        </div>

        <div className="flex items-center gap-2 text-xs text-[#555B61] font-medium">
          <ShieldCheck className="h-4 w-4 text-[#1E7B4D]" />
          <span>Append-Only Cryptographic Audit Log</span>
        </div>
      </div>

      {/* Audit Timeline Surface */}
      <div className="bg-[#FFFFFF] border border-[#D7D3CA] rounded-xs p-6 shadow-xs">
        {isLoading ? (
          <div className="pt-2">
            <LoadingSkeleton variant="table" count={4} />
          </div>
        ) : error ? (
          <ErrorState
            title="Failed to Load Audit Trail"
            message={error instanceof Error ? error.message : "Error connecting to backend"}
            onRetry={refetch}
          />
        ) : !events || events.length === 0 ? (
          <EmptyState
            title="No Matching Audit Events"
            description="Operational audit records will appear here as reconciliation batches and actions are executed."
          />
        ) : (
          <AuditTimeline events={events} />
        )}
      </div>
    </div>
  );
}
