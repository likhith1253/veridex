"use client";

import React, { useState } from "react";
import { X, Send, Sparkles, Loader2, Database, ShieldAlert, CheckCircle2 } from "lucide-react";
import { useMutation } from "@tanstack/react-query";
import { controllerApi } from "@/lib/api/controllerApi";
import type { CopilotQueryResponse } from "@/types/controller";

interface CopilotDrawerProps {
  isOpen: boolean;
  onClose: () => void;
}

export function CopilotDrawer({ isOpen, onClose }: CopilotDrawerProps) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<
    Array<{
      role: "user" | "assistant";
      text: string;
      data?: CopilotQueryResponse;
    }>
  >([
    {
      role: "assistant",
      text: "I am the Veridex Finance Copilot. Ask me about reconciliation status, unreconciled exposure, tax line variances, or exception root causes.",
    },
  ]);

  const queryMutation = useMutation({
    mutationFn: (q: string) => controllerApi.queryCopilot({ question: q }),
    onSuccess: (data) => {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: data.direct_answer || data.answer || data.interpretation || "Query completed.",
          data: data,
        },
      ]);
    },
    onError: (err: Error) => {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          text: `Query error: ${err.message}`,
        },
      ]);
    },
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || queryMutation.isPending) return;

    const userText = question.trim();
    setMessages((prev) => [...prev, { role: "user", text: userText }]);
    setQuestion("");
    queryMutation.mutate(userText);
  };

  const sampleQuestions = [
    "What is the total unreconciled financial exposure?",
    "What is the overall reconciliation match rate?",
    "Explain the top exception root cause.",
    "Are there any tax line discrepancies on settlements?",
  ];

  if (!isOpen) return null;

  return (
    <aside className="fixed inset-y-0 right-0 z-50 w-96 border-l border-[#222634] bg-[#0d0f17] shadow-2xl flex flex-col text-zinc-100">
      {/* Header */}
      <div className="h-14 px-4 border-b border-[#222634] flex items-center justify-between bg-[#11131a]">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded bg-indigo-950/70 border border-indigo-800/60 text-indigo-400">
            <Sparkles className="h-4 w-4" />
          </div>
          <div>
            <h2 className="text-xs font-bold font-mono text-zinc-100">Grounded Finance Copilot</h2>
            <p className="text-[10px] text-zinc-500">PostgreSQL fact-verified Q&A</p>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Messages Feed */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3.5 text-xs">
        {messages.map((m, idx) => (
          <div
            key={idx}
            className={`p-3 rounded-lg border ${
              m.role === "user"
                ? "bg-sky-950/30 border-sky-800/40 text-sky-200 ml-6 font-mono"
                : "bg-[#141722] border-zinc-800/80 text-zinc-300 mr-2"
            }`}
          >
            <div className="flex items-center justify-between gap-2 mb-1 text-[10px] text-zinc-500 font-mono uppercase">
              <span>{m.role === "user" ? "Controller" : "Veridex AI"}</span>
              {m.data?.confidence !== undefined && m.data.confidence !== null && (
                <span className="text-emerald-400">
                  {(m.data.confidence * 100).toFixed(0)}% Conf
                </span>
              )}
            </div>
            <p className="leading-relaxed whitespace-pre-wrap">{m.text}</p>

            {/* Evidence References */}
            {m.data?.sql_facts_used && m.data.sql_facts_used.length > 0 && (
              <div className="mt-2.5 pt-2 border-t border-zinc-800/60 text-[10px] space-y-1 text-zinc-400 font-mono">
                <div className="flex items-center gap-1 text-zinc-500 font-semibold">
                  <Database className="h-3 w-3" /> Grounded Database Facts:
                </div>
                {m.data.sql_facts_used.map((fact, fIdx) => (
                  <div key={fIdx} className="text-zinc-300 bg-zinc-900/80 px-1.5 py-0.5 rounded border border-zinc-800">
                    {fact}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}

        {queryMutation.isPending && (
          <div className="flex items-center gap-2 p-3 rounded bg-zinc-900/60 border border-zinc-800 text-zinc-400 text-xs">
            <Loader2 className="h-3.5 w-3.5 animate-spin text-indigo-400" />
            <span>Verifying PostgreSQL facts & evaluating claims...</span>
          </div>
        )}
      </div>

      {/* Suggested Questions */}
      <div className="px-4 py-2 border-t border-[#222634] bg-[#0c0e14] space-y-1">
        <div className="text-[10px] uppercase font-mono font-semibold text-zinc-500">Quick Queries</div>
        <div className="flex flex-wrap gap-1">
          {sampleQuestions.map((sq, i) => (
            <button
              key={i}
              onClick={() => {
                setQuestion(sq);
              }}
              className="text-[10px] px-2 py-1 rounded bg-[#171a23] hover:bg-[#202533] border border-zinc-800 text-zinc-400 hover:text-zinc-200 truncate max-w-full text-left transition-colors"
            >
              {sq}
            </button>
          ))}
        </div>
      </div>

      {/* Query Input */}
      <form onSubmit={handleSubmit} className="p-3 border-t border-[#222634] bg-[#11131a] flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask grounded controller question..."
          className="flex-1 rounded border border-zinc-800 bg-[#171a23] px-3 py-1.5 text-xs text-zinc-100 placeholder-zinc-500 focus:border-sky-500 focus:outline-hidden"
        />
        <button
          type="submit"
          disabled={!question.trim() || queryMutation.isPending}
          className="px-3 py-1.5 rounded bg-indigo-600 hover:bg-indigo-500 text-white disabled:opacity-50 text-xs font-semibold flex items-center gap-1 transition-colors"
        >
          <Send className="h-3.5 w-3.5" />
        </button>
      </form>
    </aside>
  );
}
