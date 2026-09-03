"use client";

import React, { useState, type ReactNode } from "react";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";
import { RunBatchModal } from "../reconciliation/RunBatchModal";
import { CopilotDrawer } from "../copilot/CopilotDrawer";

export function AppShell({ children }: { children: ReactNode }) {
  const [isBatchModalOpen, setIsBatchModalOpen] = useState(false);
  const [isCopilotOpen, setIsCopilotOpen] = useState(false);

  return (
    <div className="flex h-screen overflow-hidden bg-[#090a0f] text-zinc-100">
      {/* Sidebar Navigation */}
      <Sidebar />

      {/* Main Column */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Topbar */}
        <Topbar
          onOpenBatchModal={() => setIsBatchModalOpen(true)}
          onToggleCopilot={() => setIsCopilotOpen((prev) => !prev)}
        />

        {/* Workspace Body */}
        <main className="flex-1 overflow-y-auto p-6 bg-[#090a0f]">
          {children}
        </main>
      </div>

      {/* Global Modals & Drawers */}
      <RunBatchModal
        isOpen={isBatchModalOpen}
        onClose={() => setIsBatchModalOpen(false)}
      />
      <CopilotDrawer
        isOpen={isCopilotOpen}
        onClose={() => setIsCopilotOpen(false)}
      />
    </div>
  );
}
